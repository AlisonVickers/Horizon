
from pathlib import Path
import duckdb

DATA = Path(__file__).resolve().parent.parent / "data"

csv_path = DATA / "raw" / "data" / "transactions.csv"
parquet_path = DATA / "parquet" / "transactions.parquet"

conn = duckdb.connect(":memory:")

try:
    # DuckDB requires file paths directly in CREATE VIEW.
    # Escape single quotes so paths are safe in SQL strings.
    csv_sql_path = str(csv_path).replace("'", "''")
    parquet_sql_path = str(parquet_path).replace("'", "''")

    conn.execute(f"""
        CREATE TEMP VIEW original AS
        SELECT *
        FROM read_csv_auto('{csv_sql_path}')
    """)

    conn.execute(f"""
        CREATE TEMP VIEW converted AS
        SELECT *
        FROM read_parquet('{parquet_sql_path}')
    """)

    result = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM original) AS csv_rows,
            (SELECT COUNT(*) FROM converted) AS parquet_rows,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT * FROM original
                    EXCEPT ALL
                    SELECT * FROM converted
                )
            ) AS missing_or_changed_rows,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT * FROM converted
                    EXCEPT ALL
                    SELECT * FROM original
                )
            ) AS extra_or_changed_rows
    """).fetchone()

    print("\nTRANSACTION INTEGRITY CHECK")
    print(f"CSV rows:             {result[0]:,}")
    print(f"Parquet rows:         {result[1]:,}")
    print(f"Missing/changed rows: {result[2]:,}")
    print(f"Extra/changed rows:   {result[3]:,}")

    if result[2] == 0 and result[3] == 0:
        print("PASS: Transaction values match.")
    else:
        print("REVIEW: Differences detected.")

finally:
    conn.close()
