
from app.data.account_store import AccountStore

ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    income = store.query("""
        SELECT
            direction,
            operation,
            purpose,
            COUNT(*) AS transaction_count,
            ROUND(AVG(amount), 2) AS average_amount,
            ROUND(SUM(amount), 2) AS total_amount
        FROM transactions
        WHERE signed_amount > 0
        GROUP BY direction, operation, purpose
        ORDER BY transaction_count DESC
    """)

    print("\nINCOMING TRANSACTION CATEGORIES")
    print(income.to_string(index=False))

    recent = store.query("""
        SELECT
            date,
            operation,
            purpose,
            amount
        FROM transactions
        WHERE signed_amount > 0
        ORDER BY date DESC
        LIMIT 20
    """)

    print("\n20 MOST RECENT INCOMING TRANSACTIONS")
    print(recent.to_string(index=False))
