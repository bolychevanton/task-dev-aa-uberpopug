from auth import dbmodel as auth_dbmodel
from tasktracker import dbmodel as tt_dbmodel
from accounting import dbmodel as acc_dbmodel
from auth.config import db_url as auth_db_url
from tasktracker.config import db_url as tt_db_url
from accounting.config import db_url as acc_db_url
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio.engine import create_async_engine
import asyncio


async def drop_all(dbmodel, db_url):
    async with create_async_engine(db_url).begin() as conn:
        await conn.run_sync(dbmodel.SQLModel.metadata.drop_all)


for dbmodel, db_url in zip(
    [auth_dbmodel, tt_dbmodel, acc_dbmodel], [auth_db_url, tt_db_url, acc_db_url]
):
    asyncio.run(drop_all(dbmodel, db_url))

    # dbmodel.SQLModel.metadata.create_all(create_engine(db_url))


import subprocess

for jstream in ["accounting", "tasktracker", "auth"]:
    subprocess.run(["nats", "stream", "rm", jstream, "-f"])
