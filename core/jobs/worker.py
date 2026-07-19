from datetime import datetime, timezone
class Worker:
    def __init__(self, queue, event_store, owner='worker'): self.queue=queue; self.event_store=event_store; self.owner=owner
    def run_once(self):
        j=self.queue.acquire(self.owner)
        if not j: return None
        if j.idempotency_key in self.queue.effects: j.status='COMPLETED'; return j
        j.status='RUNNING'; self.event_store.append(j.run_id,'STAGE_STARTED',self.owner,{'stage':j.stage})
        self.queue.effects.add(j.idempotency_key); j.status='COMPLETED'; j.completed_at=datetime.now(timezone.utc); self.event_store.append(j.run_id,'STAGE_COMPLETED',self.owner,{'stage':j.stage}); return j
