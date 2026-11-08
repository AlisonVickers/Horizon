# Horizon: Resilience Rewired (Tangerine, Sheridan Datathon 2026)

**Frontend:** Alison's v2 (React + Vite), in `frontend/`.
**Backend:** Heena's engine, in `backend/`: income and expense detection, cash-flow forecast, projected balance, low-balance alerts, runway, and her own `/api` endpoints.
**API adapter:** `api_adapter/` connects the two. It's a FastAPI server that calls Heena's services and also serves the built frontend.

## Run it (Windows)
1. Put your Gemini key in `.env` (copy `.env.example`). It's optional; Astro falls back to engine-only answers.
2. Double-click `start-horizon.cmd`. Python 3.11+ is the only requirement.
3. The app opens at http://127.0.0.1:8000. Type any `account_id` in the top-right box to switch customers.

## Data
`data/parquet/` holds the tables the engine reads. `data/raw/data/` holds the source CSVs, which is the layout Heena's backend expects. `transactions.csv` (102 MB) is left out because GitHub limits files to 100 MB; everything runs from `data/parquet/transactions.parquet`.

## API
| Method | Path | What it returns |
|---|---|---|
| GET | /health | `{status, gemini}` |
| GET | /accounts/{id}/home | Profile (I, F, S, B, H, P), payday, upcoming bills, safety-net goal, peer benchmarks |
| GET | /accounts/{id}/calendar | 12 months of activity, forecast bills and payday, monthly totals, last 7 days |
| GET | /accounts/{id}/budgets | Latest month's categories, plus Astro budget plans |
| POST | /accounts/{id}/scenarios/run | `{shocks:[{name,value}]}` returns runway (the judge formula, capped at 120) |
| GET | /api/health | Heena's API health check |
| GET | /api/accounts/{id}/forecast?start_date=&end_date= | Heena's forecast of recurring income and expense events |
| GET | /api/accounts/{id}/dashboard?start_date=&end_date=&safety_buffer= | Heena's projected balance and low-balance alerts (powers the Balance outlook card) |
| POST | /accounts/{id}/assistant | `{prompt}` returns Astro's answer (engine numbers, explained by Gemini) |

Astro can answer questions about income, spending, bills and budgets, and estimate
the impact of a purchase with a stated price. If the price is missing, it asks
you to submit the question again with the amount. Forecast dates such as "next
month" are relative to the latest transaction date in the dataset, not the
computer's current date; "next month" assumes its first day. Purchase projections
use detected recurring income and expenses, exclude variable spending, and do
not establish affordability. Gemini is optional; when unavailable, Astro uses
the engine's supported answers and explicitly says when it cannot answer.
The response's `data.gemini_status` and `tool_trace` show which steps were used.

Shock names: `job_loss_ei` (EI income share as a percentage), `rent_up_pct` (household bills increase percentage), `pay_cut_pct` (income reduction percentage), `one_off_costs`, `new_car_payment`, `loan_payment_reduction`, `everyday_cut_pct`.

## Developing the frontend
`cd frontend && npm install && npm run dev` starts it at http://127.0.0.1:5173. It talks to the API on port 8000; set this in `frontend/.env` with `VITE_API_BASE_URL=http://127.0.0.1:8000`.
Run `npm run build` to update `frontend/dist`, which the server serves.

## Tests
`cd backend && python -m pytest tests` runs Heena's engine tests (51).
