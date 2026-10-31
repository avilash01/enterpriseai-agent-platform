"""Redis Streams consumer with bounded retries and a durable dead-letter stream."""
from __future__ import annotations

import asyncio
import json
import os
import socket

import httpx
from redis.asyncio import Redis
from redis.exceptions import ResponseError

STREAM = os.getenv("REDIS_STREAM", "enterpriseai:events")
GROUP = os.getenv("REDIS_CONSUMER_GROUP", "zapier-delivery")
DEAD = os.getenv("REDIS_DEAD_STREAM", "enterpriseai:events:dead")
MAX_RETRIES = int(os.getenv("MAX_DELIVERY_RETRIES", "5"))


async def deliver(url: str, event: dict):
    if not url:
        raise RuntimeError("Zapier Catch Hook is not configured")
    if not url.startswith("https://hooks.zapier.com/hooks/catch/"):
        raise ValueError("Configure a valid Zapier Catch Hook HTTPS URL")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json=event)
        response.raise_for_status()


async def _process(redis: Redis, message_id: str, fields: dict[str, str]):
    try:
        event = json.loads(fields["payload"])
        await deliver(os.getenv("ZAPIER_WEBHOOK_URL", ""), event)
    except Exception as exc:
        attempts = int(fields.get("attempts", "0")) + 1
        payload = fields.get("payload", "{}")
        if attempts > MAX_RETRIES:
            await redis.xadd(DEAD, {"payload": payload, "attempts": str(attempts), "error": str(exc)[:300]})
        else:
            await asyncio.sleep(min(2 ** (attempts - 1), 30))
            await redis.xadd(STREAM, {"payload": payload, "attempts": str(attempts), "last_error": str(exc)[:300]})
    finally:
        await redis.xack(STREAM, GROUP, message_id)


async def main():
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    consumer = f"worker-{socket.gethostname()}"
    while True:
        try:
            await redis.ping()
            try:
                await redis.xgroup_create(STREAM, GROUP, id="0-0", mkstream=True)
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
            break
        except Exception:
            await asyncio.sleep(2)

    try:
        while True:
            try:
                # Recover deliveries left pending by a worker that exited mid-request.
                claimed = await redis.xautoclaim(STREAM, GROUP, consumer, min_idle_time=30000, start_id="0-0", count=8)
                messages = claimed[1] if len(claimed) > 1 else []
                if not messages:
                    batches = await redis.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=8, block=5000)
                    messages = batches[0][1] if batches else []
                for message_id, fields in messages:
                    await _process(redis, message_id, fields)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(2)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())

