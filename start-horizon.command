#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "Creating Python environment - first run only..."
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q --disable-pip-version-check -r requirements.txt
PORT=8000
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then PORT=8001; fi
(sleep 8; open "http://127.0.0.1:$PORT") &
echo "Horizon is running at http://127.0.0.1:$PORT  (Control-C to stop)"
python -m uvicorn api_adapter.main:app --host 127.0.0.1 --port "$PORT"
