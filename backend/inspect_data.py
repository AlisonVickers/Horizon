
from pathlib import Path
import duckdb

DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "raw"
    / "data"
)

conn = duckdb.connect(":memory:")

# Ignore macOS AppleDouble metadata files
files = sorted(
    file for file in DATA_DIR.glob("*.csv")
    if not file.name.startswith("._")
)

if not files:
    raise FileNotFoundError(
        f"No CSV files found in {DATA_DIR}"
    )

for file in files:
    print(f"\n{'=' * 60}")
    print(f"DATASET: {file.name}")
    print("=" * 60)

    schema = conn.execute(
        "DESCRIBE SELECT * FROM read_csv_auto(?)",
        [str(file)]
    ).fetchall()

    for column in schema:
        print(f"{column[0]}: {column[1]}")

    count = conn.execute(
        "SELECT COUNT(*) FROM read_csv_auto(?)",
        [str(file)]
    ).fetchone()[0]

    print(f"Total rows: {count:,}")

conn.close()
