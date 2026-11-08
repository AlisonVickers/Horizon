
from app.data.account_store import AccountStore
from app.services.expense_detector import ExpenseDetector

ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    transactions = store.get_transactions()

detector = ExpenseDetector()
patterns = detector.detect(transactions)

print("\nDETECTED RECURRING EXPENSES")

if not patterns:
    print("No qualifying recurring expenses found.")

for pattern in patterns:
    print(pattern)
