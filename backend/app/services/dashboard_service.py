
from datetime import date, timedelta

import pandas as pd

from app.data.account_store import AccountStore
from app.services.income_detector import IncomeDetector
from app.services.expense_detector import ExpenseDetector
from app.services.cashflow_forecast import CashflowForecastService
from app.services.projected_balance import ProjectedBalanceService
from app.services.low_balance_alert import LowBalanceAlertService


class DashboardService:
    """Prepare financial dashboard data for one account."""

    def __init__(self):
        self.income_detector = IncomeDetector()
        self.expense_detector = ExpenseDetector()
        self.forecaster = CashflowForecastService()
        self.balance_projector = ProjectedBalanceService()
        self.alert_service = LowBalanceAlertService()

    def get_dashboard(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        safety_buffer: float = 500.00,
    ) -> dict:

        if end_date < start_date:
            raise ValueError("End date cannot precede start date")

        with AccountStore(account_id) as store:
            transactions = store.get_transactions()
            monthly_summary = store.get_monthly_summary()

        historical_balance = None
        balance_date = None

        if not monthly_summary.empty:
            valid = monthly_summary.dropna(
                subset=["month", "month_end_balance"]
            ).copy()

            if not valid.empty:
                valid = valid.sort_values("month")
                latest = valid.iloc[-1]

                historical_balance = round(
                    float(latest["month_end_balance"]), 2
                )

                balance_date = (
                    pd.Period(str(latest["month"]), freq="M")
                    .end_time.date().isoformat()
                )

        income_patterns = self.income_detector.detect(transactions)
        expense_patterns = self.expense_detector.detect(transactions)

        events = self.forecaster.forecast(
            income_patterns=income_patterns,
            expense_patterns=expense_patterns,
            start_date=start_date,
            end_date=end_date,
        )

        predicted_income = round(
            sum(e.amount for e in events if e.amount > 0), 2
        )

        predicted_expenses = round(
            -sum(e.amount for e in events if e.amount < 0), 2
        )

        projected_balance = None

        if historical_balance is not None and balance_date is not None:
            historical_date = date.fromisoformat(balance_date)

            if start_date == historical_date + timedelta(days=1):
                projected_balance = self.balance_projector.project(
                    starting_balance=historical_balance,
                    events=events,
                )

        balance_alerts = self.alert_service.analyze(
            projection=projected_balance,
            safety_buffer=safety_buffer,
        )

        return {
            "account_id": account_id,
            "forecast_type": "historical_pattern_simulation",
            "data_as_of": (
                pd.to_datetime(transactions["date"]).max()
                .date().isoformat()
                if not transactions.empty
                else None
            ),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "balance": {
                "historical_month_end_balance": historical_balance,
                "as_of": balance_date,
                "is_live": False,
            },
            "cashflow": {
                "predicted_recurring_income": predicted_income,
                "predicted_recurring_expenses": predicted_expenses,
                "event_count": len(events),
            },
            "projected_balance": projected_balance,
            "balance_alerts": balance_alerts,
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
