from __future__ import annotations
import hashlib, json, uuid
from dataclasses import dataclass
from datetime import datetime, timezone
EVENT_TYPES={'RUN_CREATED','RUN_QUEUED','STAGE_STARTED','SOURCE_DISCOVERED','SOURCE_FETCHED','SOURCE_FAILED','EVIDENCE_EXTRACTED','CLAIM_VERIFIED','REVIEW_REQUIRED','STAGE_COMPLETED','RUN_CANCELLED','RUN_FAILED','RUN_COMPLETED'}
class EventStore:
    def __init__(self): self.events=[]
    def append(self, run_id, event_type, actor='system', payload=None):
        if event_type not in EVENT_TYPES: raise ValueError('bad event')
        prev=self.events[-1]['event_hash'] if self.events else '0'*64; seq=sum(1 for e in self.events if e['run_id']==run_id)+1
        body={'event_id':str(uuid.uuid4()),'run_id':run_id,'sequence':seq,'event_type':event_type,'actor':actor,'payload':payload or {},'previous_event_hash':prev,'created_at':datetime.now(timezone.utc).isoformat()}
        body['event_hash']=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest(); self.events.append(body); return body
    def list(self, run_id, after=0): return [e for e in self.events if e['run_id']==run_id and e['sequence']>after]
    def update(self,*a,**k): raise RuntimeError('append-only events cannot be updated')
    def delete(self,*a,**k): raise RuntimeError('append-only events cannot be deleted')
