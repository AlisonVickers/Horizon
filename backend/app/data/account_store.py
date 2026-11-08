
from pathlib import Path

import duckdb


class AccountStore:
    """Isolated in-memory financial data for one account."""

    TABLES = (
        "monthly_summary",
        "transactions",
        "loans",
        "standing_orders",
    )

    def __init__(self, account_id: int):
        self.account_id = int(account_id)

        self.data_dir = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "parquet"
        )

        self.conn = duckdb.connect(":memory:")

        try:
            self._load_account()
            self._validate_account()
        except Exception:
            self.close()
            raise

    def _load_account(self):
        for table in self.TABLES:
            file_path = self.data_dir / f"{table}.parquet"

            if not file_path.exists():
                raise FileNotFoundError(
                    f"Missing Parquet file: {file_path}"
                )

            self.conn.execute(
                f"""
                CREATE TEMP TABLE {table} AS
                SELECT *
                FROM read_parquet(?)
                WHERE account_id = ?
                """,
                [str(file_path), self.account_id],
            )

    def query(self, sql: str, params=None):
        """For trusted backend code only."""
        if self.conn is None:
            raise RuntimeError("AccountStore is closed")

        return self.conn.execute(
            sql, params or []
        ).fetchdf()

    def get_transactions(self):
        return self.query(
            "SELECT * FROM transactions ORDER BY date DESC"
        )

    def get_monthly_summary(self):
        return self.query(
            "SELECT * FROM monthly_summary ORDER BY month DESC"
        )

    def get_loans(self):
        return self.query("SELECT * FROM loans")

    def get_standing_orders(self):
        return self.query("SELECT * FROM standing_orders")




    def _validate_account(self):
        """Check account existence, not transaction count."""

        accounts_file = (
            self.data_dir.parent
            / "raw"
            / "data"
            / "accounts.csv"
        )

        if not accounts_file.exists():
            raise FileNotFoundError(
                f"Missing accounts dataset: {accounts_file}"
            )

        result = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM read_csv_auto(?)
            WHERE account_id = ?
            """,
            [str(accounts_file), self.account_id],
        ).fetchone()

        if result[0] == 0:
            raise ValueError(
                f"Account {self.account_id} does not exist"
            )

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
