
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.services.dashboard_service import DashboardService


class MultiMonthForecastService:
    """Build monthly cashflow summaries from one continuous forecast."""

    def __init__(self):
        self.dashboard = DashboardService()

    @staticmethod
    def _money(value):
        return Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def forecast(
        self,
        account_id: int,
        start_date: date,
        end_date: date,
        safety_buffer: float = 500.0,
    ) -> dict:

        if end_date < start_date:
            raise ValueError("End date cannot precede start date")

        dashboard = self.dashboard.get_dashboard(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            safety_buffer=safety_buffer,
        )

        starting_balance = dashboard["balance"][
            "historical_month_end_balance"
        ]

        # Never fabricate a balance when the historical
        # balance cannot anchor the requested forecast.
        if dashboard["projected_balance"] is None:
            return {
                "status": "unavailable",
                "reason": "Forecast must start immediately after the historical balance",
                "months": [],
            }

        balance = self._money(starting_balance)

        events = dashboard["events"]
        months = {}

        for event in events:
            month = event["date"][:7]

            if month not in months:
                months[month] = {
                    "income": Decimal("0"),
                    "expenses": Decimal("0"),
                    "net_change": Decimal("0"),
                }

            amount = self._money(event["amount"])

            if amount > 0:
                months[month]["income"] += amount
            else:
                months[month]["expenses"] += -amount

            months[month]["net_change"] += amount

        from datetime import timedelta

        # Include months even when no forecast events occur.
        cursor = date(start_date.year, start_date.month, 1)
        last_month = date(end_date.year, end_date.month, 1)

        results = []

        while cursor <= last_month:
            key = cursor.strftime("%Y-%m")

            summary = months.get(key, {
                "income": Decimal("0"),
                "expenses": Decimal("0"),
                "net_change": Decimal("0"),
            })

            opening_balance = balance
            balance += summary["net_change"]

            results.append({
                "month": key,
                "opening_balance": float(self._money(opening_balance)),
                "predicted_income": float(
                    self._money(summary["income"])
                ),
                "predicted_expenses": float(
                    self._money(summary["expenses"])
                ),
                "net_change": float(
                    self._money(summary["net_change"])
                ),
                "closing_balance": float(self._money(balance)),
            })

            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)

        return {
            "status": "estimated",
            "forecast_type": "historical_pattern_simulation",
            "account_id": account_id,
            "months": results,
            "limitations": (
                "Monthly balances include forecast recurring events only. "
                "Estimated variable cash withdrawals are not deducted."
            ),
        }
        