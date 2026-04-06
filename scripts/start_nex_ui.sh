#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${HOME}/nex/logs/ui"
BACKEND_LOG="${LOG_DIR}/backend_startup.log"
FRONTEND_LOG="${LOG_DIR}/frontend_startup.log"
PORT_LOG="${LOG_DIR}/port_conflicts.log"
ERROR_LOG="${LOG_DIR}/dependency_errors.log"

mkdir -p "${LOG_DIR}"

check_and_clear_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti :"${port}" || true)"
    if [[ -n "${pids}" ]]; then
      echo "$(date -Is) port ${port} occupied by PID(s): ${pids}" | tee -a "${PORT_LOG}"
      kill -9 ${pids} || true
    fi
  elif command -v ss >/dev/null 2>&1; then
    local pids
    pids="$(ss -ltnp 2>/dev/null | awk -v p=":${port}" '$4 ~ p {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | tr '\n' ' ')"
    if [[ -n "${pids// }" ]]; then
      echo "$(date -Is) port ${port} occupied by PID(s): ${pids}" | tee -a "${PORT_LOG}"
      kill -9 ${pids} || true
    fi
  else
    echo "$(date -Is) unable to check port ${port}: neither lsof nor ss available" | tee -a "${PORT_LOG}"
  fi
}

check_and_clear_port 8000
check_and_clear_port 5173

echo "Starting Nex Backend..."
(
  cd "${ROOT_DIR}/ui/backend_api"
  uvicorn server:app --reload --port 8000
) >>"${BACKEND_LOG}" 2>>"${ERROR_LOG}" &

sleep 2

echo "Starting Nex Frontend..."
cd "${ROOT_DIR}/ui/frontend"
npm run dev >>"${FRONTEND_LOG}" 2>>"${ERROR_LOG}"
