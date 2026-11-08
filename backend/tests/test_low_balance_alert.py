
import pytest

from app.services.low_balance_alert import LowBalanceAlertService


def test_alert_when_balance_drops_below_buffer():
    projection = {
        "starting_balance": 800.00,
        "timeline": [
            {
                "date": "2026-01-05",
                "projected_balance": 350.00,
            },
            {
                "date": "2026-01-14",
                "projected_balance": 1350.00,
            },
        ],
    }

    result = LowBalanceAlertService().analyze(
        projection,
        safety_buffer=500.00,
    )

    assert result["status"] == "warning"
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["date"] == "2026-01-05"
    assert result["alerts"][0]["shortfall"] == 150.00


def test_no_alert_when_balance_stays_above_buffer():
    projection = {
        "starting_balance": 1000.00,
        "timeline": [
            {
                "date": "2026-01-05",
                "projected_balance": 700.00,
            },
        ],
    }

    result = LowBalanceAlertService().analyze(
        projection,
        safety_buffer=500.00,
    )

    assert result["status"] == "ok"
    assert result["alerts"] == []


def test_unavailable_projection():
    result = LowBalanceAlertService().analyze(
        None,
        safety_buffer=500.00,
    )

    assert result["status"] == "unavailable"
    assert result["alerts"] == []


def test_negative_safety_buffer_is_rejected():
    with pytest.raises(ValueError):
        LowBalanceAlertService().analyze(
            None,
            safety_buffer=-100.00,
        )
