import json, subprocess, sys

def test_benchmark_runs():
    out=subprocess.check_output([sys.executable,'tools/run_verification_benchmark.py','benchmarks/verification'])
    assert json.loads(out)['false_verification_rate']==0.0
