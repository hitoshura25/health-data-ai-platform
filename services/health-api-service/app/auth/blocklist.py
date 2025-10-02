import redis.asyncio as redis
from fastapi import Depends
from app.config import settings

class RedisBlocklist:
    def __init__(self, client: redis.Redis):
        self.client = client

    async def add(self, token: str, expires_in: int):
        await self.client.set(f"blocklist:{token}", "", ex=expires_in)

    async def contains(self, token: str) -> bool:
        return await self.client.exists(f"blocklist:{token}")

async def get_redis_client():
    return redis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_blocklist(client: redis.Redis = Depends(get_redis_client)) -> RedisBlocklist:
    return RedisBlocklist(client)