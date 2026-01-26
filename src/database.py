from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL) if DATABASE_URL else None
SessionLocal = (
    async_sessionmaker(
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
    )
    if engine
    else None
)
