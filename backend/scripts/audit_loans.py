
from pathlib import Path

import pandas as pd


DATA = Path(__file__).resolve().parents[2] / "data/raw/data"
CUTOFF = pd.Timestamp("2025-12-31")

loans = pd.read_csv(DATA / "loans.csv")
loans["loan_start"] = pd.to_datetime(loans["loan_start"])

running = 0
inconsistencies = []
finished_before_term_end = []

for _, loan in loans.iterrows():
    status = str(loan["status"]).strip()
    start = loan["loan_start"]
    duration = int(loan["duration_months"])
    end = start + pd.DateOffset(months=duration)

    active_by_status = status in {"C", "D"}
    active_by_dates = start <= CUTOFF < end

    if active_by_status:
        running += 1
        if not active_by_dates:
            inconsistencies.append({
                "loan_id": int(loan["loan_id"]),
                "account_id": int(loan["account_id"]),
                "status": status,
                "estimated_end": str(end.date()),
            })
    elif active_by_dates:
        finished_before_term_end.append(int(loan["loan_id"]))

print("\n=== FULL LOAN AUDIT ===")
print("Total loans:", len(loans))
print("Running loans (C/D):", running)
print("Running loan date inconsistencies:", len(inconsistencies))
print("Finished before scheduled term end:", len(finished_before_term_end))

for issue in inconsistencies[:20]:
    print("REVIEW:", issue)

if inconsistencies:
    raise SystemExit(1)

print("PASS: Running loan dates are consistent with the cutoff.")
