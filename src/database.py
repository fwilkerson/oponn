import os
import asyncio
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
    AsyncSession,
)

DATABASE_URL = os.getenv("DATABASE_URL")

# Cache engines and sessionmakers by event loop to avoid cross-loop contamination
_engines: dict[asyncio.AbstractEventLoop, AsyncEngine] = {}
_session_factories: dict[
    asyncio.AbstractEventLoop, async_sessionmaker[AsyncSession]
] = {}


def get_engine() -> AsyncEngine:
    loop = asyncio.get_running_loop()
    if loop not in _engines:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set")
        _engines[loop] = create_async_engine(DATABASE_URL)
    return _engines[loop]


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    loop = asyncio.get_running_loop()
    if loop not in _session_factories:
        _session_factories[loop] = async_sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine(), expire_on_commit=False
        )
    return _session_factories[loop]
