
from datetime import date

from app.services.cashflow_forecast import CashflowEvent
from app.services.projected_balance import ProjectedBalanceService


def test_projected_balance_calculation():
    events = [
        CashflowEvent(
            date=date(2026, 1, 14),
            category="income",
            amount=1000.00,
            event_type="income",
            source_key="pay",
        ),
        CashflowEvent(
            date=date(2026, 1, 5),
            category="rent",
            amount=-400.00,
            event_type="expense",
            source_key="rent",
        ),
    ]

    result = ProjectedBalanceService().project(
        starting_balance=500.00,
        events=events,
    )

    assert result["starting_balance"] == 500.00
    assert result["projected_ending_balance"] == 1100.00
    assert result["lowest_projected_balance"] == 100.00

    assert len(result["timeline"]) == 2

    assert result["timeline"][0]["date"] == "2026-01-05"
    assert result["timeline"][0]["projected_balance"] == 100.00

    assert result["timeline"][1]["date"] == "2026-01-14"
    assert result["timeline"][1]["projected_balance"] == 1100.00


def test_projected_balance_with_no_events():
    result = ProjectedBalanceService().project(
        starting_balance=250.00,
        events=[],
    )

    assert result["projected_ending_balance"] == 250.00
    assert result["lowest_projected_balance"] == 250.00
    assert result["timeline"] == []


def test_projected_balance_rejects_missing_balance():
    try:
        ProjectedBalanceService().project(
            starting_balance=None,
            events=[],
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
