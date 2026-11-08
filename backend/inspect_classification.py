
from collections import Counter

from app.data.account_store import AccountStore
from app.services.transaction_classifier import TransactionClassifier

ACCOUNT_ID = 61163

classifier = TransactionClassifier()

with AccountStore(ACCOUNT_ID) as store:
    transactions = store.get_transactions()

    categories = Counter()
    unknown_examples = Counter()

    for transaction in transactions.to_dict("records"):
        result = classifier.classify(transaction)

        categories[result.category] += 1

        if result.category == "unknown":
            key = (
                str(transaction.get("operation")),
                str(transaction.get("purpose")),
            )
            unknown_examples[key] += 1

    print(f"\nTotal transactions: {len(transactions)}")
    print(f"Classified transactions: {sum(categories.values())}")

    print("\nCATEGORY COUNTS")
    for category, count in categories.most_common():
        print(f"{category}: {count}")

    print("\nUNKNOWN TRANSACTION EXAMPLES")
    for (operation, purpose), count in unknown_examples.most_common(15):
        print(
            f"Operation: {operation} | "
            f"Purpose: {purpose} | "
            f"Count: {count}"
        )

    assert sum(categories.values()) == len(transactions)
    print("\nAll transactions accounted for!")
