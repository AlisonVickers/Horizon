
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class RunwayResult:
    buffer_left: float
    gap: float
    runway_months: float
    is_capped: bool


class RunwayCalculator:
    MAX_RUNWAY = 120.0

    @staticmethod
    def calculate(
        B: float,
        one_off_costs: float,
        spending_after_shock: float,
        income_after_shock: float,
    ) -> RunwayResult:

        values = (
            B,
            one_off_costs,
            spending_after_shock,
            income_after_shock,
        )

        if not all(isfinite(v) for v in values):
            raise ValueError("All inputs must be finite numbers")

        if any(v < 0 for v in values):
            raise ValueError("Inputs cannot be negative")

        buffer_left = B - one_off_costs
        gap = spending_after_shock - income_after_shock

        if buffer_left <= 0:
            runway = 0.0

        elif gap <= 0:
            runway = RunwayCalculator.MAX_RUNWAY

        else:
            runway = min(
                buffer_left / gap,
                RunwayCalculator.MAX_RUNWAY,
            )

        return RunwayResult(
            buffer_left=buffer_left,
            gap=gap,
            runway_months=runway,
            is_capped=(
                buffer_left > 0
                and runway >= RunwayCalculator.MAX_RUNWAY
            ),
        )
