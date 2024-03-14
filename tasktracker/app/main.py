"""The main application file containing the core logic of Task Tracker."""

from common.generate_events_from_schemas import generate_events_from_avro_schemas
from tasktracker.config import service_root

generate_events_from_avro_schemas(service_root)

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
from tasktracker.eventschema.tasktracker import (
    TaskAdded,
    TaskAssigned,
    TaskCompleted,
)
from tasktracker.eventschema.auth import AccountUpdated, AccountCreated

broker = NatsBroker(nats_url)
jstream = JStream(name="tasktracker", subjects=["tasks-lifecycle.>", "tasks-streams.>"])
authorizer = Authorizer(key=public_key, algorithm=algorithm)
engine = create_async_engine(db_url, echo=True)


async def random_popugs(size: int = 1) -> list[str]:
    """Utility function to get random popugs from database that are not managers or admins

    Args:
        size: the amount of popugs to get. Defaults to 1.

    Returns:
        List of public_ids of random popugs
    """
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
    subject=f"accounts-streams.{AccountCreated.v1.Name.ACCOUNTCREATED.value}.{AccountCreated.v1.Version.V1.value}",
    durable="AccountCreatedV1",
    stream=JStream(name="auth", declare=False),
    description="Handles event of new account creation.",
)
async def handle_create_account(msg: AccountCreated.v1.AccountCreatedV1):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add(
            dbmodel.Account(
                public_id=msg.data.account_public_id,
                fullname=msg.data.fullname,
                email=msg.data.email,
                role=msg.data.role,
            )
        )
        await session.commit()


@broker.subscriber(
    subject=f"accounts-streams.{AccountUpdated.v1.Name.ACCOUNTUPDATED.value}.{AccountUpdated.v1.Version.V1.value}",
    durable="AccountUpdatedV1",
    stream=JStream(name="auth", declare=False),
    deliver_policy="all",
)
async def handle_update_account(msg: AccountUpdated.v1.AccountUpdatedV1):
    """Handles event of account's update."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        account = (
            await session.exec(
                select(dbmodel.Account).where(
                    col(dbmodel.Account.public_id) == msg.data.account_public_id
                )
            )
        ).first()
        if account is not None:
            account.role = msg.data.role
            session.add(account)
            await session.commit()
            await session.refresh(account)
        else:
            session.add(
                dbmodel.Account(
                    public_id=msg.data.account_public_id,
                    fullname="None",
                    email="None",
                    role=msg.data.role,
                )
            )
            await session.commit()


@asynccontextmanager
async def instantiate_db_and_broker(app: FastAPI):
    """Utility function to instantiate database and broker when app starts.

    Args:
        app: FastAPI app
    """
    async with engine.begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.create_all)

    await broker.start()
    await broker.stream.add_stream(config=jstream.config)
    yield
    await broker.close()


api = FastAPI(lifespan=instantiate_db_and_broker)


@api.post("/add-task", status_code=201, dependencies=[Depends(authorizer)])
async def add_task(title: str, description: str):
    """Creates a new task for authorized popug.

    Args:
        description: Task description

    Raises:
        HTTPException: If no workers are available
    """
    random_popug = await random_popugs(size=1)
    if len(random_popug) == 0:
        raise HTTPException(status_code=403, detail="No popug available")
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (
            await session.exec(
                select(dbmodel.Task.title).where(col(dbmodel.Task.title) == title)
            )
        ).first() is not None:
            raise HTTPException(
                status_code=409, detail="Task with this title already exists"
            )

        new_task = dbmodel.Task(
            public_id=str(uuid.uuid4()),
            description=description,
            assigned_to=random_popug[0],
            title=title,
        )
        session.add(new_task)
        await session.commit()

        msg = TaskAdded.v1.TaskAddedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=TaskAdded.v1.Data(
                title=title,
                description=description,
                task_public_id=new_task.public_id,
                assigned_to=new_task.assigned_to,
            ),
        )
        await broker.publish(
            msg.model_dump_json().encode(),
            f"tasks-streams.{msg.name.value}.{msg.version.value}",
            stream=jstream.name,
        )

        msg_assign = TaskAssigned.v1.TaskAssignedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=TaskAssigned.v1.Data(
                task_public_id=new_task.public_id,
                assigned_to=new_task.assigned_to,
            ),
        )
        await broker.publish(
            msg_assign.model_dump_json().encode(),
            f"tasks-lifecycle.{msg_assign.name.value}.{msg_assign.version.value}",
            stream=jstream.name,
        )


@api.post(
    "/shuffle-tasks",
    status_code=201,
    dependencies=[Depends(authorizer.restrict_access(to=["manager", "admin"]))],
)
async def shuffle_tasks():
    """Assigns open tasks to random popugs.

    Raises:
        HTTPException: if no workers are available.

    Returns:
        Json of reassigned tasks
    """
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
            session.add(task)
            await session.commit()
            await session.refresh(task)
            shuffled.append(task.model_dump())
            msg = TaskAssigned.v1.TaskAssignedV1(
                id=str(uuid.uuid4()),
                time=datetime.now(),
                data=TaskAssigned.v1.Data(
                    task_public_id=task.public_id, assigned_to=task.assigned_to
                ),
            )

            await broker.publish(
                msg.model_dump_json().encode(),
                f"tasks-lifecycle.{msg.name.value}.{msg.version.value}",
                stream=jstream.name,
            )

    return shuffled


@api.get("/tasks", status_code=200, dependencies=[Depends(authorizer)])
async def tasks(status: Optional[Literal["completed", "open"]] = None):
    """Shows all tasks or filtered by status for authorized popug.

    Args:
        status: Task status (for filtering)

    Returns:
        Json of tasks
    """
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
    public_id=Depends(authorizer), status: Optional[Literal["completed", "open"]] = None
):
    """Shows all tasks (of filtered by status) assigned to authorized popug.

    Args:
        public_id: uuid of authorized popug.
        status: filter by status.

    Returns:
        Json of tasks
    """
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


@api.post("/complete-task", status_code=200)
async def complete_task(task_id: int, account_public_id: str = Depends(authorizer)):
    """Closes tasks assigned to authorized popug.

    Args:
        task_public_id: uuid of task
        public_id: uuid of authorized popug

    Raises:
        HTTPException: if task is not found
        HTTPException: if task is not assigned to authorized popug

    Returns:
        _description_
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        task = (
            await session.exec(
                select(dbmodel.Task).where(col(dbmodel.Task.id) == task_id)
            )
        ).first()
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.assigned_to != account_public_id:
            raise HTTPException(
                status_code=403, detail="You are not assigned to this task"
            )
        if task.status == "completed":
            raise HTTPException(status_code=400, detail="Task already completed")
        task.status = "completed"
        session.add(task)
        await session.commit()
        await session.refresh(task)
        msg = TaskCompleted.v1.TaskCompletedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=TaskCompleted.v1.Data(task_public_id=task.public_id),
        )
        await broker.publish(
            msg,
            f"tasks-lifecycle.{msg.name.value}.{msg.version.value}",
            stream=jstream.name,
        )

    return "Task completed"
