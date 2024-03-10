"""The main application file containing the core logic of Auth service."""

from common.generate_events_from_schemas import generate_events_from_avro_schemas
from auth.config import service_root

generate_events_from_avro_schemas(service_root)

from auth.eventschema.auth import AccountCreated, AccountUpdated

from fastapi import FastAPI, Depends, HTTPException
from common.authorizer import Authorizer
from auth.schema import RegisterDetails, LoginDetails
from auth.authenticator import Authentificator
from auth.password import get_password_hash, verify_password
from auth.config import public_key, private_key, expire, algorithm, db_url, nats_url
from auth import dbmodel
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from faststream.nats import NatsBroker, JStream
from fastapi.responses import PlainTextResponse
from typing import Optional


broker = NatsBroker(nats_url)
jstream = JStream(name="auth", subjects=["accounts-streams.>"])
auhtentificator = Authentificator(key=private_key, algorithm=algorithm, expire=expire)
authorizer = Authorizer(key=public_key, algorithm=algorithm)
engine = create_async_engine(db_url, echo=True)


async def register_account(fullname: str, email: str, password: str, role: str) -> None:
    """Utility function to register new account via adding it to database.

    Args:
        fullname: full name of popug to add
        email: popug's email address. Also used as login
        password: popug's password
        role: popug's role
    """
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
        msg = AccountCreated.v1.AccountCreatedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=AccountCreated.v1.Data(
                account_public_id=new_account.public_id,
                email=new_account.email,
                role=role,
                fullname=fullname,
            ),
        )

    await broker.publish(
        msg.model_dump_json().encode(),
        f"accounts-streams.{msg.name.value}.{msg.version.value}",
        stream=jstream.name,
    )


@asynccontextmanager
async def instantiate_db_and_broker(app: FastAPI):
    """Utility function to instantiate database and broker when app starts.

    Note:
        This function registers admin account if it doesn't exist.

    Args:
        app: FastAPI app
    """

    await broker.start()
    await broker.stream.add_stream(config=jstream.config)
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
            await register_account(
                fullname="root",
                email="admin@popug.com",
                password="password",
                role="admin",
            )

    yield
    await broker.close()


api = FastAPI(lifespan=instantiate_db_and_broker)


@api.post("/register", status_code=201, response_class=PlainTextResponse)
async def register(register_details: RegisterDetails) -> str:
    """Registers new account with user role.

    Args:
        register_details: email (a.k.a. login), password, and full name

    Raises:
        HTTPException: If email is already taken

    Returns:
        Message that account was created.
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        account_with_email = (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.email) == register_details.email
                )
            )
        ).first()
        if account_with_email is not None:
            raise HTTPException(
                status_code=400, detail="Email with this email is already registered"
            )
    await register_account(
        fullname=register_details.fullname,
        email=register_details.email,
        password=register_details.password,
        role="user",
    )
    return "Account registered"


@api.get("/login", response_class=PlainTextResponse)
async def login(login_details: LoginDetails) -> str:
    """Get auth JWT token.

    Args:
        login_details: email and password

    Raises:
        HTTPException: if invalid email and/or password

    Returns:
        JWT token
    """
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

    return token


@api.post(
    "/change-role",
    status_code=200,
    dependencies=[Depends(authorizer.restrict_access(to=["admin", "manager"]))],
    response_class=PlainTextResponse,
)
async def change_role(
    role: str, public_user_id: Optional[str] = None, email: Optional[str] = None
) -> str:
    """Changes popug's role either by public_user_id or by email.

    Args:
        role: new role
        public_user_id: uuid of popug.
        email: email of popug

    Raises:
        HTTPException: if no public_user_id or email is provided
        HTTPException: Account not found

    Returns:
        Message that role was changed.
    """
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

        session.add(account)
        await session.commit()
        await session.refresh(account)
        msg = AccountUpdated.v1.AccountUpdatedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=AccountUpdated.v1.Data(
                account_public_id=account.public_id, role=account.role
            ),
        )
    await broker.publish(
        msg.model_dump_json().encode(),
        f"accounts-streams.{msg.name.value}.{msg.version.value}",
        stream=jstream.name,
    )
    return f"Role for {account.email} changed to {account.role}"
