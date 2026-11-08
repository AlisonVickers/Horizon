
from datetime import date

from app.services.multi_month_forecast import MultiMonthForecastService


def test_returns_three_months():
    result = MultiMonthForecastService().forecast(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    )

    assert result["status"] == "estimated"
    assert len(result["months"]) == 3

    assert [m["month"] for m in result["months"]] == [
        "2026-01",
        "2026-02",
        "2026-03",
    ]


def test_balance_continues_between_months():
    result = MultiMonthForecastService().forecast(
        account_id=61163,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    )

    months = result["months"]

    assert (
        months[1]["opening_balance"]
        == months[0]["closing_balance"]
    )

    assert (
        months[2]["opening_balance"]
        == months[1]["closing_balance"]
    )


def test_unanchored_forecast_is_unavailable():
    result = MultiMonthForecastService().forecast(
        account_id=61163,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 3, 31),
    )

    assert result["status"] == "unavailable"
    assert result["months"] == []


def test_rejects_invalid_dates():
    service = MultiMonthForecastService()

    try:
        service.forecast(
            account_id=61163,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 1, 1),
        )
        assert False, "Expected ValueError"
    except ValueError:
        pass
