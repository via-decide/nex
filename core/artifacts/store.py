from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class SourceArtifact:
    artifact_id:str; canonical_url:str; requested_url:str; redirect_chain:list[str]; retrieved_at_utc:str; http_status:int; content_type:str; byte_length:int; sha256:str; publisher:str|None=None; document_title:str|None=None; document_revision:str|None=None; publication_date:str|None=None; parser_id:str|None=None; parser_version:str|None=None; retrieval_policy_version:str="ssrf-safe-v1"

class ArtifactStore:
    def __init__(self, root: str|Path="artifacts/sources"):
        self.root=Path(root); self.root.mkdir(parents=True, exist_ok=True)
    def put(self, data:bytes, requested_url:str, content_type:str, **meta:Any)->SourceArtifact:
        sha=hashlib.sha256(data).hexdigest(); path=self.root/sha[:2]/sha; path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes()!=data: raise ValueError("hash collision or mutation detected")
        if not path.exists(): path.write_bytes(data)
        art=SourceArtifact(meta.get("artifact_id",sha), meta.get("canonical_url",requested_url), requested_url, meta.get("redirect_chain",[requested_url]), meta.get("retrieved_at_utc",datetime.now(timezone.utc).isoformat()), meta.get("http_status",200), content_type, len(data), sha, **{k:v for k,v in meta.items() if k in {"publisher","document_title","document_revision","publication_date","parser_id","parser_version","retrieval_policy_version"}})
        (path.with_suffix(".json")).write_text(json.dumps(asdict(art),sort_keys=True,indent=2))
        return art
    def verify(self, sha256:str)->bool:
        p=self.root/sha256[:2]/sha256
        return p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==sha256
