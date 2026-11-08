
from datetime import date

from app.data.account_store import AccountStore
from app.services.income_detector import IncomeDetector
from app.services.expense_detector import ExpenseDetector
from app.services.cashflow_forecast import CashflowForecastService


ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    transactions = store.get_transactions()

income_patterns = IncomeDetector().detect(transactions)
expense_patterns = ExpenseDetector().detect(transactions)

print("\nACCOUNT:", ACCOUNT_ID)
print("Detected income patterns:", len(income_patterns))
print("Detected expense patterns:", len(expense_patterns))

forecast = CashflowForecastService().forecast(
    income_patterns=income_patterns,
    expense_patterns=expense_patterns,
    start_date=date(2026, 1, 1),
    end_date=date(2026, 1, 31),
)

print("\nHORIZON CASHFLOW CALENDAR — JANUARY 2026")
print("(Historical-pattern simulation, not live banking data)\n")

for event in forecast:
    print(
        f"{event.date} | "
        f"{event.event_type.upper():7} | "
        f"{event.category:28} | "
        f"${event.amount:,.2f}"
    )

print("\nTotal predicted income:", round(
    sum(event.amount for event in forecast if event.amount > 0), 2
))

print("Total predicted recurring expenses:", round(
    sum(abs(event.amount) for event in forecast if event.amount < 0), 2
))
