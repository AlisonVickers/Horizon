
from app.data.account_store import AccountStore

ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    result = store.query("""
        SELECT
            date,
            operation,
            purpose,
            signed_amount
        FROM transactions
        WHERE operation = 'bank fee'
        ORDER BY date DESC
        LIMIT 15
    """)

    print("\nRECENT STATEMENT FEES")
    print(result.to_string(index=False))
