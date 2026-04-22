from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator

from redis.asyncio import Redis
from trainops_domain.schemas import RunEvent

from trainops_common.settings import get_settings


class EventBus:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or get_settings().redis_url
        self._queues: dict[str, set[asyncio.Queue[str]]] = defaultdict(set)

    @staticmethod
    def channel(run_id: str) -> str:
        return f"trainops:run:{run_id}:events"

    async def publish(self, event: RunEvent) -> None:
        payload = event.model_dump_json()
        channel = self.channel(str(event.run_id))
        for queue in list(self._queues[channel]):
            queue.put_nowait(payload)
        try:
            redis = Redis.from_url(self.redis_url, decode_responses=True)
            await redis.publish(channel, payload)
            await redis.aclose()
        except Exception:
            # In-memory listeners still receive events in local smoke tests.
            return

    async def subscribe(self, run_id: str) -> AsyncIterator[str]:
        channel = self.channel(run_id)
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        self._queues[channel].add(queue)
        redis: Redis | None = None
        pubsub = None
        try:
            try:
                redis = Redis.from_url(self.redis_url, decode_responses=True)
                pubsub = redis.pubsub()
                await pubsub.subscribe(channel)
            except Exception:
                pubsub = None
            while True:
                if pubsub is not None:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
                    if message and message.get("data"):
                        yield str(message["data"])
                        continue
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    yield json.dumps({"type": "heartbeat", "message": "alive"})
        finally:
            self._queues[channel].discard(queue)
            if pubsub is not None:
                await pubsub.unsubscribe(channel)
            if redis is not None:
                await redis.aclose()


event_bus = EventBus()
