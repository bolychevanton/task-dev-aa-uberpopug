# regular FastStream code
from faststream.nats import NatsBroker, JStream
from accounting.config import nats_url
from accounting.eventschema.accounting import EndOfDayHappened
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_faststream import BrokerWrapper, StreamScheduler
from uuid import uuid4
from datetime import datetime

broker = NatsBroker(nats_url)

jstream = JStream(name="accounting", subjects=["cron.>", "transactions.>"])


# wrap FastStream object
taskiq_broker = BrokerWrapper(broker)


async def end_of_day():
    return EndOfDayHappened.v1.EndOfDayHappenedV1(
        id=str(uuid4()),
        time=datetime.now(),
    )


# create periodic task
taskiq_broker.task(
    message=end_of_day,
    # If you are using RabbitBroker, then you need to replace subject with queue.
    # If you are using KafkaBroker, then you need to replace subject with topic.
    subject=f"cron.{EndOfDayHappened.v1.Name.ENDOFDAYHAPPENED.value}.{EndOfDayHappened.v1.Version.V1.value}",
    schedule=[
        {
            "cron": "*/1 * * * *",
        }
    ],
    stream=jstream.name,
)

# create scheduler object
scheduler = StreamScheduler(
    broker=taskiq_broker,
    sources=[LabelScheduleSource(taskiq_broker)],
)

# @app.task(daily.after("23:50"), execution="async")
# async def close_billing_cycles(broker: NatsBroker = Arg("broker")):
#     tommorow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
#     new_billing_cycle_start = datetime.combine(tommorow, datetime.min.time())
#     new_billing_cycle_end = datetime.combine(tommorow, datetime.max.time())
#     async with AsyncSession(engine, expire_on_commit=False) as session:
#         open_billing_cycles = await session.exec(
#             select(dbmodel.BillingCycle).where(dbmodel.BillingCycle.status == "active")
#         )
#         msgs: list[FinTransactionApplied.v1.FinTransactionAppliedV1] = []
#         for bc in open_billing_cycles:
#             account = (
#                 await session.exec(
#                     select(dbmodel.Account).where(
#                         dbmodel.Account.public_id == bc.account_public_id
#                     )
#                 )
#             ).first()
#             if account is not None and account.balance > 0:
#                 transaction = dbmodel.Transaction(
#                     billing_cycle=bc.id,
#                     public_id=str(uuid.uuid4()),
#                     account_id=account.public_id,
#                     credit=0.0,
#                     debit=account.balance,
#                     type=FinTransactionApplied.v1.TransactionType.PAYMENT.value,
#                     description=f"{FinTransactionApplied.v1.TransactionType.PAYMENT.value} for billing cycle {bc.start_date}-{bc.end_date}",
#                 )

#                 account.balance = 0
#                 session.add(transaction)
#                 session.add(account)

#                 msgs.append(
#                     FinTransactionApplied.v1.FinTransactionAppliedV1(
#                         id=str(uuid.uuid4()),
#                         time=datetime.now(),
#                         data=FinTransactionApplied.v1.Data(
#                             account_public_id=bc.account_public_id,
#                             type=FinTransactionApplied.v1.TransactionType.PAYMENT.value,
#                             description=f"{FinTransactionApplied.v1.TransactionType.PAYMENT.value} for billing cycle {bc.start_date}-{bc.end_date}",
#                             amount=account.balance,
#                         ),
#                     )
#                 )

#             bc.start_date = new_billing_cycle_start
#             bc.end_date = new_billing_cycle_end
#             bc.status = "closed"
#             session.add(bc)

#         await session.commit()

#         for msg in msgs:
#             await broker.publish(
#                 msg.model_dump_json().encode(),
#                 f"transactions.{msg.name.value}.{msg.version.value}",
#                 stream=jstream.name,
#             )


# if __name__ == "__main__":
#     asyncio.run(start_app())
