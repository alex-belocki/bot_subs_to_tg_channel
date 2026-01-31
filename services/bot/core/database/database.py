import asyncio

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    async_scoped_session,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase

from core.constants.config import settings


engine = create_async_engine(settings.DATABASE_URL)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def scoped_session():
    """Используется в тасках celery"""
    scoped_factory = async_scoped_session(
        async_session_maker,
        scopefunc=asyncio.current_task,
    )
    try:
        async with scoped_factory() as s:
            yield s
    finally:
        await scoped_factory.remove()
