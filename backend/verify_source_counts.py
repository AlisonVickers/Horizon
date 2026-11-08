
from pathlib import Path
import duckdb

root = Path(__file__).resolve().parent.parent / "data"

csv_file = root / "raw/data/transactions.csv"
parquet_file = root / "parquet/transactions.parquet"

conn = duckdb.connect(":memory:")

try:
    csv_count = conn.execute(
        "SELECT COUNT(*) FROM read_csv_auto(?)",
        [str(csv_file)]
    ).fetchone()[0]

    parquet_count = conn.execute(
        "SELECT COUNT(*) FROM read_parquet(?)",
        [str(parquet_file)]
    ).fetchone()[0]

    print(f"Original CSV records: {csv_count:,}")
    print(f"Parquet records:      {parquet_count:,}")

    if csv_count == parquet_count:
        print("PASS: Record counts match.")
    else:
        print("FAIL: Record counts differ!")

finally:
    conn.close()
