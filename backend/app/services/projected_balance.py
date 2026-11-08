
from decimal import Decimal, ROUND_HALF_UP

from app.services.cashflow_forecast import CashflowEvent


class ProjectedBalanceService:
    """Project balances from a starting balance and cashflow events."""

    @staticmethod
    def _money(value) -> Decimal:
        return Decimal(str(value)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def project(
        self,
        starting_balance: float,
        events: list[CashflowEvent],
    ) -> dict:

        if starting_balance is None:
            raise ValueError("Starting balance is required")

        balance = self._money(starting_balance)
        starting_amount = float(balance)

        timeline = []

        for event in sorted(
            events,
            key=lambda e: (e.date, e.event_type, e.source_key),
        ):
            amount = self._money(event.amount)
            balance += amount

            timeline.append({
                "date": event.date.isoformat(),
                "category": event.category,
                "event_type": event.event_type,
                "amount": float(amount),
                "projected_balance": float(balance),
            })

        lowest_balance = min(
            [starting_amount]
            + [item["projected_balance"] for item in timeline]
        )

        return {
            "starting_balance": starting_amount,
            "projected_ending_balance": float(balance),
            "lowest_projected_balance": lowest_balance,
            "timeline": timeline,
            "projection_scope": "detected_recurring_events_only",
        }
