
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


class SmartAlertService:
    """Detect potential shortfalls using recurring events and cash outflow estimates."""

    @staticmethod
    def _money(value):
        return Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def analyze(
        self,
        starting_balance: float,
        events: list,
        start_date: date,
        end_date: date,
        monthly_variable_outflow: float,
        safety_buffer: float = 500.0,
        scenario: str = "typical",
    ) -> dict:
        if end_date < start_date:
            raise ValueError("End date cannot precede start date")

        if (
            starting_balance is None
            or monthly_variable_outflow is None
        ):
            return {
                "status": "unavailable",
                "scenario": scenario,
                "alerts": [],
                "reason": "Missing balance or spending estimate",
            }

        balance = self._money(starting_balance)
        buffer = self._money(safety_buffer)
        daily_outflow = (
            Decimal(str(monthly_variable_outflow))
            / Decimal("30.44")
        )

        events_by_date = {}

        for event in events:
            event_date = event["date"]

            if isinstance(event_date, str):
                event_date = date.fromisoformat(event_date)

            if start_date <= event_date <= end_date:
                events_by_date.setdefault(event_date, []).append(event)

        alerts = []
        previous_below_buffer = balance < buffer
        lowest_balance = balance
        lowest_date = start_date

        cursor = start_date

        while cursor <= end_date:
            daily_events = events_by_date.get(cursor, [])

            for event in daily_events:
                balance += self._money(event["amount"])

            balance -= daily_outflow
            balance = self._money(balance)

            if balance < lowest_balance:
                lowest_balance = balance
                lowest_date = cursor

            below_buffer = balance < buffer

            if below_buffer and not previous_below_buffer:
                alerts.append({
                    "type": "projected_low_balance",
                    "severity": (
                        "critical" if balance < 0 else "warning"
                    ),
                    "date": cursor.isoformat(),
                    "projected_balance": float(balance),
                    "safety_buffer": float(buffer),
                    "scenario": scenario,
                    "message": (
                        "Projected balance may fall below "
                        "your selected safety buffer."
                    ),
                    "suggestion": (
                        "Review upcoming payments and "
                        "consider reducing optional spending."
                    ),
                })

            previous_below_buffer = below_buffer
            cursor += timedelta(days=1)

        # Report an existing shortfall even if the forecast
        # starts below the safety buffer.
        if self._money(starting_balance) < buffer:
            alerts.insert(0, {
                "type": "starting_low_balance",
                "severity": (
                    "critical" if starting_balance < 0 else "warning"
                ),
                "date": start_date.isoformat(),
                "projected_balance": float(
                    self._money(starting_balance)
                ),
                "safety_buffer": float(buffer),
                "scenario": scenario,
                "message": "Starting balance is below the safety buffer.",
                "suggestion": "Review upcoming essential payments.",
            })

        return {
            "status": "estimated",
            "scenario": scenario,
            "alerts": alerts,
            "lowest_adjusted_balance": float(
                self._money(lowest_balance)
            ),
            "lowest_balance_date": lowest_date.isoformat(),
            "method": "daily_recurring_events_plus_estimated_cash_outflow",
            "limitations": (
                "Uses historical cash withdrawals as an outflow proxy. "
                "Cash withdrawals may not represent actual consumption. "
                "This is a scenario estimate, not a guaranteed prediction."
            ),
        }
