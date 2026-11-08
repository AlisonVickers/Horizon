
from dataclasses import dataclass
from datetime import date, timedelta
import calendar

from app.services.income_detector import IncomePattern
from app.services.expense_detector import ExpensePattern


@dataclass(frozen=True)
class CashflowEvent:
    date: date
    category: str
    amount: float
    event_type: str
    source_key: str


class CashflowForecastService:

    def forecast(
        self,
        income_patterns: list[IncomePattern],
        expense_patterns: list[ExpensePattern],
        start_date: date,
        end_date: date,
    ) -> list[CashflowEvent]:

        if end_date < start_date:
            raise ValueError("end_date cannot precede start_date")

        events = []

        for pattern in income_patterns:
            events.extend(
                self._generate_events(
                    pattern, "income", start_date, end_date
                )
            )

        for pattern in expense_patterns:
            events.extend(
                self._generate_events(
                    pattern, "expense", start_date, end_date
                )
            )

        return sorted(
            events,
            key=lambda event: (event.date, event.event_type, event.source_key),
        )

    def _generate_events(
        self,
        pattern: IncomePattern | ExpensePattern,
        event_type: str,
        start_date: date,
        end_date: date,
    ) -> list[CashflowEvent]:

        dates = []

        if pattern.frequency in {"monthly", "semimonthly"}:
            year, month = start_date.year, start_date.month

            while (year, month) <= (end_date.year, end_date.month):
                last_day = calendar.monthrange(year, month)[1]

                if pattern.month_end:
                    candidate_days = [last_day]
                else:
                    candidate_days = [
                        min(day, last_day)
                        for day in pattern.days_of_month
                    ]

                for day in sorted(set(candidate_days)):
                    candidate = date(year, month, day)

                    if start_date <= candidate <= end_date:
                        dates.append(candidate)

                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1

        elif pattern.frequency in {"weekly", "biweekly", "custom"}:
            if pattern.interval_days is None:
                return []

            interval = int(round(pattern.interval_days))

            if interval <= 0:
                return []

            anchor = date.fromisoformat(pattern.last_observed_date)
            candidate = anchor

            while candidate < start_date:
                candidate += timedelta(days=interval)

            while candidate <= end_date:
                dates.append(candidate)
                candidate += timedelta(days=interval)

        return [
            CashflowEvent(
                date=event_date,
                category=pattern.category,
                amount=(
                    pattern.typical_amount
                    if event_type == "income"
                    else -pattern.typical_amount
                ),
                event_type=event_type,
                source_key=pattern.source_key,
            )
            for event_date in dates
        ]
