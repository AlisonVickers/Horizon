
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from app.data.account_store import AccountStore


class FinancialProfileService:
    """Build a customer profile using Tangerine judging definitions."""

    @staticmethod
    def _money(value):
        return float(
            Decimal(str(value)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        )

    @staticmethod
    def _median(frame, column):
        return float(frame[column].median())

    def build(self, account_id: int) -> dict:
        with AccountStore(account_id) as store:
            monthly = store.get_monthly_summary()
            loans = store.get_loans()

        if monthly.empty:
            return {
                "account_id": account_id,
                "status": "unavailable",
                "reason": "No monthly financial history available",
            }

        monthly = monthly.sort_values("month")

        # Tangerine's judging definitions
        income = self._median(monthly, "money_in")
        spending = self._median(monthly, "money_out")

        fixed_costs_by_month = (
            monthly["household_bills"]
            + monthly["insurance"]
            + monthly["loan_payments"]
        )
        fixed_costs = float(fixed_costs_by_month.median())

        household_bills = self._median(
            monthly, "household_bills"
        )

        buffer = float(
            monthly.tail(6)["avg_daily_balance"].mean()
        )

        # Only running loans count.
        active_loans = loans[
            loans["status"].isin(["C", "D"])
        ]

        active_loan_payment = (
            float(active_loans["monthly_payment"].sum())
            if not active_loans.empty
            else 0.0
        )

        return {
            "account_id": account_id,
            "status": "available",
            "as_of": str(monthly.iloc[-1]["month"]),
            "months_of_history": len(monthly),
            "typical_monthly_income": self._money(income),
            "typical_monthly_spending": self._money(spending),
            "typical_fixed_costs": self._money(fixed_costs),
            "household_bills": self._money(household_bills),
            "savings_buffer": self._money(buffer),
            "active_loan_payment": self._money(
                active_loan_payment
            ),
            "method": "tangerine_judging_definitions",
            "limitations": [
                "Historical account data through December 2025",
                "Median monthly figures are historical estimates",
                "Savings buffer uses average daily balances, not cash savings",
                "Active loans identified using statuses C and D",
            ],
        }
