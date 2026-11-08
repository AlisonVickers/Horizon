
import calendar
from datetime import date

import pandas as pd


class VariableSpendingEstimator:
    """Estimate cash outflow from historical withdrawals."""

    def estimate(
        self,
        transactions: pd.DataFrame,
        as_of: date,
        lookback_months: int = 12,
    ) -> dict:
        if lookback_months < 1:
            raise ValueError("lookback_months must be positive")

        if transactions.empty:
            return {
                "status": "unavailable",
                "monthly_estimate": None,
                "daily_estimate": None,
                "monthly_totals": [],
                "method": "median_monthly_cash_withdrawals",
            }

        df = transactions.copy()
        df["date"] = pd.to_datetime(df["date"])

        # Do not use transactions after the historical cutoff.
        df = df[df["date"].dt.date <= as_of]

        if df.empty:
            return {
                "status": "unavailable",
                "monthly_estimate": None,
                "daily_estimate": None,
                "monthly_totals": [],
                "method": "median_monthly_cash_withdrawals",
            }

        cutoff_month = pd.Period(as_of, freq="M")
        # Exclude the current month if it is incomplete.
        last_complete_month = (
            cutoff_month
            if as_of.day == calendar.monthrange(
                as_of.year, as_of.month
            )[1]
            else cutoff_month - 1
        )

        months = pd.period_range(
            end=last_complete_month,
            periods=lookback_months,
            freq="M",
        )
        # Determine which months are supported by the account history.
        first_observed_month = df["date"].min().to_period("M")
        last_observed_month = df["date"].max().to_period("M")
        
        covered_months = [
            month for month in months
            if first_observed_month <= month <= last_observed_month
        ]
        
        coverage_ratio = len(covered_months) / lookback_months
        
        if not covered_months:
            return {
                "status": "unavailable",
                "monthly_estimate": None,
                "daily_estimate": None,
                "monthly_totals": [],
                "method": "median_monthly_cash_withdrawals",
                "coverage_ratio": 0.0,
                "limitations": "No historical data in the requested window.",
            }
            
        withdrawals = df[
            (df["operation"] == "cash withdrawal")
            & (df["signed_amount"] < 0)
        ].copy()

        withdrawals["month"] = withdrawals["date"].dt.to_period("M")
        withdrawals["outflow"] = -withdrawals["signed_amount"]

        monthly = (
            withdrawals.groupby("month")["outflow"]
            .sum()
            .reindex(covered_months, fill_value=0.0)
        )

        # Median resists unusually large monthly withdrawals.
        monthly_estimate = round(float(monthly.median()), 2)
        
        conservative_monthly_estimate = round(
            float(monthly.quantile(0.75)), 2
        )
        
        daily_estimate = round(monthly_estimate / 30.44, 2)

        
        return {
            "status": (
                "estimated" if coverage_ratio >= 0.75
                else "low_coverage"
            ),
            "monthly_estimate": monthly_estimate,
            "daily_estimate": daily_estimate,
            "monthly_totals": [
                {
                    "month": str(month),
                    "amount": round(float(amount), 2),
                }
                for month, amount in monthly.items()
            ],
            "method": "median_monthly_cash_withdrawals",
            "lookback_months": lookback_months,
            "coverage_ratio": round(coverage_ratio, 3),
            "covered_months": len(covered_months),
            "conservative_monthly_estimate": conservative_monthly_estimate,
            "limitations": (
                "Cash withdrawals are bank outflows, not verified "
                "everyday consumption. Transfers and recurring "
                "obligations are excluded. Coverage is estimated "
                "from the observed transaction date range."
            ),
        }
    
