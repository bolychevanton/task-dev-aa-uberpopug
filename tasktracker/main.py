from fastapi import FastAPI, Depends, HTTPException
from common.authorizer import Authorizer
from tasktracker.config import (
    public_key,
    algorithm,
    db_url,
    nats_url,
)
from tasktracker import dbmodel
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
import nats
from nats.js import JetStreamContext
import orjson
from contextlib import asynccontextmanager
import uuid
from datetime import datetime

authorizer = Authorizer(key=public_key, algorithm=algorithm)
jetstream: JetStreamContext = None
engine = create_async_engine(db_url)


@asynccontextmanager
async def instantiate_db_and_broker(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.email) == "root@localhost.ru"
                )
            )
        ).first() is None:
            session.add(
                dbmodel.Account(
                    fullname="root",
                    email="root@localhost.ru",
                    role="admin",
                    public_id=str(uuid.uuid4()),
                    password_hash=get_password_hash("root"),
                )
            )
            await session.commit()

    nc = await nats.connect(nats_url)
    global jetstream
    jetstream = nc.jetstream()

    # "auth.account" for auth business events
    # "account.streams" for cud events
    await jetstream.add_stream(name="tasks", subjects=["TASKS.*", "TASKS-STREAMS.*"])
    yield
    await nc.close()


app = FastAPI(lifespan=instantiate_db_and_broker)


def create_task(public_id=Depends(authorizer)):
    return {"public_id": public_id}


def shuffle_tasks(
    public_id=Depends(authorizer.restrict_access(to=["manager", "admin"]))
):
    return {"public_id": public_id}


def tasks(public_id=Depends(authorizer), status: str = None, from_ts=None, to_ts=None):
    return {"public_id": public_id}


def complete_task(task_public_id: str, public_id: str = Depends(authorizer)):
    return {"public_id": public_id}


def show_my_tasks(public_id=Depends(authorizer)):
    return {"public_id": public_id}
