import asyncio

from rocketry import Rocketry
from rocketry.args import Arg
from accounting.config import nats_url
from faststream.nats import NatsBroker, JStream
from rocketry.conds import daily
from datetime import datetime, date, timedelta

app = Rocketry(execution="async")

broker = NatsBroker(nats_url)
app.params(broker=broker)
jstream = JStream(name="accounting", subjects=["transactions.*"])


async def start_app():
    async with broker:
        await broker.stream.add_stream(config=jstream.config)
        await app.serve()


@app.task(daily.after("23:50"), execution="async")
async def close_billing_cycles(broker: NatsBroker = Arg("broker")):
    tommorow = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
    new_billing_cycle_start = datetime.combine(tommorow, datetime.min.time())
    new_billing_cycle_end = datetime.combine(tommorow, datetime.max.time())
    await broker.publish("Hi, Rocketry!", "test", stream=jstream.name)


if __name__ == "__main__":
    asyncio.run(start_app())
