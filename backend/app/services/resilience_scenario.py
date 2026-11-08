
from decimal import Decimal

from app.services.runway_calculator import RunwayCalculator


class ResilienceScenarioService:
    """Calculate combined financial shocks using Tangerine's rules."""

    def __init__(self):
        self.calculator = RunwayCalculator()

    def simulate(
        self,
        profile: dict,
        *,
        income_replacement_rate: float = 1.0,
        bills_increase_percent: float = 0.0,
        one_off_cost: float = 0.0,
        new_monthly_payment: float = 0.0,
        benefit_duration_months: int | None = None,
    ) -> dict:
        if profile.get("status") != "available":
            raise ValueError("An available financial profile is required")

        def number(value):
            result = Decimal(str(value))
            if not result.is_finite():
                raise ValueError("Financial inputs must be finite")
            return result

        rate = number(income_replacement_rate)
        increase = number(bills_increase_percent)
        repair = number(one_off_cost)
        payment = number(new_monthly_payment)

        if not Decimal("0") <= rate <= Decimal("1"):
            raise ValueError("Income replacement rate must be between 0 and 1")

        if min(increase, repair, payment) < 0:
            raise ValueError("Shock costs cannot be negative")

        if benefit_duration_months is not None:
            if (
                isinstance(benefit_duration_months, bool)
                or not isinstance(benefit_duration_months, int)
                or benefit_duration_months <= 0
            ):
                raise ValueError("Benefit duration must be a positive integer")

        income = number(profile["typical_monthly_income"])
        spending = number(profile["typical_monthly_spending"])
        bills = number(profile["household_bills"])
        buffer = number(profile["savings_buffer"])

        income_after = income * rate
        extra_bills = bills * increase / Decimal("100")
        spending_after = spending + extra_bills + payment

        baseline = self.calculator.calculate(
            buffer=float(buffer),
            monthly_spending=float(spending),
            monthly_income=float(income),
        )

        shocked = self.calculator.calculate(
            buffer=float(buffer),
            monthly_spending=float(spending_after),
            monthly_income=float(income_after),
            one_off_costs=float(repair),
        )

        duration = benefit_duration_months

        return {
            "status": "calculated",
            "account_id": profile["account_id"],
            "baseline": baseline,
            "shocked": shocked,
            "income_after": round(float(income_after), 2),
            "spending_after": round(float(spending_after), 2),
            "additional_monthly_bills": round(float(extra_bills), 2),
            "scenario": {
                "income_replacement_rate": float(rate),
                "bills_increase_percent": float(increase),
                "one_off_cost": float(repair),
                "new_monthly_payment": float(payment),
                "benefit_duration_months": duration,
            },
            "outlasts_benefit": (
                None if duration is None
                else shocked["status"] == "no_shortfall"
                or shocked["runway_months"] >= duration
            ),
            "limitations": [
                "Historical median-based estimates",
                "Income replacement is assumed, not verified EI eligibility",
                "Runway assumes the shock persists indefinitely",
                "Benefit expiry is not modeled",
            ],
        }
