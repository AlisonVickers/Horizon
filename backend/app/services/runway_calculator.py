
from decimal import Decimal, ROUND_HALF_UP


class RunwayCalculator:
    """Calculate financial runway using Tangerine's judging formula."""

    MAX_MONTHS = Decimal("120")

    @staticmethod
    def calculate(
        buffer: float,
        monthly_spending: float,
        monthly_income: float,
        one_off_costs: float = 0,
    ) -> dict:
        b = Decimal(str(buffer))
        s = Decimal(str(monthly_spending))
        i = Decimal(str(monthly_income))
        costs = Decimal(str(one_off_costs))

        if not all(x.is_finite() for x in (b, s, i, costs)):
            raise ValueError("Inputs must be finite")

        if s < 0 or i < 0 or costs < 0:
            raise ValueError(
                "Income, spending, and one-off costs cannot be negative"
            )

        buffer_left = b - costs
        monthly_shortfall = s - i

        if buffer_left <= 0:
            runway = Decimal("0")
            status = "depleted"
        elif monthly_shortfall <= 0:
            runway = self_max = RunwayCalculator.MAX_MONTHS
            status = "no_shortfall"
        else:
            runway = min(
                buffer_left / monthly_shortfall,
                RunwayCalculator.MAX_MONTHS,
            ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            status = "shortfall"

        return {
            "status": status,
            "runway_months": float(runway),
            "buffer_left": float(buffer_left),
            "monthly_shortfall": float(monthly_shortfall),
            "display": (
                "No shortfall (120+ months)"
                if status == "no_shortfall"
                else f"{runway:.1f} months"
            ),
            "method": "tangerine_judging_formula",
        }

