import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.services.safe_to_spend import SafeToSpendService


class ScenarioSimulatorService:
    """Simulate hypothetical changes without modifying financial records."""

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

    def simulate(
        self,
        starting_balance: float,
        events: list,
        start_date: date,
        end_date: date,
        monthly_variable_outflow: float,
        safety_buffer: float = 500.0,
        scenario_type: str = "one_time_expense",
        amount: float = 0.0,
        scenario_date: date | None = None,
        income_reduction_percent: float = 0.0,
    ) -> dict:

        if end_date < start_date:
            raise ValueError("End date cannot precede start date")

        if starting_balance is None or monthly_variable_outflow is None:
            return {
                "status": "unavailable",
                "reason": "Missing historical balance or spending estimate",
            }

        if self._money(amount) < 0:
            raise ValueError("Amount cannot be negative")

        if not 0 <= income_reduction_percent <= 100:
            raise ValueError("Income reduction must be between 0 and 100")

        if scenario_type not in (
            "one_time_expense",
            "income_reduction",
        ):
            raise ValueError("Unsupported scenario type")

        if scenario_type == "one_time_expense":
            if scenario_date is None:
                raise ValueError("Expense date is required")

            if not start_date <= scenario_date <= end_date:
                raise ValueError("Expense date must be within forecast period")

        baseline_events = [
            dict(event)
            for event in events
        ]

        simulated_events = [
            dict(event)
            for event in events
        ]

        if scenario_type == "one_time_expense":
            simulated_events.append({
                "date": scenario_date.isoformat(),
                "amount": -float(self._money(amount)),
                "event_type": "scenario_expense",
            })

        elif scenario_type == "income_reduction":
            reduction = Decimal(
                str(income_reduction_percent)
            ) / Decimal("100")

            for event in simulated_events:
                if (
                    event.get("event_type") == "income"
                    and self._money(event["amount"]) > 0
                ):
                    adjusted = self._money(event["amount"]) * (
                        Decimal("1") - reduction
                    )
                    event["amount"] = float(self._money(adjusted))

        baseline = self.safe_to_spend_service.calculate(
            starting_balance=starting_balance,
            events=baseline_events,
            start_date=start_date,
            end_date=end_date,
            monthly_variable_outflow=monthly_variable_outflow,
            safety_buffer=safety_buffer,
            variable_status="estimated",
        )

        simulated = self.safe_to_spend_service.calculate(
            starting_balance=starting_balance,
            events=simulated_events,
            start_date=start_date,
            end_date=end_date,
            monthly_variable_outflow=monthly_variable_outflow,
            safety_buffer=safety_buffer,
            variable_status="estimated",
        )

        if (
            baseline["status"] != "estimated"
            or simulated["status"] != "estimated"
        ):
            return {
                "status": "unavailable",
                "reason": "Unable to calculate scenario projections",
            }

        difference = self._money(
            simulated["lowest_adjusted_balance"]
        ) - self._money(
            baseline["lowest_adjusted_balance"]
        )

        return {
            "status": "estimated",
            "scenario_type": scenario_type,
            "baseline": baseline,
            "simulated": simulated,
            "change_in_lowest_balance": float(difference),
            "baseline_buffer_breached": (
                baseline["lowest_adjusted_balance"] < safety_buffer
            ),
            "simulated_buffer_breached": (
                simulated["lowest_adjusted_balance"] < safety_buffer
            ),
            "scenario_events": simulated_events,
            "limitations": (
                "This is a hypothetical scenario based on historical "
                "recurring cashflow and estimated cash withdrawals. "
                "It is not a guarantee of affordability."
            ),
        }

    def simulate_shocks(
        self,
        starting_balance: float,
        events: list,
        start_date: date,
        end_date: date,
        monthly_variable_outflow: float,
        shocks: list[dict],
        safety_buffer: float = 500.0,
        monthly_income: float = 0.0,
    ) -> dict:
        """Apply the shock keys used by the adapter's scenario dashboard."""
        baseline_events = [dict(event) for event in events]
        simulated_events = [dict(event) for event in events]
        variable_outflow = monthly_variable_outflow
        one_off_costs = 0.0
        baseline_monthly_income = float(monthly_income)
        simulated_monthly_income = baseline_monthly_income
        if baseline_monthly_income < 0:
            raise ValueError("Monthly income cannot be negative")

        for shock in shocks:
            name = shock["name"]
            value = float(shock["value"])
            if value < 0:
                raise ValueError("Shock values cannot be negative")

            if name == "job_loss_ei":
                share = value if value <= 1 else value / 100
                if share > 1:
                    raise ValueError("Income replacement share cannot exceed 100%")
                simulated_monthly_income *= share
                for event in simulated_events:
                    if event.get("event_type") == "income" and event["amount"] > 0:
                        event["amount"] = float(self._money(event["amount"] * share))
            elif name == "pay_cut_pct":
                reduction = value if value <= 1 else value / 100
                if reduction > 1:
                    raise ValueError("Pay cut cannot exceed 100%")
                simulated_monthly_income *= 1 - reduction
                for event in simulated_events:
                    if event.get("event_type") == "income" and event["amount"] > 0:
                        event["amount"] = float(
                            self._money(event["amount"] * (1 - reduction))
                        )
            elif name == "rent_up_pct":
                increase = value if value <= 1 else value / 100
                for event in simulated_events:
                    category = str(event.get("category", "")).lower()
                    if event["amount"] < 0 and ("rent" in category or "household" in category):
                        event["amount"] = float(
                            self._money(event["amount"] * (1 + increase))
                        )
            elif name == "new_car_payment":
                cursor = start_date
                while cursor <= end_date:
                    simulated_events.append({
                        "date": cursor.isoformat(),
                        "amount": -float(self._money(value)),
                        "event_type": "scenario_expense",
                        "category": "new car payment",
                    })
                    day = min(
                        cursor.day,
                        calendar.monthrange(
                            cursor.year + (cursor.month == 12),
                            1 if cursor.month == 12 else cursor.month + 1,
                        )[1],
                    )
                    cursor = date(
                        cursor.year + (cursor.month == 12),
                        1 if cursor.month == 12 else cursor.month + 1,
                        day,
                    )
            elif name == "one_off_costs":
                one_off_costs += value
                simulated_events.append({
                    "date": start_date.isoformat(),
                    "amount": -float(self._money(value)),
                    "event_type": "scenario_expense",
                    "category": "one-off cost",
                })
            elif name == "loan_payment_reduction":
                for event in simulated_events:
                    category = str(event.get("category", "")).lower()
                    if event["amount"] < 0 and "loan" in category:
                        event["amount"] = float(
                            self._money(event["amount"] * max(0, 1 - value))
                        )
            elif name == "everyday_cut_pct":
                reduction = value if value <= 1 else value / 100
                variable_outflow = max(0.0, variable_outflow * (1 - reduction))
            else:
                raise ValueError(f"Unsupported scenario shock: {name}")

        baseline = self.safe_to_spend_service.calculate(
            starting_balance=starting_balance,
            events=baseline_events,
            start_date=start_date,
            end_date=end_date,
            monthly_variable_outflow=monthly_variable_outflow,
            safety_buffer=safety_buffer,
            variable_status="estimated",
            monthly_income=baseline_monthly_income,
        )
        simulated = self.safe_to_spend_service.calculate(
            starting_balance=starting_balance,
            events=simulated_events,
            start_date=start_date,
            end_date=end_date,
            monthly_variable_outflow=variable_outflow,
            safety_buffer=safety_buffer,
            variable_status="estimated",
            monthly_income=simulated_monthly_income,
        )
        if baseline["status"] != "estimated" or simulated["status"] != "estimated":
            return {
                "status": "unavailable",
                "reason": "Unable to calculate scenario projections",
            }

        difference = self._money(
            simulated["lowest_adjusted_balance"]
        ) - self._money(baseline["lowest_adjusted_balance"])
        return {
            "status": "estimated",
            "baseline": baseline,
            "simulated": simulated,
            "change_in_lowest_balance": float(difference),
            "baseline_buffer_breached": baseline["lowest_adjusted_balance"] < safety_buffer,
            "simulated_buffer_breached": simulated["lowest_adjusted_balance"] < safety_buffer,
            "scenario_events": simulated_events,
            "one_off_costs": one_off_costs,
            "monthly_variable_outflow": variable_outflow,
            "monthly_income": simulated_monthly_income,
            "baseline_monthly_income": baseline_monthly_income,
            "limitations": (
                "This is a hypothetical scenario based on historical recurring cashflow "
                "and estimated cash withdrawals. It is not a guarantee of affordability."
            ),
        }
