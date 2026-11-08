from __future__ import annotations

import math
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api_adapter.schemas import AssistantRequest, AssistantResponse, ScenarioRequest
from api_adapter.service import AccountNotFoundError, AdapterAccountService

ROOT = Path(__file__).resolve().parents[1]

# Load GEMINI_API_KEY / GEMINI_MODEL from the project's .env (never committed).
for env_file in (ROOT / ".env", ROOT / "api_adapter" / ".env"):
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not line.lstrip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

service = AdapterAccountService(ROOT / "data" / "parquet")

app = FastAPI(title="Horizon API adapter", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000", "http://127.0.0.1:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def account_call(callback):
    try:
        return _clean_json_values(callback())
    except AccountNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _clean_json_values(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _clean_json_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_json_values(item) for item in value]
    return value


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "gemini": bool(os.environ.get("GEMINI_API_KEY"))}


@app.get("/accounts/{account_id}/home")
def home(account_id: int):
    return account_call(lambda: service.home(account_id))


@app.get("/accounts/{account_id}/calendar")
def calendar(account_id: int):
    return account_call(lambda: service.calendar(account_id))


@app.get("/accounts/{account_id}/budgets")
def budgets(account_id: int):
    return account_call(lambda: service.budgets(account_id))


@app.post("/accounts/{account_id}/scenarios/run")
def scenario(account_id: int, request: ScenarioRequest):
    return account_call(lambda: service.scenario(
        account_id,
        [{"name": shock.name, "value": shock.value} for shock in request.shocks],
    ))


@app.post("/accounts/{account_id}/assistant", response_model=AssistantResponse)
def assistant(account_id: int, request: AssistantRequest):
    return account_call(lambda: service.assistant(account_id, request.prompt))


# Heena's own API (/api/health, /api/accounts/{id}/forecast, /api/accounts/{id}/dashboard).
from app.api.main import app as heena_app  # noqa: E402  (backend/ is on sys.path via service.py)

for route in heena_app.router.routes:
    if getattr(route, "path", "").startswith("/api/"):
        app.router.routes.append(route)

# Serve the built v2 frontend (frontend/dist) from the same server, so one command runs everything.
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
