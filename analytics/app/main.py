from common.generate_events_from_schemas import generate_events_from_avro_schemas
from analytics.config import service_root, nats_url, db_url, public_key, algorithm

generate_events_from_avro_schemas(service_root)

from analytics.eventschema.tasktracker import (
    TaskAdded,
)
from contextlib import asynccontextmanager

from analytics.eventschema.auth import AccountUpdated, AccountCreated
from analytics.eventschema.accounting import (
    FinTransactionApplied,
    TaskCostsGenerated,
)
from analytics import dbmodel
from typing import Any
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, col
from datetime import datetime, date
from sqlmodel import func, and_
from fastapi import FastAPI, Depends
from faststream.nats import NatsBroker, JStream
from faststream import FastStream
from common.authorizer import Authorizer

broker = NatsBroker(nats_url)
engine = create_async_engine(db_url, echo=False)
authorizer = Authorizer(key=public_key, algorithm=algorithm)


@broker.subscriber(
    subject=f"accounts-streams.{AccountCreated.v1.Name.ACCOUNTCREATED.value}.{AccountCreated.v1.Version.V1.value}",
    durable="AnalyticsAccountCreatedV1",
    stream=JStream(name="auth", declare=False),
    description="Handles event of new account creation.",
)
async def handle_create_account(msg: AccountCreated.v1.AccountCreatedV1):
    async with AsyncSession(engine, expire_on_commit=True) as session:
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
    durable="AnalyticsAccountUpdatedV1",
    stream=JStream(name="auth", declare=False),
    deliver_policy="all",
    retry=True,
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

        account.role = msg.data.role
        session.add(account)
        await session.commit()


@broker.subscriber(
    subject=f"tasks-streams.{TaskAdded.v1.Name.TASKADDED.value}.{TaskAdded.v1.Version.V1.value}",
    durable="AnalyticsTaskAddedV1",
    stream=JStream(name="tasktracker", declare=False),
    deliver_policy="all",
)
async def add_task_to_db(msg: TaskAdded.v1.TaskAddedV1):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        task = dbmodel.Task(
            public_id=msg.data.task_public_id,
            title=msg.data.title,
            description=msg.data.description,
            assigned_to=msg.data.assigned_to,
        )
        session.add(task)
        await session.commit()


@broker.subscriber(
    subject=f"accounting-tasks-streams.{TaskCostsGenerated.v1.Name.TASKCOSTSGENERATED.value}.{TaskCostsGenerated.v1.Version.V1.value}",
    durable="AnalyticsTaskCostGeneratedV1",
    stream=JStream(name="accounting", declare=False),
    deliver_policy="all",
    retry=True,
)
async def add_task_to_db(msg: TaskCostsGenerated.v1.TaskCostsGeneratedV1):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        task = (
            await session.exec(
                select(dbmodel.Task).where(
                    dbmodel.Task.public_id == msg.data.task_public_id
                )
            )
        ).first()
        if task is None:
            raise Exception("Task not found. Sending to DLQ")

        task.assign_task_cost = msg.data.assign_cost
        task.complete_task_cost = msg.data.complete_cost
        session.add(task)
        await session.commit()


@broker.subscriber(
    subject=f"transactions.{FinTransactionApplied.v1.Name.FINTRANSACTIONAPPLIED.value}.{FinTransactionApplied.v1.Version.V1.value}",
    durable="AnalyticsFinTransactionAppliedV1",
    stream=JStream(name="accounting", declare=False),
    retry=True,  # will retry to consume the message if it callback fails
)
async def add_transaction_to_db(msg: FinTransactionApplied.v1.FinTransactionAppliedV1):
    if msg.data.type != FinTransactionApplied.v1.TransactionType.PAYMENT:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(
                dbmodel.Transaction(
                    account_public_id=msg.data.account_public_id,
                    time=msg.time,
                    transaction_type=msg.data.type,
                    credit=(
                        msg.data.amount
                        if msg.data.type
                        == FinTransactionApplied.v1.TransactionType.WITHDRAWAL
                        else 0.0
                    ),
                    debit=(
                        msg.data.amount
                        if msg.data.type
                        == FinTransactionApplied.v1.TransactionType.ENROLLMENT
                        else 0.0
                    ),
                    description=msg.data.description,
                    type=msg.data.type.value,
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
    yield
    await broker.close()


api = FastAPI(lifespan=instantiate_db_and_broker)


@api.get(
    "/today-earnings",
    dependencies=[Depends(authorizer.restrict_access(to=["admin", "manager"]))],
)
async def get_today_earnings():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        today_min_time = datetime.combine(date.today(), datetime.min.time())
        today_max_time = datetime.combine(date.today(), datetime.max.time())
        transactions = (
            await session.exec(
                select(dbmodel.Transaction)
                .where(dbmodel.Transaction.time <= today_max_time)
                .where(dbmodel.Transaction.time >= today_min_time)
            )
        ).all()

        return {"total_earnings": sum(t.debit - t.credit for t in transactions)}


@api.get(
    "/popug-stats",
    dependencies=[Depends(authorizer.restrict_access(to=["admin", "manager"]))],
)
async def popug_stats():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        today_min_time = datetime.combine(date.today(), datetime.min.time())
        today_max_time = datetime.combine(date.today(), datetime.max.time())
        popug_debits_credits = (
            await session.exec(
                select(
                    dbmodel.Transaction.account_public_id,
                    func.sum(dbmodel.Transaction.debit).label("debit"),
                    func.sum(dbmodel.Transaction.credit).label("credit"),
                )
                .where(
                    and_(
                        dbmodel.Transaction.time >= today_min_time,
                        dbmodel.Transaction.time <= today_max_time,
                    )
                )
                .group_by(dbmodel.Transaction.account_public_id)
            )
        ).all()

        return {
            "minus_popugs": sum((t.credit - t.debit < 0) for t in popug_debits_credits),
            "plus_popugs": sum((t.credit - t.debit > 0) for t in popug_debits_credits),
        }


@api.get(
    "/most-expensive-task",
    dependencies=[Depends(authorizer.restrict_access(to=["admin", "manager"]))],
)
async def most_expensive_task(from_dt: datetime, to_dt: datetime):
    # Not done yet
    pass
