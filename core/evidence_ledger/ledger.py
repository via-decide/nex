from __future__ import annotations
import hashlib, json, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

EVENT_TYPES={"SOURCE_DISCOVERED","SOURCE_FETCH_STARTED","SOURCE_FETCH_SUCCEEDED","SOURCE_FETCH_FAILED","SOURCE_PARSED","EXTRACTION_CREATED","CLAIM_CREATED","EVIDENCE_LINK_CREATED","REVIEW_RECORDED","CLAIM_SUPERSEDED"}
@dataclass(frozen=True)
class Claim: claim_id:str; text:str; version:int=1; supersedes_id:str|None=None
@dataclass(frozen=True)
class EvidenceLink:
    claim_id:str; source_artifact_sha256:str; page:int|None; section:str|None; start_offset:int; end_offset:int; support_type:str; supporting_text_sha256:str; extraction_model:str; extraction_prompt_version:str; review_status:str="UNREVIEWED"
class EvidenceLedger:
    def __init__(self): self.events=[]
    def append(self, event_type:str, payload:dict[str,Any])->dict[str,Any]:
        if event_type not in EVENT_TYPES: raise ValueError("invalid event")
        e={"event_id":str(uuid.uuid4()),"event_type":event_type,"payload":payload,"created_at":datetime.now(timezone.utc).isoformat(),"sequence":len(self.events)+1}
        self.events.append(e); return e
    def create_claim(self,text:str, supersedes_id:str|None=None)->Claim:
        c=Claim(str(uuid.uuid4()),text,1,supersedes_id); self.append("CLAIM_CREATED",asdict(c)); return c
    def link(self, claim:Claim, sha:str, text:str, start:int, end:int, page:int|None=None, section:str|None=None, support_type:str="DIRECT")->EvidenceLink:
        if start<0 or end<=start or end>len(text): raise ValueError("invalid offsets")
        link=EvidenceLink(claim.claim_id,sha,page,section,start,end,support_type,hashlib.sha256(text[start:end].encode()).hexdigest(),"deterministic-v1","v1")
        self.append("EVIDENCE_LINK_CREATED",asdict(link)); return link
    def coverage(self)->dict[str,int]:
        failed=sum(1 for e in self.events if e["event_type"]=="SOURCE_FETCH_FAILED"); claims=sum(1 for e in self.events if e["event_type"]=="CLAIM_CREATED"); links=sum(1 for e in self.events if e["event_type"]=="EVIDENCE_LINK_CREATED")
        return {"sources_failed":failed,"claims_extracted":claims,"claims_with_direct_evidence":links,"claims_without_evidence":max(0,claims-links)}
