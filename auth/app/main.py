from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from common.authorizer import Authorizer
from auth.schema import RegisterDetails, LoginDetails
from auth.authenticator import Authentificator
from auth.password import get_password_hash, verify_password
from auth.config import public_key, private_key, expire, algorithm, db_url, nats_url
from auth import dbmodel
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
import orjson
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from faststream.nats import NatsBroker, JStream


broker = NatsBroker(nats_url)
stream = JStream(name="auth", subjects=["accounts.*", "accounts-streams.*"])
auhtentificator = Authentificator(key=private_key, algorithm=algorithm, expire=expire)
authorizer = Authorizer(key=public_key, algorithm=algorithm)
engine = create_async_engine(db_url, echo=True)


async def add_account(fullname: str, email: str, password: str, role: str) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        new_account = dbmodel.Account(
            fullname=fullname,
            email=email,
            role=role,
            public_id=str(uuid.uuid4()),
            password_hash=get_password_hash(password),
        )
        session.add(new_account)
        await session.commit()
        event_data = orjson.dumps(
            dict(
                public_id=new_account.public_id,
                fullname=new_account.fullname,
                email=new_account.email,
                role=new_account.role,
                created_at=new_account.created_at,
            )
        )
    await broker.publish(
        event_data, "accounts-streams.account-created", stream=stream.name
    )
    # Maybe not reasonable to publish BE here, but just in case
    await broker.publish(
        event_data, "accounts.account-created", stream=stream.name
    )  # be


@asynccontextmanager
async def instantiate_db_and_broker(app: FastAPI):
    await broker.connect(nats_url)
    await broker.stream.add_stream(config=stream.config)
    print("connected")
    async with engine.begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.email) == "admin@popug.com"
                )
            )
        ).first() is None:
            await add_account(
                fullname="root",
                email="admin@popug.com",
                password="password",
                role="admin",
            )

    yield
    await broker.close()


api = FastAPI(lifespan=instantiate_db_and_broker)


@api.post("/register", status_code=201)
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
    await add_account(
        fullname=register_details.fullname,
        email=register_details.email,
        password=register_details.password,
        role="user",
    )
    return "Account created"


@api.get("/login")
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
    await broker.publish(
        orjson.dumps(
            dict(
                public_id=account_with_email.public_id,
                email=account_with_email.email,
                logined_at=datetime.now(),
            )
        ),
        "accounts.account-logined",
        stream=stream.name,
    )

    return token


@api.post(
    "/change-role",
    status_code=200,
    dependencies=[Depends(authorizer.restrict_access(to=["admin", "manager"]))],
)
async def change_role(
    role: str, public_user_id: str | None = None, email: str | None = None
):
    if (public_user_id is None) + (email is None) != 1:
        raise HTTPException(
            status_code=400, detail="Provide either public_user_id or email"
        )

    statement = (
        select(dbmodel.Account).where(col(dbmodel.Account.public_id) == public_user_id)
        if public_user_id is not None
        else select(dbmodel.Account).where(col(dbmodel.Account.email) == email)
    )

    async with AsyncSession(engine, expire_on_commit=False) as session:
        account = (await session.exec(statement)).first()
        print(account)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        account.role = role
        account.updated_at = datetime.now()

        session.add(account)
        await session.commit()
        await session.refresh(account)
        print("REFRESGE", account)
        event_data = orjson.dumps(
            dict(
                public_id=account.public_id,
                fullname=account.fullname,
                email=account.email,
                role=account.role,
                updated_at=account.updated_at,
            )
        )

    await broker.publish(
        event_data, "accounts-streams.role-changed", stream=stream.name
    )
    return f"Role for {account.email} changed"
