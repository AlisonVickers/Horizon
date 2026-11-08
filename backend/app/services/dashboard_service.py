
from datetime import date, timedelta

import pandas as pd

from app.data.account_store import AccountStore
from app.services.income_detector import IncomeDetector
from app.services.expense_detector import ExpenseDetector
from app.services.cashflow_forecast import CashflowForecastService
from app.services.projected_balance import ProjectedBalanceService
from app.services.low_balance_alert import LowBalanceAlertService
from app.services.variable_spending import VariableSpendingEstimator
from app.services.safe_to_spend import SafeToSpendService
from app.services.smart_alert import SmartAlertService
from app.services.payday_spending import PaydaySpendingService


class DashboardService:
    """Prepare financial dashboard data for one account."""

    def __init__(self):
        self.income_detector = IncomeDetector()
        self.expense_detector = ExpenseDetector()
        self.forecaster = CashflowForecastService()
        self.balance_projector = ProjectedBalanceService()
        self.alert_service = LowBalanceAlertService()
        self.variable_spending = VariableSpendingEstimator()
        self.safe_to_spend_service = SafeToSpendService()
        self.smart_alert_service = SmartAlertService()
        self.payday_spending_service = PaydaySpendingService(
            safe_to_spend_service=self.safe_to_spend_service
        )
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

        # Estimate historical non-recurring cash withdrawals.
        variable_spending = self.variable_spending.estimate(
            transactions=transactions,
            as_of=start_date - timedelta(days=1),
            lookback_months=12,
        )

        # Prepare forecast events once for both scenarios.
        safe_events = [
            {
                "date": event.date.isoformat(),
                "amount": event.amount,
            }
            for event in events
        ]

        safe_to_spend = {
            "status": "unavailable",
            "safe_to_spend": None,
            "reason": "Cannot calculate a supported spending allowance",
        }

        conservative_safe_to_spend = {
            "status": "unavailable",
            "safe_to_spend": None,
            "reason": "Cannot calculate conservative allowance",
        }

        if (
            projected_balance is not None
            and historical_balance is not None
            and variable_spending["status"] == "estimated"
        ):
            # Typical scenario: median monthly cash withdrawals.
            safe_to_spend = self.safe_to_spend_service.calculate(
                starting_balance=historical_balance,
                events=safe_events,
                start_date=start_date,
                end_date=end_date,
                monthly_variable_outflow=variable_spending[
                    "monthly_estimate"
                ],
                safety_buffer=safety_buffer,
                variable_status=variable_spending["status"],
            )

            # Conservative scenario: 75th percentile withdrawals.
            conservative_safe_to_spend = (
                self.safe_to_spend_service.calculate(
                    starting_balance=historical_balance,
                    events=safe_events,
                    start_date=start_date,
                    end_date=end_date,
                    monthly_variable_outflow=variable_spending[
                        "conservative_monthly_estimate"
                    ],
                    safety_buffer=safety_buffer,
                    variable_status=variable_spending["status"],
                )
            )
            
        smart_alerts = {
            "status": "unavailable",
            "reason": "No anchored balance or supported spending estimate",
            "typical": None,
            "conservative": None,
        }

        if (
            projected_balance is not None
            and historical_balance is not None
            and variable_spending["status"] == "estimated"
        ):
            typical_alerts = self.smart_alert_service.analyze(
                starting_balance=historical_balance,
                events=safe_events,
                start_date=start_date,
                end_date=end_date,
                monthly_variable_outflow=variable_spending[
                    "monthly_estimate"
                ],
                safety_buffer=safety_buffer,
                scenario="typical",
            )

            conservative_alerts = self.smart_alert_service.analyze(
                starting_balance=historical_balance,
                events=safe_events,
                start_date=start_date,
                end_date=end_date,
                monthly_variable_outflow=variable_spending[
                    "conservative_monthly_estimate"
                ],
                safety_buffer=safety_buffer,
                scenario="conservative",
            )

            smart_alerts = {
                "status": "estimated",
                "typical": typical_alerts,
                "conservative": conservative_alerts,
            }

        
        payday_spending = {
            "status": "unavailable",
            "next_payday": None,
            "spendable_until_payday": None,
            "reason": "No anchored balance or supported spending estimate",
        }

        if (
            projected_balance is not None
            and historical_balance is not None
            and variable_spending["status"] == "estimated"
        ):
            payday_events = [
                {
                    "date": event.date.isoformat(),
                    "amount": event.amount,
                    "event_type": event.event_type,
                }
                for event in events
            ]

            payday_spending = self.payday_spending_service.calculate(
                starting_balance=historical_balance,
                events=payday_events,
                start_date=start_date,
                end_date=end_date,
                monthly_variable_outflow=variable_spending[
                    "conservative_monthly_estimate"
                ],
                safety_buffer=safety_buffer,
                variable_status=variable_spending["status"],
            )


        return {
            "account_id": account_id,
            "forecast_type": "historical_pattern_simulation",
            "data_as_of": (
                pd.to_datetime(transactions["date"])
                .max().date().isoformat()
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
            "variable_spending": variable_spending,
            "safe_to_spend": safe_to_spend,
            "conservative_safe_to_spend": conservative_safe_to_spend,
            "smart_alerts": smart_alerts,
            "payday_spending": payday_spending,
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
