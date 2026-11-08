
from app.data.account_store import AccountStore

ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    result = store.query("""
        SELECT
            COALESCE(purpose, operation) AS payment_type,
            partner_bank,
            partner_account,
            COUNT(*) AS transactions,
            MIN(date) AS first_payment,
            MAX(date) AS last_payment
        FROM transactions
        WHERE signed_amount < 0
          AND operation IN (
              'transfer out to another bank',
              'bank fee'
          )
        GROUP BY
            operation,
            purpose,
            partner_bank,
            partner_account
        ORDER BY last_payment DESC
    """)

    print("\nRECURRING PAYMENT ACTIVITY")
    print(result.to_string(index=False))
