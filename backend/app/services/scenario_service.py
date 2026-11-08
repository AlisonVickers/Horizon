from __future__ import annotations

from typing import Mapping


class ScenarioService:
    """Apply the supported scenario event keys to an account profile."""

    @staticmethod
    def _percent(value: float) -> float:
        # Accept the original fractional form as well as slider percentages.
        return value if 0 <= value <= 1 else value / 100

    def apply(
        self,
        profile: Mapping[str, float],
        shocks: list[Mapping[str, float]],
    ) -> dict[str, float]:
        income = profile["income"]
        spending = profile["spending"]
        one_off_costs = 0.0

        for shock in shocks:
            name = shock["name"]
            value = shock["value"]
            if name in {"job_loss_ei", "ei_income_percent"}:
                # job_loss_ei is the established key; its value is the EI share.
                income *= self._percent(value)
            elif name in {"rent_up_pct", "rent_up_percent"}:
                spending += profile["household_bills"] * self._percent(value)
            elif name in {"pay_cut_pct", "pay_cut_percent"}:
                income *= max(0.0, 1.0 - self._percent(value))
            elif name == "one_off_costs":
                one_off_costs += value
            elif name == "loan_payment_reduction":
                spending = max(
                    0.0,
                    spending - (profile["loan_payment"] if value <= 1 else value),
                )
            elif name == "new_car_payment":
                spending += value
            elif name == "everyday_cut_pct":
                spending = max(
                    0.0,
                    spending - profile["everyday_spending"] * self._percent(value),
                )
            else:
                raise ValueError(f"Unsupported scenario shock: {name}")

        return {
            "income": income,
            "spending": spending,
            "one_off_costs": one_off_costs,
        }
