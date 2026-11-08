
import pandas as pd

from app.services.recurrence_analyzer import RecurrenceAnalyzer


def test_weekly_pattern():
    dates = pd.Series(
        pd.date_range("2025-03-07", periods=8, freq="7D")
    )

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is not None
    assert result.frequency == "weekly"


def test_biweekly_pattern():
    dates = pd.Series(
        pd.date_range("2025-03-07", periods=8, freq="14D")
    )

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is not None
    assert result.frequency == "biweekly"


def test_custom_interval():
    dates = pd.Series(
        pd.date_range("2025-03-07", periods=8, freq="10D")
    )

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is not None
    assert result.frequency == "custom"
    assert result.interval_days == 10.0


def test_irregular_pattern():
    dates = pd.Series(pd.to_datetime([
        "2025-01-01",
        "2025-01-04",
        "2025-01-19",
        "2025-02-07",
        "2025-03-13",
    ]))

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is None
def test_month_end_pattern():
    dates = pd.Series(
        pd.date_range(
            start="2025-01-31",
            periods=6,
            freq="ME",
        )
    )

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is not None
    assert result.frequency == "monthly"
    assert result.observations == 6
def test_monthly_payments_near_month_end():
    dates = pd.Series(pd.to_datetime([
        "2025-01-29",
        "2025-02-26",
        "2025-03-28",
        "2025-04-29",
        "2025-05-29",
        "2025-06-27",
    ]))

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is not None
    assert result.frequency == "monthly"
    assert result.observations == 6
def test_semimonthly_pattern():
    dates = pd.Series(pd.to_datetime([
        "2025-01-01",
        "2025-01-15",
        "2025-02-01",
        "2025-02-15",
        "2025-03-01",
        "2025-03-15",
        "2025-04-01",
        "2025-04-15",
    ]))

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is not None
    assert result.frequency == "semimonthly"
    assert result.observations == 8

def test_semimonthly_calendar_days():
    dates = pd.Series(pd.to_datetime([
        "2025-01-01", "2025-01-15",
        "2025-02-01", "2025-02-15",
        "2025-03-01", "2025-03-15",
        "2025-04-01", "2025-04-15",
    ]))

    result = RecurrenceAnalyzer().analyze(dates)

    assert result is not None
    assert result.frequency == "semimonthly"
    assert result.days_of_month == (1, 15)
