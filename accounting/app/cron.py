# regular FastStream code
from faststream.nats import NatsBroker, JStream
from accounting.config import nats_url
from accounting.eventschema.accounting import EndOfDayHappened
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_faststream import BrokerWrapper, StreamScheduler
from uuid import uuid4
from datetime import datetime

broker = NatsBroker(nats_url)
jstream = JStream(name="accounting", subjects=["cron-streams.>", "transactions.>"])
taskiq_broker = BrokerWrapper(broker)


async def end_of_day():
    return EndOfDayHappened.v1.EndOfDayHappenedV1(
        id=str(uuid4()),
        time=datetime.now(),
    )


# send message every day at 23:50
taskiq_broker.task(
    message=end_of_day,
    subject=f"cron-streams.{EndOfDayHappened.v1.Name.ENDOFDAYHAPPENED.value}.{EndOfDayHappened.v1.Version.V1.value}",
    schedule=[
        {
            "cron": "50 23 * * *",
        }
    ],
    stream=jstream.name,
)

scheduler = StreamScheduler(
    broker=taskiq_broker,
    sources=[LabelScheduleSource(taskiq_broker)],
)
