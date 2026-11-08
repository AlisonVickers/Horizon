
from decimal import Decimal


class LowBalanceAlertService:
    """Detect low balances in a projected cashflow timeline."""

    def analyze(
        self,
        projection: dict,
        safety_buffer: float = 500.00,
    ) -> dict:

        if safety_buffer < 0:
            raise ValueError("Safety buffer cannot be negative")

        if projection is None:
            return {
                "status": "unavailable",
                "safety_buffer": safety_buffer,
                "alerts": [],
            }

        threshold = Decimal(str(safety_buffer))
        alerts = []

        starting_balance = Decimal(
            str(projection["starting_balance"])
        )

        if starting_balance < threshold:
            alerts.append({
                "date": None,
                "type": "starting_balance_below_buffer",
                "projected_balance": float(starting_balance),
                "shortfall": float(threshold - starting_balance),
            })

        # Report the first event that enters each below-buffer period.
        was_below = starting_balance < threshold

        for event in projection["timeline"]:
            balance = Decimal(str(event["projected_balance"]))
            is_below = balance < threshold

            if is_below and not was_below:
                alerts.append({
                    "date": event["date"],
                    "type": "balance_below_buffer",
                    "projected_balance": float(balance),
                    "shortfall": float(threshold - balance),
                })

            was_below = is_below

        return {
            "status": "warning" if alerts else "ok",
            "safety_buffer": float(threshold),
            "alerts": alerts,
        }
