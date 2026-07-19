from __future__ import annotations
import csv, io, json, math, statistics
from dataclasses import dataclass
from typing import Any, Callable
from core.auth import Role, Principal, require_role
from core.security.request_controls import reject_executable_payload

@dataclass(frozen=True)
class ToolSpec:
    tool_id:str; input_schema:dict[str,Any]; output_schema:dict[str,Any]; maximum_runtime_seconds:int; maximum_input_bytes:int; maximum_output_bytes:int; network_policy:str; filesystem_policy:str; required_role:Role; audit_category:str; handler:Callable[[dict[str,Any]],dict[str,Any]]

def _calc(p):
    expr=str(p.get("expression",""))
    if not all(c in "0123456789+-*/(). %" for c in expr): raise ValueError("calculator accepts arithmetic only")
    return {"result": eval(expr, {"__builtins__":{}}, {})}
def _stats(p):
    nums=[float(x) for x in p.get("values",[])]; return {"count":len(nums),"mean":statistics.mean(nums) if nums else None,"min":min(nums) if nums else None,"max":max(nums) if nums else None}
def _csv(p):
    rows=list(csv.DictReader(io.StringIO(str(p.get("csv",""))))); return {"rows":len(rows),"columns":list(rows[0].keys()) if rows else []}
def _json(p): json.loads(str(p.get("json",""))); return {"valid":True}
def _citation(p): return {"citations":[u for u in p.get("urls",[]) if isinstance(u,str) and u.startswith(("http://","https://"))]}
def _repo(p):
    path=str(p.get("path","README.md"))
    if path.startswith("/") or ".." in path: raise ValueError("path denied")
    with open(path,"r",encoding="utf-8",errors="replace") as f: return {"text":f.read(20000)}
def _transform(p): return {"normalized": str(p.get("text","")).strip().lower()}

def _spec(t,h,role=Role.RESEARCHER): return ToolSpec(t,{"type":"object"},{"type":"object"},5,100000,100000,"none","deny_except_repo_read",role,"tool_execution",h)
REGISTRY={s.tool_id:s for s in [_spec("calculator",_calc),_spec("statistics_summary",_stats),_spec("csv_profile",_csv),_spec("json_validation",_json),_spec("citation_check",_citation),_spec("repository_read",_repo,Role.READER),_spec("fixed_research_transform",_transform)]}

def execute_tool(tool_id:str, parameters:dict[str,Any], principal:Principal)->dict[str,Any]:
    if tool_id not in REGISTRY: raise ValueError("Tool is not registered")
    spec=REGISTRY[tool_id]; require_role(principal,spec.required_role); reject_executable_payload(parameters)
    if len(json.dumps(parameters).encode())>spec.maximum_input_bytes: raise ValueError("Tool input too large")
    out=spec.handler(parameters)
    if len(json.dumps(out).encode())>spec.maximum_output_bytes: raise ValueError("Tool output too large")
    return out
