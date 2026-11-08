
from collections import Counter
from pathlib import Path

import duckdb

from app.services.transaction_classifier import TransactionClassifier

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "parquet"
    / "transactions.parquet"
)

classifier = TransactionClassifier()
categories = Counter()
unknown_examples = Counter()

conn = duckdb.connect(":memory:")

try:
    transactions = conn.execute(
        """
        SELECT operation, purpose, direction
        FROM read_parquet(?)
        """,
        [str(DATA_FILE)],
    )

    while True:
        batch = transactions.fetchmany(10000)

        if not batch:
            break

        for operation, purpose, direction in batch:
            result = classifier.classify({
                "operation": operation,
                "purpose": purpose,
                "direction": direction,
            })

            categories[result.category] += 1

            if result.category == "unknown":
                unknown_examples[
                    (str(operation), str(purpose), str(direction))
                ] += 1

finally:
    conn.close()

print("\nALL-ACCOUNT CLASSIFICATION COVERAGE")

total = sum(categories.values())
recognized = total - categories["unknown"]

print(f"Total transactions: {total:,}")
print(f"Recognized: {recognized:,}")
print(f"Unknown: {categories['unknown']:,}")

if total:
    print(f"Recognition coverage: {recognized / total:.2%}")

print("\nCATEGORY COUNTS")
for category, count in categories.most_common():
    print(f"{category}: {count:,}")

print("\nMOST COMMON UNKNOWN PATTERNS")
for pattern, count in unknown_examples.most_common(15):
    print(f"{pattern}: {count:,}")

assert total > 0
print("\nClassification audit completed!")
