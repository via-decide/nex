from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable
import os, secrets
from fastapi import Header, HTTPException, Request

class Role(StrEnum):
    READER="READER"; RESEARCHER="RESEARCHER"; REVIEWER="REVIEWER"; ADMIN="ADMIN"

ROLE_ORDER={Role.READER:0,Role.RESEARCHER:1,Role.REVIEWER:2,Role.ADMIN:3}
@dataclass(frozen=True)
class Principal:
    subject: str
    roles: set[Role]
    object_grants: dict[str,set[str]]

def _dev_principal()->Principal:
    return Principal("local-user", {Role.ADMIN,Role.REVIEWER,Role.RESEARCHER,Role.READER}, {"*":{"*"}})

def authenticate(authorization: str|None=Header(default=None))->Principal:
    if os.getenv("NEX_LOCAL_DEV_AUTH_BYPASS","false").lower()=="true": return _dev_principal()
    token=os.getenv("NEX_DEV_TOKEN","change-me-local-token")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Authentication required")
    supplied=authorization.split(" ",1)[1]
    if not secrets.compare_digest(supplied, token):
        raise HTTPException(403,"Invalid credentials")
    return _dev_principal()

def require_role(p:Principal, role:Role)->None:
    if max(ROLE_ORDER[r] for r in p.roles) < ROLE_ORDER[role]:
        raise HTTPException(403,"Insufficient role")

def authorize_object(p:Principal, object_type:str, object_id:str, role:Role=Role.READER)->None:
    require_role(p, role)
    if "*" in p.object_grants and "*" in p.object_grants["*"]: return
    if object_id not in p.object_grants.get(object_type,set()):
        raise HTTPException(403,"Object access denied")
