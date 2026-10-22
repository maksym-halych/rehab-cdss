import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from api.db import SCHEMA, Base, create_engine
from api.settings import database_url

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set. See api/.env.example")
    engine = create_engine(url)
    async with engine.connect() as connection:
        # The version table lives in our schema, so the schema must exist first
        await connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await connection.commit()
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline (--sql) mode is not supported")
asyncio.run(_run_async())
