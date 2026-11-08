from dataclasses import dataclass
from app.services.recurrence_analyzer import RecurrenceAnalyzer
import pandas as pd


@dataclass(frozen=True)
class IncomePattern:
    category: str
    typical_amount: float
    day_of_month: int | None
    frequency: str
    confidence: str
    observations: int

    # Additional information for forecasting
    source_key: str = ""
    last_observed_date: str = ""
    amount_variability: float = 0.0
    source_quality: str = "unknown"
    interval_days: float | None = None
    days_of_month: tuple[int, ...] = ()
    month_end: bool = False


class IncomeDetector:

    def detect(self, transactions: pd.DataFrame) -> list[IncomePattern]:
        if transactions.empty:
            return []

        incoming = transactions[
            (transactions["signed_amount"] > 0)
            & (
                transactions["operation"]
                == "transfer in from another bank"
            )
        ].copy()

        if incoming.empty:
            return []
        # Keep transactions with at least one usable source identifier.
        # Fully unsourced transactions remain in the original dataset,
        # but are excluded from automatic recurring-income detection.

        source_columns = ["partner_bank", "partner_account"]

        for column in source_columns:
            incoming[column] = (
                incoming[column]
                .astype("string")
                .str.strip()
                .replace("", pd.NA)
            )

        has_source = incoming[source_columns].notna().any(axis=1)

        incoming = incoming[has_source].copy()

        if incoming.empty:
            return []
        incoming["date"] = pd.to_datetime(incoming["date"])
        incoming["month"] = incoming["date"].dt.to_period("M")

        patterns = []

        # Use the latest available transaction as the reference date.
        reference_date = pd.to_datetime(
            transactions["date"],
            errors="coerce"
        ).max()

        if pd.isna(reference_date):
            return []

        grouped = incoming.groupby(
            ["partner_bank", "partner_account"],
            dropna=False
        )

        for source, group in grouped:
            group = group.sort_values("date")

            # Require enough observations to recognize a pattern.
            if len(group) < 4:
                continue

            # Let the shared analyzer detect recurring timing patterns.
            recurrence = RecurrenceAnalyzer().analyze(group["date"])

            if recurrence is None:
                continue

            # detect pattern engine
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
                day_of_month = int(group["date"].dt.day.median())
            else:
                day_of_month = None

            amounts = group["signed_amount"]
            median_amount = float(amounts.median())

            if median_amount > 0:
                amount_variability = float(
                    (amounts - median_amount).abs().median()
                    / median_amount
                )
            else:
                amount_variability = 0.0

            last_payment = group["date"].max()

            # Reject income streams that stopped long before
            # the latest observed account activity.
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

            source_key = "|".join(
                "" if pd.isna(value) else str(value)
                for value in source
            )

            # Check whether both source identifiers are available.
            source_quality = (
                "complete"
                if all(pd.notna(value) for value in source)
                else "partial"
            )

            # Provisional confidence based on source identification.
            confidence = (
                "high"
                if source_quality == "complete"
                else "low"
            )

            patterns.append(
                IncomePattern(
                    category="recurring_incoming_transfer",
                    typical_amount=round(median_amount, 2),
                    day_of_month=day_of_month,
                    frequency=frequency,
                    confidence=confidence,
                    observations=len(group),
                    source_key=source_key,
                    last_observed_date=last_payment.strftime("%Y-%m-%d"),
                    amount_variability=round(amount_variability, 4),
                    source_quality=source_quality,
                    interval_days=recurrence.interval_days,
                    days_of_month=recurrence.days_of_month,
                    month_end=recurrence.month_end,
                )
            )

        return patterns
