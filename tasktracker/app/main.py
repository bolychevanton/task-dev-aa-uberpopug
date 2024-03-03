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
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from faststream.nats import NatsBroker, JStream
import numpy as np
from typing import Literal, Optional

broker = NatsBroker(nats_url)
stream = JStream(name="tasks", subjects=["tasks.*", "tasks-streams.*"])
authorizer = Authorizer(key=public_key, algorithm=algorithm)
engine = create_async_engine(db_url, echo=True)


async def random_popugs(size: int = 1) -> list[str]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        popugs = (
            await session.exec(
                select(dbmodel.Account.public_id)
                .where(col(dbmodel.Account.role) != "manager")
                .where(col(dbmodel.Account.role) != "admin")
            )
        ).all()
    if len(popugs) > 0:
        return [popugs[i] for i in np.random.randint(len(popugs), size=size)]
    else:
        return []


@broker.subscriber(
    "accounts-streams.account-created",
    stream=JStream(name="auth", declare=False),
    deliver_policy="all",
)
async def handle_new_account(public_id: str, fullname: str, email: str, role: str):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add(
            dbmodel.Account(
                public_id=public_id, fullname=fullname, email=email, role=role
            )
        )
        await session.commit()


@broker.subscriber(
    "accounts-streams.role-changed",
    stream=JStream(name="auth", declare=False),
    deliver_policy="all",
)
async def role_changed(public_id: str, fullname: str, email: str, role: str):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        account = (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.public_id) == public_id
                )
            )
        ).first()
        if account is not None:
            account.role = role
            session.add(account)
            await session.commit()
            await session.refresh(account)
        else:
            session.add(
                dbmodel.Account(
                    public_id=public_id, fullname=fullname, email=email, role=role
                )
            )
            await session.commit()


@asynccontextmanager
async def instantiate_db_and_broker(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.create_all)

    await broker.start()
    await broker.stream.add_stream(config=stream.config)
    yield
    await broker.close()


api = FastAPI(lifespan=instantiate_db_and_broker)


@api.post("/create-task", status_code=201, dependencies=[Depends(authorizer)])
async def create_task(description: str):
    random_popug = await random_popugs(size=1)
    if len(random_popug) == 0:
        raise HTTPException(status_code=403, detail="No popug available")
    async with AsyncSession(engine, expire_on_commit=False) as session:
        new_task = dbmodel.Task(
            public_id=str(uuid.uuid4()),
            description=description,
            assigned_to=random_popug[0],
        )
        session.add(new_task)
        await session.commit()
        msg = new_task.model_dump_json(
            include={"public_id", "description", "assigned_to", "created_at"}
        ).encode()
        await broker.publish(msg, "tasks-streams.task-created", stream=stream.name)
        await broker.publish(msg, "tasks.task-created", stream=stream.name)


@api.post(
    "/shuffle-tasks",
    status_code=201,
    dependencies=[Depends(authorizer.restrict_access(to=["manager", "admin"]))],
)
async def shuffle_tasks():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        open_tasks = (
            await session.exec(
                select(dbmodel.Task).where(col(dbmodel.Task.status) == "open")
            )
        ).all()

        random_popugs_uuids = await random_popugs(size=len(open_tasks))
        if len(random_popugs_uuids) == 0:
            raise HTTPException(status_code=403, detail="No popugs available")

        shuffled = []
        for i, task in enumerate(open_tasks):
            task.assigned_to = random_popugs_uuids[i]
            task.updated_at = datetime.now()
            session.add(task)
            await session.commit()
            await session.refresh(task)
            shuffled.append(task.model_dump())
            msg = task.model_dump_json(
                include={"public_id", "assigned_to", "updated_at", "description"}
            ).encode()
            await broker.publish(
                msg, "tasks-streams.task-assignee-updated", stream=stream.name
            )
            await broker.publish(msg, "tasks.task-assignee-updated", stream=stream.name)

    return shuffled


@api.get("/tasks", status_code=200, dependencies=[Depends(authorizer)])
async def tasks(status: Optional[Literal["closed", "open"]] = None):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if status is None:
            tasks = await session.exec(select(dbmodel.Task))
        else:
            tasks = await session.exec(
                select(dbmodel.Task).where(col(dbmodel.Task.status) == status)
            )
        return [task.model_dump() for task in tasks.all()]


@api.get("/tasks-me", status_code=200)
async def show_my_tasks(
    public_id=Depends(authorizer), status: Optional[Literal["closed", "open"]] = None
):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if status is None:
            tasks = await session.exec(
                select(dbmodel.Task).where(col(dbmodel.Task.assigned_to) == public_id)
            )
        else:
            tasks = await session.exec(
                select(dbmodel.Task)
                .where(col(dbmodel.Task.assigned_to) == public_id)
                .where(col(dbmodel.Task.status) == status)
            )
        return [task.model_dump() for task in tasks.all()]


@api.post("/close-task", status_code=200)
async def close_task(task_public_id: str, public_id: str = Depends(authorizer)):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        task = (
            await session.exec(
                select(dbmodel.Task).where(
                    col(dbmodel.Task.public_id) == task_public_id
                )
            )
        ).first()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.assigned_to != public_id:
            raise HTTPException(
                status_code=403, detail="You are not assigned to this task"
            )
        task.status = "closed"
        task.updated_at = datetime.now()
        session.add(task)
        await session.commit()
        await session.refresh(task)
        msg = task.model_dump_json(
            include={"public_id", "assigned_to", "updated_at", "description"}
        ).encode()
        await broker.publish(msg, "tasks-streams.task-closed", stream=stream.name)
        await broker.publish(msg, "tasks.task-closed", stream=stream.name)

    return "Task closed"
