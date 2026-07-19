import json, subprocess, sys
from pathlib import Path

def test_export_cli(tmp_path):
    out=tmp_path/'pack.json'; subprocess.check_call([sys.executable,'tools/export_electronics_research_pack.py','--fixture','domain_packs/electronics/fixtures/example_board','--output',str(out)])
    pack=json.loads(out.read_text()); assert pack['pack_sha256'] and pack['conflicts'] and pack['missing_facts'][0]['status']=='BLOCKED_SOURCE_REQUIRED'
