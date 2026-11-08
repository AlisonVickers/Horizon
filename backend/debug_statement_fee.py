
import pandas as pd
from app.data.account_store import AccountStore

with AccountStore(61163) as store:
    transactions = store.get_transactions()

fees = transactions[
    transactions["operation"] == "bank fee"
].copy()

fees["date"] = pd.to_datetime(fees["date"])
fees = fees.sort_values("date")
fees["month"] = fees["date"].dt.to_period("M")

month_numbers = [
    month.year * 12 + month.month
    for month in fees["month"]
]

print("Fee transactions:", len(fees))
print("Unique months:", fees["month"].nunique())
print("Duplicate months:", fees["month"].duplicated().any())
print("All consecutive:", all(
    current - previous == 1
    for previous, current in zip(
        month_numbers, month_numbers[1:]
    )
))
print("All month-end:", fees["date"].dt.is_month_end.all())
print("Last fee:", fees["date"].max())
print("Latest transaction:", pd.to_datetime(transactions["date"]).max())
