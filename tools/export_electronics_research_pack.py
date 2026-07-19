#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from domain_packs.electronics.exporters.pack import build_pack
p=argparse.ArgumentParser(); p.add_argument('--fixture',required=True); p.add_argument('--output',required=True); a=p.parse_args()
fixture=json.loads((Path(a.fixture)/'pack_fixture.json').read_text())
pack=build_pack(fixture); out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(pack,sort_keys=True,indent=2)); print(out)
