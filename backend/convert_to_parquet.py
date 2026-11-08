
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "raw" / "data"
DEST = ROOT / "data" / "parquet"

DATASETS = (
    "monthly_summary",
    "transactions",
    "loans",
    "standing_orders",
)

DEST.mkdir(parents=True, exist_ok=True)

with duckdb.connect(":memory:") as conn:
    for name in DATASETS:
        source_file = SOURCE / f"{name}.csv"
        output_file = DEST / f"{name}.parquet"

        if not source_file.is_file():
            raise FileNotFoundError(source_file)

        conn.execute(
            """
            COPY (
                SELECT *
                FROM read_csv_auto(?)
            )
            TO ?
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """,
            [str(source_file), str(output_file)],
        )

        count = conn.execute(
            "SELECT COUNT(*) FROM read_parquet(?)",
            [str(output_file)],
        ).fetchone()[0]

        print(f"{name}: {count:,} rows converted")

print("Parquet conversion complete!")
