"""Durable automation-event consumer. Human-approved events flow to Zapier."""
import asyncio, json, os
import aio_pika
import httpx

async def deliver(url: str, event: dict):
    if not url: return
    if not url.startswith("https://hooks.zapier.com/"):
        raise ValueError("Configure a Zapier Catch Hook HTTPS URL")
    async with httpx.AsyncClient(timeout=20) as client:
        response=await client.post(url,json=event); response.raise_for_status()

async def main():
    connection=await aio_pika.connect_robust(os.getenv("AMQP_URL","amqp://enterpriseai:enterpriseai@rabbitmq/"))
    async with connection:
        channel=await connection.channel(); await channel.set_qos(prefetch_count=8)
        queue=await channel.declare_queue("enterpriseai.events",durable=True)
        dead=await channel.declare_queue("enterpriseai.events.dead",durable=True)
        async with queue.iterator() as messages:
            async for message in messages:
                try:
                    event=json.loads(message.body)
                    await deliver(os.getenv("ZAPIER_WEBHOOK_URL", ""),event)
                    await message.ack()
                except Exception as exc:
                    retry=int((message.headers or {}).get("x-retries",0))
                    headers={**(message.headers or {}),"x-retries":retry+1,"last-error":str(exc)[:300]}
                    target=dead if retry>=5 else queue
                    await asyncio.sleep(min(2**retry,30))
                    await channel.default_exchange.publish(aio_pika.Message(message.body,headers=headers,delivery_mode=aio_pika.DeliveryMode.PERSISTENT),routing_key=target.name)
                    await message.ack()

if __name__=="__main__": asyncio.run(main())
