
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import redis.asyncio as redis

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class Base(DeclarativeBase):
    pass

async def get_async_session():
    async with SessionLocal() as session:
        yield session
