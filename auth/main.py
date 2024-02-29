from fastapi import FastAPI, Depends, HTTPException
from common.authorizer import Authorizer
from auth.schema import RegisterDetails, LoginDetails
from auth.authenticator import Authentificator
from auth.password import get_password_hash, verify_password
from config import public_key, private_key, expire, algorithm, db_url, nats_url
from auth import dbmodel
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
import nats
from nats.js import JetStreamContext
import orjson
from contextlib import asynccontextmanager
import uuid

auhtentificator = Authentificator(key=private_key, algorithm=algorithm, expire=expire)
authorizer = Authorizer(key=public_key, algorithm=algorithm)
jetstream: JetStreamContext = None
engine = create_async_engine(db_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.create_all)
    nc = await nats.connect(nats_url)
    global jetstream
    jetstream = nc.jetstream()
    await jetstream.add_stream(name="auth", subjects=["accounts", "accounts-streams"])
    # "auth.account" for auth business events
    # "account.streams" for cud events
    yield
    await nc.close()


app = FastAPI(lifespan=lifespan)
users = []


@app.post("/register", status_code=201)
async def register(register_details: RegisterDetails):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        account_with_email = (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.email) == register_details.email
                )
            )
        ).first()
        if account_with_email is not None:
            raise HTTPException(status_code=400, detail="Email is taken")

    async with AsyncSession(engine, expire_on_commit=False) as session:
        new_account = dbmodel.Account(
            fullname=register_details.fullname,
            email=register_details.email,
            role=register_details.role,
            public_id=str(uuid.uuid4()),
            password_hash=get_password_hash(register_details.password),
        )
        session.add(new_account)
        await session.commit()
        event_data = orjson.dumps(
            dict(
                public_id=new_account.public_id,
                fullname=new_account.fullname,
                email=new_account.email,
                role=new_account.role,
            )
        )
    await jetstream.publish(subject="accounts-streams", payload=event_data)  # cud
    await jetstream.publish(subject="accounts", payload=event_data)  # be
    return {"message": "Account created"}


@app.post("/login")
async def login(login_details: LoginDetails):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        account_with_email = (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.email) == login_details.email
                )
            )
        ).first()

    if (account_with_email is None) or (
        not verify_password(login_details.password, account_with_email.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid email and/or password")
    token = auhtentificator.encode_token(
        account_with_email.public_id, account_with_email.role
    )
    return {"token": token}


@app.get("/unprotected")
async def unprotected():
    return {"hello": "world"}


@app.get("/protected")
async def protected(public_id: str = Depends(authorizer.restrict_access(to=["admin"]))):
    return {"public_id": public_id}


# with TestClient(app) as client:
#     client.get(headers={"Authorization": f"Bearer {jwt_encoder.encode_token('test')}"})
