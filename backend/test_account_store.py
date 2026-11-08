
from pathlib import Path

import duckdb

from app.data.account_store import AccountStore


ACCOUNT_ID = 61163

DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "parquet"
)

with duckdb.connect(":memory:") as source:
    with AccountStore(ACCOUNT_ID) as store:

        for table in AccountStore.TABLES:
            # Number of rows in the original dataset
            file_path = DATA_DIR / f"{table}.parquet"

            expected = source.execute(
                """
                SELECT COUNT(*)
                FROM read_parquet(?)
                WHERE account_id = ?
                """,
                [str(file_path), ACCOUNT_ID],
            ).fetchone()[0]

            # Number of rows loaded into AccountStore
            result = store.query(
                f"""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(*) FILTER (
                        WHERE account_id != ?
                    ) AS foreign_rows
                FROM {table}
                """,
                [ACCOUNT_ID],
            )

            actual = int(result.iloc[0]["total_rows"])
            foreign = int(result.iloc[0]["foreign_rows"])

            print(
                f"{table}: "
                f"{actual} rows "
                f"(expected {expected})"
            )

            assert actual == expected, (
                f"Row count mismatch in {table}"
            )

            assert foreign == 0, (
                f"Account isolation failed in {table}"
            )

        # A valid test account must have transactions.
        transaction_count = store.query(
            "SELECT COUNT(*) AS total FROM transactions"
        ).iloc[0]["total"]

        assert transaction_count > 0, (
            "Selected account has no transactions"
        )

print("\nAccount isolation test passed!")
