
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RecurrenceResult:
    frequency: str
    interval_days: float | None
    observations: int
    timing_consistency: float
    days_of_month: tuple[int, ...] = ()
    month_end: bool = False


class RecurrenceAnalyzer:
    """
    Analyzes transaction dates to discover recurring intervals.

    Does not decide whether a transaction is income or an expense.
    """

    def analyze(self, dates: pd.Series) -> RecurrenceResult | None:
        parsed_dates = (
            pd.to_datetime(dates, errors="coerce")
            .dropna()
            .sort_values()
            .reset_index(drop=True)
        )

        if len(parsed_dates) < 4:
            return None

        intervals = parsed_dates.diff().dt.days.dropna()

        if intervals.empty:
            return None

        typical_interval = float(intervals.median())

        if typical_interval <= 0:
            return None

        # Measure the proportion of gaps close to the typical gap.
        tolerance = max(1.0, typical_interval * 0.10)

        consistent = (
            (intervals - typical_interval).abs() <= tolerance
        )

        timing_consistency = float(consistent.mean())

        # Do not force a pattern when the evidence is weak.


        # Check whether payments follow consecutive calendar months.
        months = parsed_dates.dt.to_period("M")

        month_numbers = [
            month.year * 12 + month.month
            for month in months
        ]

        consecutive_months = (
            months.nunique() == len(parsed_dates)
            and all(
                current - previous == 1
                for previous, current in zip(
                    month_numbers, month_numbers[1:]
                )
            )
        )

        days = parsed_dates.dt.day
        days_before_month_end = (
            parsed_dates.dt.days_in_month - days
        )

        fixed_day_pattern = days.max() - days.min() <= 2
        month_end_pattern = (days_before_month_end <= 3).all()

        # Check for two recurring payments per calendar month.
        monthly_groups = parsed_dates.groupby(
            parsed_dates.dt.to_period("M")
        )

        monthly_dates = [
            group.dt.day.sort_values().tolist()
            for _, group in monthly_groups
        ]

        two_per_month = (
            len(monthly_dates) >= 3
            and all(len(days) == 2 for days in monthly_dates)
        )

        semimonthly_pattern = False

        if two_per_month:
            first_days = [days[0] for days in monthly_dates]
            second_days = [days[1] for days in monthly_dates]

            stable_first = max(first_days) - min(first_days) <= 2
            stable_second = max(second_days) - min(second_days) <= 2

            month_numbers = [
                month.year * 12 + month.month
                for month in monthly_groups.groups
            ]

            consecutive = all(
                current - previous == 1
                for previous, current in zip(
                    month_numbers, month_numbers[1:]
                )
            )

            semimonthly_pattern = (
                stable_first and stable_second and consecutive
            )
        days_of_month = ()

        if semimonthly_pattern:
            frequency = "semimonthly"
            days_of_month = (
                int(pd.Series(first_days).median()),
                int(pd.Series(second_days).median()),
            )

        elif consecutive_months and (
            fixed_day_pattern or month_end_pattern
        ):
            frequency = "monthly"

            if not month_end_pattern:
                days_of_month = (int(days.median()),)

        elif timing_consistency < 0.75:
            return None
        elif 6 <= typical_interval <= 8:
            frequency = "weekly"
        elif 13 <= typical_interval <= 15:
            frequency = "biweekly"
        else:
            frequency = "custom"

        return RecurrenceResult(
            frequency=frequency,
            interval_days=round(typical_interval, 2),
            observations=len(parsed_dates),
            timing_consistency=round(timing_consistency, 4),
            days_of_month=days_of_month,
            month_end=bool(
                frequency == "monthly"
                and month_end_pattern
            ),
        )
