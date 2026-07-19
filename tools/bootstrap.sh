#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt pytest==8.2.2 ruff==0.5.0 mypy==1.10.1 jsonschema==4.22.0 beautifulsoup4==4.12.3 pypdf==4.2.0
if [ -d frontend ]; then (cd frontend && npm ci); fi
