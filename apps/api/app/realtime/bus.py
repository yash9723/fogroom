"""Redis pub/sub fan-out of room events across API worker processes."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.redis import get_redis

logger = logging.getLogger("fogroom.bus")

CHANNEL_PREFIX = "room:"

Handler = Callable[[str, dict[str, Any]], Awaitable[None]]


async def publish_events(events: list[dict[str, Any]]) -> None:
    redis = get_redis()
    async with redis.pipeline(transaction=False) as pipe:
        for event in events:
            pipe.publish(f"{CHANNEL_PREFIX}{event['room_id']}", json.dumps(event, default=str))
        await pipe.execute()


async def subscribe_forever(handler: Handler, stop: asyncio.Event) -> None:
    """Listen on room:* and hand every event to `handler(room_id, event)`.

    Reconnects with backoff if Redis goes away; clients resync from PostgreSQL.
    """
    backoff = 1.0
    while not stop.is_set():
        pubsub = get_redis().pubsub()
        try:
            await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
            backoff = 1.0
            while not stop.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                channel = str(message.get("channel", ""))
                room_id = channel.removeprefix(CHANNEL_PREFIX)
                try:
                    event = json.loads(message["data"])
                except (TypeError, ValueError):
                    continue
                await handler(room_id, event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis subscriber error; retrying in %.0fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 15.0)
        finally:
            try:
                await pubsub.aclose()
            except Exception:
                logger.debug("pubsub close failed", exc_info=True)
