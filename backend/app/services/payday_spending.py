
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.services.safe_to_spend import SafeToSpendService


class PaydaySpendingService:
    """Estimate additional spendable money before the next predicted payday."""

    def __init__(self, safe_to_spend_service=None):
        self.safe_to_spend_service = (
            safe_to_spend_service or SafeToSpendService()
        )

    @staticmethod
    def _money(value):
        return Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def calculate(
        self,
        starting_balance: float,
        events: list,
        start_date: date,
        end_date: date,
        monthly_variable_outflow: float,
        safety_buffer: float = 500.0,
        variable_status: str = "estimated",
    ) -> dict:

        if end_date < start_date:
            raise ValueError("End date cannot precede start date")

        # Only detected recurring income counts as a predicted payday.
        paydays = []

        for event in events:
            event_date = event["date"]
            if isinstance(event_date, str):
                event_date = date.fromisoformat(event_date)

            if (
                start_date <= event_date <= end_date
                and self._money(event["amount"]) > 0
                and event.get("event_type") == "income"
            ):
                paydays.append(event_date)

        if not paydays:
            return {
                "status": "unavailable",
                "next_payday": None,
                "spendable_until_payday": None,
                "reason": "No predicted recurring payday in the forecast period",
            }

        next_payday = min(paydays)

        # Exclude payday itself so the allowance does not
        # depend on income that has not arrived yet.
        spending_end = next_payday - timedelta(days=1)

        if spending_end < start_date:
            return {
                "status": "estimated",
                "next_payday": next_payday.isoformat(),
                "days_until_payday": 0,
                "spendable_until_payday": 0.0,
                "reason": "Payday is today; incoming funds are not yet included",
                "limitations": (
                    "Payday is inferred from historical recurring income "
                    "and is not a confirmed deposit."
                ),
            }

        relevant_events = []

        for event in events:
            event_date = event["date"]
            if isinstance(event_date, str):
                event_date = date.fromisoformat(event_date)

            if start_date <= event_date <= spending_end:
                relevant_events.append(event)

        allowance = self.safe_to_spend_service.calculate(
            starting_balance=starting_balance,
            events=relevant_events,
            start_date=start_date,
            end_date=spending_end,
            monthly_variable_outflow=monthly_variable_outflow,
            safety_buffer=safety_buffer,
            variable_status=variable_status,
        )

        if allowance["status"] != "estimated":
            return {
                "status": "unavailable",
                "next_payday": next_payday.isoformat(),
                "spendable_until_payday": None,
                "reason": "Insufficient support for spending estimate",
            }

        return {
            "status": "estimated",
            "next_payday": next_payday.isoformat(),
            "days_until_payday": (next_payday - start_date).days,
            "spendable_until_payday": allowance["safe_to_spend"],
            "lowest_adjusted_balance": allowance[
                "lowest_adjusted_balance"
            ],
            "safety_buffer": float(self._money(safety_buffer)),
            "method": "minimum_adjusted_balance_before_next_payday",
            "limitations": (
                "Payday and cash withdrawals are historical-pattern "
                "estimates. This is not guaranteed available money."
            ),
        }
