
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


class SafeToSpendService:
    """Calculate a cashflow-based spending allowance."""

    @staticmethod
    def _money(value):
        return Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def calculate(
        self,
        starting_balance,
        events,
        start_date: date,
        end_date: date,
        monthly_variable_outflow,
        safety_buffer=500,
        variable_status="estimated",
        monthly_income=0,
    ):
        if end_date < start_date:
            raise ValueError("end_date must not precede start_date")

        if variable_status not in {"estimated", "low_coverage"}:
            return {
                "status": "unavailable",
                "safe_to_spend": None,
                "reason": "Variable outflow estimate unavailable",
            }

        balance = self._money(starting_balance)
        buffer = self._money(safety_buffer)
        monthly_outflow = self._money(monthly_variable_outflow)
        monthly_income_amount = self._money(monthly_income)

        if buffer < 0 or monthly_outflow < 0:
            raise ValueError("Amounts must not be negative")

        if monthly_income_amount < 0:
            raise ValueError("Monthly income cannot be negative")

        # Daily allocation is an approximation, not an observed
        # transaction schedule.
        daily_outflow = monthly_outflow / Decimal("30.44")
        daily_income = monthly_income_amount / Decimal("30.44")

        # Events are dictionaries with date and signed amount.
        events_by_date = {}

        for event in events:
            event_date = event["date"]

            if isinstance(event_date, str):
                event_date = date.fromisoformat(event_date)

            if start_date <= event_date <= end_date:
                events_by_date[event_date] = (
                    events_by_date.get(event_date, Decimal("0"))
                    + self._money(event["amount"])
                )

        lowest_balance = balance
        lowest_date = start_date
        current_date = start_date

        while current_date <= end_date:
            balance += events_by_date.get(
                current_date, Decimal("0")
            )
            balance += daily_income
            balance -= daily_outflow

            if balance < lowest_balance:
                lowest_balance = balance
                lowest_date = current_date

            current_date += timedelta(days=1)

        available = max(
            Decimal("0"),
            lowest_balance - buffer,
        )

        return {
            "status": (
                "estimated"
                if variable_status == "estimated"
                else "low_confidence"
            ),
            "safe_to_spend": float(self._money(available)),
            "lowest_adjusted_balance": float(
                self._money(lowest_balance)
            ),
            "lowest_balance_date": lowest_date.isoformat(),
            "safety_buffer": float(buffer),
            "monthly_variable_outflow": float(monthly_outflow),
            "method": "minimum_adjusted_daily_balance",
            "limitations": (
                "This is a cashflow-based allowance, not a "
                "guaranteed safe spending amount. Variable "
                "withdrawals are approximated uniformly across "
                "days and may include non-consumption transfers."
            ),
        }
