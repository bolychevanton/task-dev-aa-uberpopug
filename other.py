from faststream import FastStream, Logger
from faststream.nats import JStream, NatsBroker
from faststream.nats.producer import NatsJSFastProducer
import orjson

broker = NatsBroker()
app = FastStream(broker)


@broker.subscriber(
    "js-subject",
    stream="stream",
    deliver_policy="last",
)
async def handler(msg: str):
    print(msg, msg)
