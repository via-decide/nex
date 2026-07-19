from __future__ import annotations
import json, os, re, time
from collections import defaultdict, deque
from typing import Any
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_CODE_PATTERNS=[r"\b(import|exec|eval|subprocess|os\.system|__import__)\b",r"#!\s*/bin/",r"\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b.+\bFROM\b",r"<script\b",r"\{\{.*\}\}",r"\$\([^)]*\)"]
_regex=[re.compile(p,re.I|re.S) for p in _CODE_PATTERNS]

def reject_executable_payload(value:Any)->None:
    text=json.dumps(value, sort_keys=True) if not isinstance(value,str) else value
    if any(r.search(text) for r in _regex):
        raise HTTPException(400,"Executable code payloads are not accepted")

def audit_event(category:str, **fields:Any)->dict[str,Any]:
    clean={k:("[REDACTED]" if "token" in k.lower() or "authorization" in k.lower() else v) for k,v in fields.items()}
    return {"category":category,"ts":time.time(),**clean}

class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_bytes:int=1_000_000, rate:int=120, window:int=60):
        super().__init__(app); self.max=max_body_bytes; self.rate=rate; self.window=window; self.hits=defaultdict(deque)
    async def dispatch(self, request:Request, call_next):
        origin=request.headers.get("origin")
        allowed=[o.strip() for o in os.getenv("NEX_ALLOWED_ORIGINS","http://127.0.0.1:3000,http://localhost:3000").split(",") if o.strip()]
        if origin and origin not in allowed and os.getenv("NEX_ENV","development") == "production":
            return JSONResponse({"detail":"Origin rejected"}, status_code=403)
        ip=request.client.host if request.client else "unknown"; now=time.time(); q=self.hits[ip]
        while q and now-q[0]>self.window: q.popleft()
        if len(q)>=self.rate: return JSONResponse({"detail":"Rate limit exceeded"}, status_code=429)
        q.append(now)
        if int(request.headers.get("content-length") or 0)>self.max:
            return JSONResponse({"detail":"Request too large"}, status_code=413)
        return await call_next(request)
