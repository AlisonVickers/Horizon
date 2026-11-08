
from pathlib import Path
import duckdb

file_path = (
    Path(__file__).resolve().parent.parent
    / "data/parquet/monthly_summary.parquet"
)

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
                LAG(month) OVER (
                    PARTITION BY account_id
                    ORDER BY month
                ) AS previous_month,
                LAG(month_end_balance) OVER (
                    PARTITION BY account_id
                    ORDER BY month
                ) AS previous_balance
            FROM read_parquet(?)
        )
        SELECT
            account_id,
            previous_month,
            month,
            previous_balance,
            money_in,
            money_out,
            month_end_balance,
            ROUND(
                previous_balance
                + money_in
                - money_out
                - month_end_balance,
                2
            ) AS difference
        FROM monthly
        WHERE previous_balance IS NOT NULL
          AND ABS(
              previous_balance
              + money_in
              - money_out
              - month_end_balance
          ) > 0.01
        ORDER BY ABS(
            previous_balance
            + money_in
            - money_out
            - month_end_balance
        ) DESC
        LIMIT 15
        """,
        [str(file_path)],
    ).fetchdf()

    print("\nLARGEST BALANCE MISMATCHES")
    print(result.to_string(index=False))

finally:
    conn.close()
