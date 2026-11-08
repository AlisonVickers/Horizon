
from app.data.account_store import AccountStore

ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    result = store.query("""
        SELECT
            date,
            operation,
            purpose,
            partner_bank,
            partner_account,
            signed_amount
        FROM transactions
        WHERE signed_amount > 0
          AND operation = 'transfer in from another bank'
        ORDER BY date DESC
        LIMIT 24
    """)

    print("\nRECENT INCOMING TRANSFERS")
    print(result.to_string(index=False))
