import asyncio, json
async def sse_events(event_store, run_id, last_event_id=0):
    sent=int(last_event_id or 0)
    while True:
        events=event_store.list(run_id, sent)
        for e in events:
            sent=e['sequence']; yield f"id: {sent}\nevent: {e['event_type']}\ndata: {json.dumps(e,sort_keys=True)}\n\n"
        if events and events[-1]['event_type'] in {'RUN_COMPLETED','RUN_FAILED','RUN_CANCELLED'}: break
        yield ": heartbeat\n\n"; await asyncio.sleep(0.01)
