import nats
import asyncio

nats_url = "nats://localhost:4222"


async def create_streams():
    nc = await nats.connect(nats_url)
    js = nc.jetstream()
    await js.add_stream(name="main", subjects=["auth.>"])


asyncio.run(create_streams())
