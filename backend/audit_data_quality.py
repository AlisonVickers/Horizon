
from pathlib import Path

import duckdb

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "parquet"
    / "transactions.parquet"
)

conn = duckdb.connect(":memory:")

try:
    result = conn.execute(
        """
        SELECT
            COUNT(*) AS total_transactions,

            COUNT(*) FILTER (
                WHERE transaction_id IS NULL
            ) AS missing_transaction_ids,

            COUNT(*) - COUNT(DISTINCT transaction_id)
                AS duplicate_transaction_ids,

            COUNT(*) FILTER (
                WHERE account_id IS NULL
            ) AS missing_account_ids,

            COUNT(*) FILTER (
                WHERE date IS NULL
            ) AS missing_dates,

            COUNT(*) FILTER (
                WHERE amount IS NULL
                   OR signed_amount IS NULL
            ) AS missing_amounts,

            COUNT(*) FILTER (
                WHERE amount < 0
            ) AS negative_amounts,

            COUNT(*) FILTER (
                WHERE
                    (direction = 'credit (money in)'
                     AND signed_amount < 0)
                    OR
                    (direction = 'debit (money out)'
                     AND signed_amount > 0)
            ) AS direction_mismatches,

            MIN(date) AS earliest_transaction,
            MAX(date) AS latest_transaction

        FROM read_parquet(?)
        """,
        [str(DATA_FILE)],
    ).fetchdf()

    print("\nTRANSACTION DATA QUALITY AUDIT")
    print(result.to_string(index=False))

finally:
    conn.close()
