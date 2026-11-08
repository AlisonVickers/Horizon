
from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "parquet"

conn = duckdb.connect(":memory:")

try:
    result = conn.execute(
        """
        WITH monthly AS (
            SELECT
                account_id,
                month,
                money_in,
                money_out,
                month_end_balance,
                LAG(month_end_balance) OVER (
                    PARTITION BY account_id
                    ORDER BY month
                ) AS previous_balance
            FROM read_parquet(?)
        )
        SELECT
            COUNT(*) AS months_checked,
            COUNT(*) FILTER (
                WHERE previous_balance IS NOT NULL
            ) AS comparable_months,
            COUNT(*) FILTER (
                WHERE previous_balance IS NOT NULL
                  AND ABS(
                      previous_balance
                      + money_in
                      - money_out
                      - month_end_balance
                  ) > 0.01
            ) AS mismatched_months
        FROM monthly
        """,
        [str(BASE_DIR / "monthly_summary.parquet")],
    ).fetchdf()

    print("\nMONTHLY BALANCE RECONCILIATION")
    print(result.to_string(index=False))

finally:
    conn.close()
