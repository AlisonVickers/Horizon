
from app.data.account_store import AccountStore
from app.services.income_detector import IncomeDetector

ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    transactions = store.get_transactions()

detector = IncomeDetector()
patterns = detector.detect(transactions)

print("\nDETECTED INCOME PATTERNS")

if not patterns:
    print("No qualifying recurring transfers found.")

for pattern in patterns:
    print(pattern)
