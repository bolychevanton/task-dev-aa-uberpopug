from faststream import FastStream, Logger
from faststream.nats import JStream, NatsBroker
from faststream.nats.producer import NatsJSFastProducer
import orjson
from faststream.nats.helpers import stream_builder

broker = NatsBroker()
app = FastStream(broker)

stream = JStream(name="stream", subjects=["js-subject"])


# @broker.subscriber(
#     "js-subject",
#     # stream=stream,
#     deliver_policy="all",
# )
# async def handler(msg: str):
#     print(msg)


@app.after_startup
async def test_publish():
    await broker.stream.add_stream(config=stream.config)
    await broker.publish("hello world", "js-subject", stream=stream.name)
    # publish with stream verification


# from faststream import FastStream
# from faststream.exceptions import AckMessage
# from faststream.nats import NatsBroker

# broker = NatsBroker("nats://localhost:4222")
# app = FastStream(broker)


# @broker.subscriber("test-subject")
# async def handle(body):
#     raise AckMessage()


# @app.after_startup
# async def test_publishing():
#     await broker.publish("Hello!", "test-subject")
