from __future__ import annotations
import ipaddress, socket
from dataclasses import dataclass, field
from urllib.parse import urlparse
import httpx

BLOCKED=["is_private","is_loopback","is_link_local","is_multicast","is_reserved","is_unspecified"]
@dataclass
class FetchRecord:
    final_url:str; redirect_chain:list[str]; resolved_addresses:list[str]; content_type:str; byte_length:int
@dataclass
class NetworkPolicy:
    allowed_ports:set[int]=field(default_factory=lambda:{80,443})
    allowed_content_types:set[str]=field(default_factory=lambda:{"text/html","application/xhtml+xml","application/json","application/xml","application/atom+xml","text/plain","text/markdown","application/pdf"})
    max_bytes:int=5_000_000; domain_allowlist:set[str]|None=None

def validate_url(url:str, policy:NetworkPolicy=NetworkPolicy())->list[str]:
    p=urlparse(url)
    if p.scheme not in {"http","https"}: raise ValueError("Only HTTP(S) URLs are allowed")
    if p.username or p.password: raise ValueError("URL credentials are forbidden")
    port=p.port or (443 if p.scheme=="https" else 80)
    if port not in policy.allowed_ports: raise ValueError("Port is not allowlisted")
    host=p.hostname or ""
    if policy.domain_allowlist and host not in policy.domain_allowlist: raise ValueError("Domain not allowlisted")
    infos=socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addrs=sorted({i[4][0] for i in infos})
    for a in addrs:
        ip=ipaddress.ip_address(a)
        if any(getattr(ip, attr) for attr in BLOCKED) or ip in ipaddress.ip_network("100.64.0.0/10"):
            raise ValueError(f"Blocked network address: {a}")
    return addrs

async def safe_fetch(url:str, policy:NetworkPolicy=NetworkPolicy())->tuple[bytes,FetchRecord]:
    chain=[]; current=url; resolved=[]
    async with httpx.AsyncClient(follow_redirects=False, timeout=httpx.Timeout(10,connect=3,read=5)) as client:
        for _ in range(6):
            resolved += validate_url(current, policy); r=await client.get(current); chain.append(str(r.url))
            if r.is_redirect and "location" in r.headers: current=str(r.url.join(r.headers["location"])); continue
            ctype=r.headers.get("content-type","").split(";")[0]
            if ctype not in policy.allowed_content_types: raise ValueError("Content type rejected")
            data=r.content
            if len(data)>policy.max_bytes: raise ValueError("Response too large")
            return data, FetchRecord(str(r.url),chain,resolved,ctype,len(data))
    raise ValueError("Too many redirects")
