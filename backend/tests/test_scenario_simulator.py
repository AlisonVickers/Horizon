
from datetime import date

import pytest

from app.services.scenario_simulator import ScenarioSimulatorService


def test_trip_expense_reduces_allowance():
    result = ScenarioSimulatorService().simulate(
        starting_balance=5000,
        events=[],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=0,
        scenario_type="one_time_expense",
        amount=1200,
        scenario_date=date(2026, 1, 10),
    )

    assert result["status"] == "estimated"
    assert result["simulated"]["safe_to_spend"] == 3300.0
    assert result["change_in_lowest_balance"] == -1200.0


def test_income_reduction_changes_projection():
    result = ScenarioSimulatorService().simulate(
        starting_balance=2000,
        events=[
            {
                "date": "2026-01-15",
                "amount": 3000,
                "event_type": "income",
            }
        ],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=0,
        scenario_type="income_reduction",
        income_reduction_percent=20,
    )

    assert result["status"] == "estimated"
    assert result["scenario_events"][0]["amount"] == 2400.0


def test_rejects_negative_expense():
    with pytest.raises(ValueError):
        ScenarioSimulatorService().simulate(
            starting_balance=5000,
            events=[],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            monthly_variable_outflow=0,
            scenario_type="one_time_expense",
            amount=-100,
            scenario_date=date(2026, 1, 10),
        )


def test_rejects_invalid_expense_date():
    with pytest.raises(ValueError):
        ScenarioSimulatorService().simulate(
            starting_balance=5000,
            events=[],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            monthly_variable_outflow=0,
            scenario_type="one_time_expense",
            amount=100,
            scenario_date=date(2026, 2, 1),
        )


def test_original_events_remain_unchanged():
    events = [{
        "date": "2026-01-15",
        "amount": 3000,
        "event_type": "income",
    }]

    ScenarioSimulatorService().simulate(
        starting_balance=2000,
        events=events,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        monthly_variable_outflow=0,
        scenario_type="income_reduction",
        income_reduction_percent=20,
    )

    assert events[0]["amount"] == 3000
