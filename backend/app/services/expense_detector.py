
from dataclasses import dataclass

import pandas as pd

from app.services.recurrence_analyzer import RecurrenceAnalyzer


@dataclass(frozen=True)
class ExpensePattern:
    category: str
    typical_amount: float
    day_of_month: int | None
    frequency: str
    confidence: str
    observations: int

    # Additional information for reliable forecasting
    source_key: str = ""
    last_observed_date: str = ""
    amount_variability: float = 0.0
    interval_days: float | None = None
    days_of_month: tuple[int, ...] = ()
    month_end: bool = False


class ExpenseDetector:

    def detect(self, transactions: pd.DataFrame) -> list[ExpensePattern]:
        if transactions.empty:
            return []

        outgoing = transactions[
            transactions["signed_amount"] < 0
        ].copy()

        if outgoing.empty:
            return []

        outgoing["date"] = pd.to_datetime(outgoing["date"])
        outgoing["month"] = outgoing["date"].dt.to_period("M")

        # Only use outgoing bank transfers and statement fees.
        outgoing = outgoing[
            outgoing["operation"].isin([
                "transfer out to another bank",
                "bank fee",
            ])
        ].copy()

        outgoing["source_key"] = (
            outgoing["operation"].fillna("")
            + "|"
            + outgoing["partner_bank"].astype("string").fillna("")
            + "|"
            + outgoing["partner_account"].astype("string").fillna("")
            + "|"
            + outgoing["purpose"].astype("string").fillna("")
        )

        patterns = []

        reference_date = pd.to_datetime(
            transactions["date"], errors="coerce"
        ).max()

        if pd.isna(reference_date):
            return []

        for _, group in outgoing.groupby("source_key"):
            group = group.sort_values("date")

            last_payment = group["date"].max()

            # Detect recurring payment timing using the shared analyzer.
            recurrence = RecurrenceAnalyzer().analyze(group["date"])

            if recurrence is None:
                continue

            supported_frequencies = {
                "weekly",
                "biweekly",
                "semimonthly",
                "monthly",
                "custom",
            }

            if recurrence.frequency not in supported_frequencies:
                continue

            frequency = recurrence.frequency

            if frequency == "monthly":
                max_gap_days = 45
            elif frequency == "semimonthly":
                max_gap_days = 25
            elif frequency == "custom":
                max_gap_days = max(
                    7,
                    int(recurrence.interval_days * 1.5)
                )
            else:
                max_gap_days = {
                    "weekly": 11,
                    "biweekly": 21,
                }[frequency]

            if (reference_date - last_payment).days > max_gap_days:
                continue

            dates = group["date"]
            days = dates.dt.day

            # Use the shared analyzer's month-end decision.
            is_month_end = recurrence.month_end

            day_of_month = (
                int(days.median())
                if frequency == "monthly" and not is_month_end
                else None
            )

            amounts = group["signed_amount"].abs()

            # Measure how much payment amounts vary.
            median_amount = float(amounts.median())

            if median_amount > 0:
                amount_variability = float(
                    (amounts - median_amount).abs().median()
                    / median_amount
                )
            else:
                amount_variability = 0.0

            category = (
                group["purpose"].dropna().iloc[0]
                if group["purpose"].notna().any()
                else group["operation"].iloc[0]
            )

            patterns.append(
                ExpensePattern(
                    category=str(category),
                    typical_amount=round(median_amount, 2),
                    day_of_month=day_of_month,
                    frequency=frequency,
                    confidence="high",
                    observations=len(group),
                    source_key=str(group["source_key"].iloc[0]),
                    last_observed_date=last_payment.strftime("%Y-%m-%d"),
                    amount_variability=round(amount_variability, 4),
                    interval_days=recurrence.interval_days,
                    days_of_month=recurrence.days_of_month,
                    month_end=recurrence.month_end,
                )
            )

        return patterns
