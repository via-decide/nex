import asyncio
class EventPublisher:
    def __init__(self): self.queues=[]
    async def publish(self,event):
        for q in self.queues: await q.put(event)
    async def subscribe(self):
        q=asyncio.Queue(); self.queues.append(q); return q
