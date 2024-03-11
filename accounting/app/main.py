from common.generate_events_from_schemas import generate_events_from_avro_schemas
from accounting.config import service_root, nats_url, db_url
from accounting.eventschema.tasktracker import (
    TaskAssigned,
    TaskCompleted,
    TaskAdded,
)
from accounting.eventschema.auth import AccountUpdated, AccountCreated
from accounting.eventschema.accounting import FinTransactionApplied, EndOfDayHappened
from accounting import dbmodel
from typing import Any
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, col
import uuid
from datetime import datetime
from typing import Optional
import numpy as np
from datetime import date, timedelta

generate_events_from_avro_schemas(service_root)


from faststream.nats import NatsBroker, JStream
from faststream import FastStream


broker = NatsBroker(nats_url)
app = FastStream(broker)
jstream = JStream(name="accounting", subjects=["cron.>", "transactions.>"])
engine = create_async_engine(db_url, echo=False)

# cron_app = Rocketry(execution="async")


@app.on_startup
async def create_tables():
    await broker.connect()
    await broker.stream.add_stream(config=jstream.config)
    async with engine.begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.create_all)
    # await cron_app.serve()


# @cron_app.task("every 5 seconds", execution="async")
# async def print_hello():
#     print("hello")


async def get_active_billing_cycle_id(
    session: AsyncSession, public_id: str
) -> Optional[int]:
    return (
        await session.exec(
            select(dbmodel.BillingCycle.id)
            .where(dbmodel.BillingCycle.status == "active")
            .where(dbmodel.BillingCycle.account_public_id == public_id)
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
    subject=f"accounts-streams.{AccountCreated.v1.Name.ACCOUNTCREATED.value}.{AccountCreated.v1.Version.V1.value}",
    durable="AccountingAccountCreatedV1",
    stream=JStream(name="auth", declare=False),
    description="Handles event of new account creation.",
)
async def handle_create_account_other(msg: AccountCreated.v1.AccountCreatedV1):
    async with AsyncSession(engine, expire_on_commit=True) as active:
        account = await get_account(active, msg.data.account_public_id)

    if account is None:
        async with AsyncSession(engine, expire_on_commit=True) as bill_cycle_session:
            billing_cycle = dbmodel.BillingCycle(
                status="active",
                account_public_id=msg.data.account_public_id,
            )

            bill_cycle_session.add(billing_cycle)
            await bill_cycle_session.commit()

        async with AsyncSession(engine, expire_on_commit=True) as session:
            session.add(
                dbmodel.Account(
                    public_id=msg.data.account_public_id,
                    fullname=msg.data.fullname,
                    email=msg.data.email,
                    role=msg.data.role,
                    billing_cycle=await get_active_billing_cycle_id(
                        session, msg.data.account_public_id
                    ),
                )
            )
            await session.commit()


@broker.subscriber(
    subject=f"accounts-streams.{AccountUpdated.v1.Name.ACCOUNTUPDATED.value}.{AccountUpdated.v1.Version.V1.value}",
    durable="AccountingAccountUpdatedV1",
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
    durable="AccountingTaskAddedV1",
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
        await session.commit()


@broker.subscriber(
    subject=f"tasks-lifecycle.{TaskAssigned.v1.Name.TASKASSIGNED.value}.{TaskAssigned.v1.Version.V1.value}",
    durable="AccountingTaskAssignedV1",
    stream=JStream(name="tasktracker", declare=False),
    deliver_policy="all",
    retry=True,  # will retry to consume the message if it callback fails
)
async def apply_transaction_for_task_assignment(msg: TaskAssigned.v1.TaskAssignedV1):
    async with AsyncSession(engine, expire_on_commit=False) as session:

        task = await get_task(session, msg.data.task_public_id)
        if task is None:
            raise Exception("Task not found. Sending to DLQ.")
        account = await get_account(session, msg.data.assigned_to)
        if account is None:
            raise Exception("Account not found. Sending to DLQ.")

        transaction = dbmodel.Transaction(
            billing_cycle=await get_active_billing_cycle_id(
                session, msg.data.assigned_to
            ),
            public_id=str(uuid.uuid4()),
            account_id=msg.data.assigned_to,
            credit=0.0,
            debit=task.assign_task_cost,
            type=FinTransactionApplied.v1.TransactionType.ENROLLMENT.value,
            task_public_id=msg.data.task_public_id,
            description=f"{FinTransactionApplied.v1.TransactionType.ENROLLMENT.value} for task {task.title}",
        )

        account.balance -= task.assign_task_cost
        session.add(transaction)
        session.add(account)
        await session.commit()

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
    subject=f"tasks-lifecycle.{TaskCompleted.v1.Name.TASKCOMPLETED.value}.{TaskCompleted.v1.Version.V1.value}",
    durable="AccountingTaskCompletedV1",
    stream=JStream(name="tasktracker", declare=False),
    retry=True,  # will retry to consume the message if it callback fails
)
async def apply_transaction_for_task_completion(msg: TaskCompleted.v1.TaskCompletedV1):
    async with AsyncSession(engine, expire_on_commit=False) as session:

        task = await get_task(session, msg.data.task_public_id)
        account = await get_account(session, task.assigned_to)

        transaction = dbmodel.Transaction(
            billing_cycle=await get_active_billing_cycle_id(session, task.assigned_to),
            public_id=str(uuid.uuid4()),
            account_id=task.assigned_to,
            credit=task.complete_task_cost,
            debit=0.0,
            type=FinTransactionApplied.v1.TransactionType.WITHDRAWAL.value,
            task_public_id=msg.data.task_public_id,
            description=f"{FinTransactionApplied.v1.TransactionType.WITHDRAWAL.value} for task {task.title}",
        )

        account.balance += task.complete_task_cost
        session.add(transaction)
        session.add(account)
        await session.commit()

        msg = FinTransactionApplied.v1.FinTransactionAppliedV1(
            id=str(uuid.uuid4()),
            time=datetime.now(),
            data=FinTransactionApplied.v1.Data(
                account_public_id=task.assigned_to,
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
    subject=f"cron.{EndOfDayHappened.v1.Name.ENDOFDAYHAPPENED.value}.{EndOfDayHappened.v1.Version.V1.value}",
    durable="AccountingEndOfDayHappenedV1",
    stream=JStream(name="accounting", declare=False),
    retry=True,  # will retry to consume the message if it callback fails
)
async def close_billing_cycles():
    tommorow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
    new_billing_cycle_start = datetime.combine(tommorow, datetime.min.time())
    new_billing_cycle_end = datetime.combine(tommorow, datetime.max.time())
    async with AsyncSession(engine, expire_on_commit=False) as session:
        open_billing_cycles = await session.exec(
            select(dbmodel.BillingCycle).where(dbmodel.BillingCycle.status == "active")
        )
        msgs: list[FinTransactionApplied.v1.FinTransactionAppliedV1] = []
        for bc in open_billing_cycles:
            account = (
                await session.exec(
                    select(dbmodel.Account).where(
                        dbmodel.Account.public_id == bc.account_public_id
                    )
                )
            ).first()
            if account is not None and account.balance > 0:
                transaction = dbmodel.Transaction(
                    billing_cycle=bc.id,
                    public_id=str(uuid.uuid4()),
                    account_id=account.public_id,
                    credit=0.0,
                    debit=account.balance,
                    type=FinTransactionApplied.v1.TransactionType.PAYMENT.value,
                    description=f"{FinTransactionApplied.v1.TransactionType.PAYMENT.value} for billing cycle {bc.start_date}-{bc.end_date}",
                )

                account.balance = 0
                session.add(transaction)
                session.add(account)

                msgs.append(
                    FinTransactionApplied.v1.FinTransactionAppliedV1(
                        id=str(uuid.uuid4()),
                        time=datetime.now(),
                        data=FinTransactionApplied.v1.Data(
                            account_public_id=bc.account_public_id,
                            type=FinTransactionApplied.v1.TransactionType.PAYMENT.value,
                            description=f"{FinTransactionApplied.v1.TransactionType.PAYMENT.value} for billing cycle {bc.start_date}-{bc.end_date}",
                            amount=account.balance,
                        ),
                    )
                )

            bc.status = "closed"
            session.add(bc)
            session.add(
                dbmodel.BillingCycle(
                    start_date=new_billing_cycle_start,
                    end_date=new_billing_cycle_end,
                    account_public_id=bc.account_public_id,
                )
            )
        await session.commit()

        for msg in msgs:
            await broker.publish(
                msg.model_dump_json().encode(),
                f"transactions.{msg.name.value}.{msg.version.value}",
                stream=jstream.name,
            )
