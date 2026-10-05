"""Shared async Redis client (presence, pub/sub, engine locks, rate limits)."""

from redis.asyncio import Redis

from app.core.config import settings


class RedisState:
    client: Redis | None = None

    def init(self, url: str | None = None) -> Redis:
        self.client = Redis.from_url(url or settings.redis_url, decode_responses=True)
        return self.client

    def get(self) -> Redis:
        if self.client is None:
            return self.init()
        return self.client

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None


redis_state = RedisState()


def get_redis() -> Redis:
    return redis_state.get()
