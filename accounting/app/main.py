from common.generate_events_from_schemas import generate_events_from_avro_schemas
from accounting.config import service_root, nats_url, db_url
from accounting.eventschema.tasktracker import (
    TaskAssigned,
    TaskCompleted,
    TaskAdded,
)
from accounting.eventschema.accounting import FinTransactionApplied
from accounting import dbmodel
from typing import Any
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, col
import uuid
from datetime import datetime
from typing import Optional
import numpy as np

generate_events_from_avro_schemas(service_root)


from faststream.nats import NatsBroker, JStream
from faststream import FastStream

broker = NatsBroker(nats_url)
app = FastStream(broker)
jstream = JStream(name="accounting", subjects=["transactions.*"])
engine = create_async_engine(db_url, echo=True)


async def get_billing_cycle_id(session: AsyncSession, public_id: str) -> Optional[int]:
    return (
        await session.exec(
            select(dbmodel.BillingCycle.id).where(
                dbmodel.BillingCycle.status == "active"
            )
        )
    ).first()


async def get_account(
    session: AsyncSession, account_public_id: str
) -> Optional[dbmodel.Account]:
    return (
        await session.exec(
            select(dbmodel.Account).where(
                dbmodel.Account.public_id == account_public_id
            )
        )
    ).first()


async def get_task(
    session: AsyncSession, task_public_id: str
) -> Optional[dbmodel.Task]:
    return (
        await session.exec(
            select(dbmodel.Task).where(dbmodel.Task.public_id == task_public_id)
        )
    ).first()


@broker.subscriber(
    subject=f"tasks-lifecycle.{TaskAssigned.v1.Name.TASKASSIGNED}.{TaskAssigned.v1.Version.V1}",
    durable=f"tasks-lifecycle.{TaskAssigned.v1.Name.TASKASSIGNED}.{TaskAssigned.v1.Version.V1}",
    stream=JStream(name="tasktracker", declare=False),
    deliver_policy="all",
    retry=True,  # will retry to consume the message if it callback fails
)
async def apply_transaction_for_task_assignment(msg: TaskAssigned.v1.TaskAssignedV1):
    async with AsyncSession(engine, expire_on_commit=False) as session:

        task = await get_task(session, msg.data.task_public_id)
        account = await get_account(session, msg.data.assigned_to)

        transaction = dbmodel.Transaction(
            billing_cycle=await get_billing_cycle_id(session, "active"),
            public_id=str(uuid.uuid4()),
            account_id=msg.data.assigned_to,
            credit=0.0,
            debit=task.complete_task_cost,
            type=FinTransactionApplied.v1.TransactionType.ENROLLMENT.value,
            task_public_id=msg.data.task_public_id,
            description=f"{FinTransactionApplied.v1.TransactionType.ENROLLMENT.value} for task {task.title}",
        )

        account.balance -= task.complete_task_cost
        session.add(transaction)
        session.add(account)
        session.commit()

        msg = FinTransactionApplied.v1.FinTransactionAppliedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=FinTransactionApplied.v1.Data(
                account_public_id=msg.data.assigned_to,
                type=FinTransactionApplied.v1.TransactionType.ENROLLMENT.value,
                description=f"{FinTransactionApplied.v1.TransactionType.ENROLLMENT.value} for task {task.title}",
                amount=task.complete_task_cost,
            ),
        )
        await broker.publish(
            msg.model_dump_json().encode(),
            f"transactions.{msg.name.value}.{msg.version.value}",
            stream=jstream.name,
        )


@broker.subscriber(
    subject=f"tasks-lifecycle.{TaskCompleted.v1.Name.TASKCOMPLETED}.{TaskCompleted.v1.Version.V1}",
    durable=f"tasks-lifecycle.{TaskCompleted.v1.Name.TASKCOMPLETED}.{TaskCompleted.v1.Version.V1}",
    stream=JStream(name="tasktracker", declare=False),
    retry=True,  # will retry to consume the message if it callback fails
)
async def apply_transaction_for_task_completion(msg: TaskAssigned.v1.TaskAssignedV1):
    async with AsyncSession(engine, expire_on_commit=False) as session:

        task = await get_task(session, msg.data.task_public_id)
        account = await get_account(session, msg.data.assigned_to)

        transaction = dbmodel.Transaction(
            billing_cycle=await get_billing_cycle_id(session, "active"),
            public_id=str(uuid.uuid4()),
            account_id=msg.data.assigned_to,
            credit=task.assign_task_cost,
            debit=0.0,
            type=FinTransactionApplied.v1.TransactionType.WITHDRAWAL.value,
            task_public_id=msg.data.task_public_id,
            description=f"{FinTransactionApplied.v1.TransactionType.WITHDRAWAL.value} for task {task.title}",
        )

        account.balance += task.assign_task_cost
        session.add(transaction)
        session.add(account)
        session.commit()

        msg = FinTransactionApplied.v1.FinTransactionAppliedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=FinTransactionApplied.v1.Data(
                account_public_id=msg.data.assigned_to,
                type=FinTransactionApplied.v1.TransactionType.WITHDRAWAL.value,
                description=f"{FinTransactionApplied.v1.TransactionType.WITHDRAWAL.value} for task {task.title}",
                amount=task.assign_task_cost,
            ),
        )
        await broker.publish(
            msg.model_dump_json().encode(),
            f"transactions.{msg.name.value}.{msg.version.value}",
            stream=jstream.name,
        )


@broker.subscriber(
    subject=f"tasks-streams.{TaskAdded.v1.Name.TASKADDED}.{TaskAdded.v1.Version.V1}",
    durable=f"tasks-streams.{TaskAdded.v1.Name.TASKADDED}.{TaskAdded.v1.Version.V1}",
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
            assign_task_cost=float(np.random.randint(10, 20)),
            complete_task_cost=float(np.random.randint(20, 40)),
        )
        session.add(task)
        session.commit()
