from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from common.jwt_decoder import JWTDecoder
from auth.schema import AuthDetails
from auth.jwt_encoder import JWTEncoder
from auth.password import get_password_hash, verify_password
from config import public_key, private_key, expire, algorithm, db_url, nats_url
from auth import dbmodel
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
from datetime import datetime
import nats
from nats.js import JetStreamContext
import orjson
from contextlib import asynccontextmanager
import uuid

jwt_encoder = JWTEncoder(key=private_key, algorithm=algorithm, expire=expire)
jwt_decoder = JWTDecoder(key=public_key, algorithm=algorithm)
jetstream: JetStreamContext = None
engine = create_async_engine(db_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.create_all)
    nc = await nats.connect(nats_url)
    global jetstream
    jetstream = nc.jetstream()
    await jetstream.add_stream(
        name="auth", subjects=["auth.account", "account.streams"]
    )
    # "auth.account" for auth business events
    # "account.streams" for cud events
    yield
    await nc.close()


app = FastAPI(lifespan=lifespan)
users = []


@app.post("/register", status_code=201)
async def register(auth_details: AuthDetails):
    async with AsyncSession(engine, expire_on_commit=False) as session:

        account_with_email = (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.email) == auth_details.email
                )
            )
        ).first()
        if account_with_email is not None:
            raise HTTPException(status_code=400, detail="Email is taken")

    async with AsyncSession(engine, expire_on_commit=False) as session:

        new_account = dbmodel.Account(
            fullname=auth_details.fullname,
            email=auth_details.email,
            role=auth_details.role,
            public_id=str(uuid.uuid4()),
            password_hash=get_password_hash(auth_details.password),
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
    await jetstream.publish(subject="account.streams", payload=event_data)  # cud
    await jetstream.publish(subject="auth.account", payload=event_data)  # be
    return {"message": "Account created"}


@app.post("/login")
async def login(auth_details: AuthDetails):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        account_with_email = (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account) == auth_details.email
                )
            )
        ).first()

    if (account_with_email is None) or (
        not verify_password(auth_details.password, account_with_email.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid email and/or password")
    token = jwt_encoder.encode_token(account_with_email.public_id)
    return {"token": token}


@app.get("/unprotected")
async def unprotected():
    return {"hello": "world"}


@app.get("/protected")
async def protected(public_id=Depends(jwt_decoder)):
    return {"public_id": public_id}


# with TestClient(app) as client:
#     client.get(headers={"Authorization": f"Bearer {jwt_encoder.encode_token('test')}"})
