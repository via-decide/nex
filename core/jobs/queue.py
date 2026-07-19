from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib, json, uuid
@dataclass
class Job:
    job_id:str; run_id:str; stage:str; payload_hash:str; idempotency_key:str; attempt:int=0; maximum_attempts:int=3; available_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc)); lease_owner:str|None=None; lease_expires_at:datetime|None=None; heartbeat_at:datetime|None=None; status:str='QUEUED'; last_error:str|None=None; created_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc)); completed_at:datetime|None=None
class JobQueue:
    def __init__(self): self.jobs=[]; self.effects=set()
    def enqueue(self, run_id, stage, payload):
        ph=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(); j=Job(str(uuid.uuid4()),run_id,stage,ph,f'{run_id}:{stage}:{ph}'); self.jobs.append(j); return j
    def acquire(self, owner, lease_seconds=30):
        now=datetime.now(timezone.utc)
        for j in self.jobs:
            if j.status in {'QUEUED','WAITING_RETRY'} and j.available_at<=now:
                j.status='LEASED'; j.lease_owner=owner; j.lease_expires_at=now+timedelta(seconds=lease_seconds); j.heartbeat_at=now; return j
        return None
