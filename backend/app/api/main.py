
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query

from app.data.account_store import AccountStore
from app.services.income_detector import IncomeDetector
from app.services.expense_detector import ExpenseDetector
from app.services.cashflow_forecast import CashflowForecastService
from app.services.dashboard_service import DashboardService


app = FastAPI(
    title="Horizon API",
    version="0.1.0",
    description="Financial resilience backend for Horizon",
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app": "Horizon",
        "message": "Horizon API is running!",
    }


@app.get("/api/accounts/{account_id}/forecast")
def get_account_forecast(
    account_id: int,
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date = Query(default=date(2026, 1, 31)),
):
    if account_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Account ID must be positive",
        )

    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="End date cannot precede start date",
        )

    if (end_date - start_date) > timedelta(days=366):
        raise HTTPException(
            status_code=422,
            detail="Forecast cannot exceed 366 days",
        )

    try:
        with AccountStore(account_id) as store:
            transactions = store.get_transactions()

    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Account not found",
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Financial dataset unavailable",
        )

    income_patterns = IncomeDetector().detect(transactions)
    expense_patterns = ExpenseDetector().detect(transactions)

    events = CashflowForecastService().forecast(
        income_patterns=income_patterns,
        expense_patterns=expense_patterns,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "account_id": account_id,
        "forecast_type": "historical_pattern_simulation",
        "data_as_of": (
            str(transactions["date"].max())[:10]
            if not transactions.empty
            else None
        ),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "summary": {
            "predicted_income": round(
                sum(e.amount for e in events if e.amount > 0), 2
            ),
            "predicted_recurring_expenses": round(
                sum(abs(e.amount) for e in events if e.amount < 0), 2
            ),
        },
        "events": [
            {
                "date": event.date.isoformat(),
                "category": event.category,
                "amount": event.amount,
                "event_type": event.event_type,
            }
            for event in events
        ],
    }


@app.get("/api/accounts/{account_id}/dashboard")
def get_account_dashboard(
    account_id: int,
    start_date: date = Query(default=date(2026, 1, 1)),
    end_date: date = Query(default=date(2026, 1, 31)),
    safety_buffer: float = Query(
        default=500.0,
        ge=0,
        le=1_000_000,
        allow_inf_nan=False,
    ),
):
    if account_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Account ID must be positive",
        )

    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="End date cannot precede start date",
        )

    if (end_date - start_date) > timedelta(days=366):
        raise HTTPException(
            status_code=422,
            detail="Dashboard period cannot exceed 366 days",
        )

    try:
        return DashboardService().get_dashboard(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            safety_buffer=safety_buffer,
        )

    except ValueError as exc:
        if str(exc) == f"Account {account_id} does not exist":
            raise HTTPException(
                status_code=404,
                detail="Account not found",
            ) from exc
        raise

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Financial dataset unavailable",
        ) from exc
