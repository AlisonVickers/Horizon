
from datetime import date, timedelta

import pandas as pd

from app.services.variable_spending import VariableSpendingEstimator


class ForecastBacktestService:
    """Evaluate historical variable-outflow predictions."""

    def __init__(self):
        self.estimator = VariableSpendingEstimator()

    def evaluate(self, transactions, test_months=6):
        if test_months < 1:
            raise ValueError("test_months must be positive")

        if transactions.empty:
            return {"status": "unavailable", "results": []}

        df = transactions.copy()
        df["date"] = pd.to_datetime(df["date"])

        latest = df["date"].max().to_period("M")
        months = pd.period_range(
            end=latest,
            periods=test_months,
            freq="M",
        )

        results = []

        for month in months:
            cutoff = month.start_time.date() - timedelta(days=1)

            # Historical data only: no future information leakage.
            historical = df[df["date"].dt.date <= cutoff]

            prediction = self.estimator.estimate(
                historical,
                as_of=cutoff,
                lookback_months=12,
            )

            if prediction["status"] != "estimated":
                continue

            actual_rows = df[
                (df["date"].dt.to_period("M") == month)
                & (df["operation"] == "cash withdrawal")
                & (df["signed_amount"] < 0)
            ]

            actual = round(
                float(-actual_rows["signed_amount"].sum()), 2
            )

            predicted = prediction["monthly_estimate"]
            absolute_error = round(abs(predicted - actual), 2)

            results.append({
                "month": str(month),
                "predicted": predicted,
                "actual": actual,
                "absolute_error": absolute_error,
            })

        if not results:
            return {"status": "unavailable", "results": []}

        mae = round(
            sum(r["absolute_error"] for r in results)
            / len(results),
            2,
        )

        reliability = (
            "high" if mae <= 1000
            else "moderate" if mae <= 3000
            else "low"
        )
        
        return {
            "status": "evaluated",
            "months_evaluated": len(results),
            "mean_absolute_error": mae,
            "reliability": reliability,
            "results": results,
            "limitations": (
                "Backtesting evaluates cash-withdrawal estimates, "
                "not verified consumer spending or income forecasts."
            ),
        }