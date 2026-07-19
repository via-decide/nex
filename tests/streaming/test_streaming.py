import asyncio
from core.events.event_store import EventStore
from api.streaming import sse_events

def test_sse_resume():
    async def run():
        es=EventStore(); es.append('r','RUN_CREATED'); es.append('r','RUN_COMPLETED')
        chunks=[]
        async for c in sse_events(es,'r',1): chunks.append(c)
        assert 'RUN_COMPLETED' in ''.join(chunks)
    asyncio.run(run())
