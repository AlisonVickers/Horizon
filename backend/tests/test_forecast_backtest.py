
from app.data.account_store import AccountStore
from app.services.forecast_backtest import ForecastBacktestService


def test_backtest_returns_reliability():
    with AccountStore(61163) as store:
        transactions = store.get_transactions()

    result = ForecastBacktestService().evaluate(
        transactions,
        test_months=6,
    )

    assert result["status"] == "evaluated"
    assert result["months_evaluated"] == 6
    assert result["mean_absolute_error"] >= 0
    assert result["reliability"] in {
        "high", "moderate", "low"
    }
