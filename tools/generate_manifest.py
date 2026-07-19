#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser(); p.add_argument('--output',default='artifacts/build-manifest.json'); a=p.parse_args()
files=[]
for pat in ['pyproject.toml','uv.lock','requirements.txt','frontend/package-lock.json','Dockerfile','Makefile']:
    path=Path(pat)
    if path.exists(): files.append({'path':pat,'sha256':h(path)})
manifest={'validation_id':'nex_reproducible_manifest_v1','python_version':'3.11.*','node_version':'20.14.0','files':files}
out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(manifest,sort_keys=True,indent=2)); print(out)
