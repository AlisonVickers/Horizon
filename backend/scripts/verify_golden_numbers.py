
from pathlib import Path

import pandas as pd

from app.services.financial_profile import FinancialProfileService
from app.services.runway_calculator import RunwayCalculator


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "raw" / "data"
CUTOFF = pd.Timestamp("2025-12-31")

monthly = pd.read_csv(DATA / "monthly_summary.csv")
loans = pd.read_csv(DATA / "loans.csv")

monthly["month"] = monthly["month"].astype(str)
loans["loan_start"] = pd.to_datetime(loans["loan_start"])

# Reproducible selection:
# - account 61163
# - accounts with running loans
# - accounts without running loans
running_ids = loans.loc[
    loans["status"].isin(["C", "D"]), "account_id"
].tolist()

all_ids = sorted(monthly["account_id"].unique().tolist())

selected = list(dict.fromkeys(
    [61163] +
    running_ids[:5] +
    [a for a in all_ids if a not in running_ids][:10]
))[:10]


def expected_profile(account_id):
    rows = (
        monthly.loc[monthly["account_id"] == account_id]
        .sort_values("month")
    )

    if rows.empty:
        raise ValueError(f"No monthly history for {account_id}")

    fixed_by_month = (
        rows["household_bills"]
        + rows["insurance"]
        + rows["loan_payments"]
    )

    account_loans = loans.loc[
        loans["account_id"] == account_id
    ]

    loan_payment = 0.0
    loan_warnings = []

    for _, loan in account_loans.iterrows():
        if loan["status"] not in ("C", "D"):
            continue

        end_date = loan["loan_start"] + pd.DateOffset(
            months=int(loan["duration_months"])
        )

        if loan["loan_start"] <= CUTOFF < end_date:
            loan_payment += float(loan["monthly_payment"])
        else:
            loan_warnings.append(
                f"Loan {loan['loan_id']} has running status "
                f"but dates do not cover cutoff"
            )

    return {
        "typical_monthly_income": float(rows["money_in"].median()),
        "typical_monthly_spending": float(rows["money_out"].median()),
        "typical_fixed_costs": float(fixed_by_month.median()),
        "household_bills": float(rows["household_bills"].median()),
        "savings_buffer": float(
            rows.tail(6)["avg_daily_balance"].mean()
        ),
        "active_loan_payment": loan_payment,
    }, loan_warnings


def check_value(actual, expected):
    # Allow 1 cent for rounding differences.
    return abs(actual - expected) <= 0.011


failures = []
warnings = []

for account_id in selected:
    expected, loan_warnings = expected_profile(account_id)
    actual = FinancialProfileService().build(int(account_id))

    warnings.extend(
        f"Account {account_id}: {message}"
        for message in loan_warnings
    )

    print(f"\nACCOUNT {account_id}")

    for metric, expected_value in expected.items():
        actual_value = actual[metric]
        passed = check_value(actual_value, expected_value)

        print(
            f"{'PASS' if passed else 'FAIL'} "
            f"{metric}: expected={expected_value:.2f}, "
            f"actual={actual_value:.2f}"
        )

        if not passed:
            failures.append((account_id, metric))

    # Independent runway calculation from raw CSV metrics.
    buffer = expected["savings_buffer"]
    income = expected["typical_monthly_income"]
    spending = expected["typical_monthly_spending"]
    bills = expected["household_bills"]

    def expected_runway(b, s, i):
        if b <= 0:
            return 0.0
        if s <= i:
            return 120.0
        return min(b / (s - i), 120.0)

    scenarios = {
        "baseline": (buffer, spending, income),
        "EI_55_percent": (buffer, spending, income * 0.55),
        "bills_up_15_percent": (
            buffer, spending + 0.15 * bills, income
        ),
        "combined": (
            buffer, spending + 0.15 * bills, income * 0.55
        ),
        "one_month_repair": (
            buffer - spending, spending, income
        ),
    }

    for name, (b, s, i) in scenarios.items():
        reference = expected_runway(b, s, i)

        result = RunwayCalculator.calculate(
            buffer=b,
            monthly_spending=s,
            monthly_income=i,
        )

        # Compare unrounded reference to 1-decimal service output.
        passed = abs(result["runway_months"] - reference) <= 0.051

        print(
            f"{'PASS' if passed else 'FAIL'} "
            f"runway/{name}: "
            f"reference={reference:.3f}, "
            f"actual={result['runway_months']:.1f}"
        )

        if not passed:
            failures.append((account_id, f"runway/{name}"))

print("\n=== VALIDATION SUMMARY ===")
print(f"Accounts checked: {len(selected)}")
print(f"Profile comparisons: {len(selected) * 6}")
print(f"Runway comparisons: {len(selected) * 5}")
print(f"Failures: {len(failures)}")
print(f"Loan date warnings: {len(warnings)}")

for warning in warnings:
    print("WARNING:", warning)

for failure in failures:
    print("FAILURE:", failure)

if failures or warnings:
    raise SystemExit(1)

print("PASS: All checked values match the independent reference.")
