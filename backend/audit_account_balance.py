
from app.data.account_store import AccountStore

ACCOUNT_ID = 61163

with AccountStore(ACCOUNT_ID) as store:
    result = store.query("""
        SELECT
            date,
            transaction_id,
            signed_amount,
            balance
        FROM transactions
        ORDER BY date DESC, transaction_id DESC
        LIMIT 10
    """)

    print("\nLATEST TRANSACTION BALANCES")
    print(result.to_string(index=False))

    monthly = store.query("""
        SELECT
            month,
            money_in,
            money_out,
            month_end_balance
        FROM monthly_summary
        ORDER BY month DESC
        LIMIT 6
    """)

    print("\nLATEST MONTHLY SUMMARIES")
    print(monthly.to_string(index=False))
