
from decimal import Decimal

from app.services.financial_profile import FinancialProfileService
from app.services.resilience_scenario import ResilienceScenarioService


ACCOUNT_IDS = [61163, 55447, 22715, 57243, 66505,
               90623, 20133, 20143, 20160, 20176]


def reference_runway(buffer, spending, income, one_off=0):
    left = buffer - one_off
    gap = spending - income

    if left <= 0:
        return Decimal("0")
    if gap <= 0:
        return Decimal("120")
    return min(left / gap, Decimal("120"))


scenarios = [
    ("baseline", 1, 0, 0),
    ("job_loss", 0.55, 0, 0),
    ("bills_up", 1, 15, 0),
    ("combined", 0.55, 15, 0),
    ("repair", 1, 0, 2000),
    ("combined_repair", 0.55, 15, 2000),
]

failures = []

for account_id in ACCOUNT_IDS:
    profile = FinancialProfileService().build(account_id)

    I = Decimal(str(profile["typical_monthly_income"]))
    S = Decimal(str(profile["typical_monthly_spending"]))
    H = Decimal(str(profile["household_bills"]))
    B = Decimal(str(profile["savings_buffer"]))

    for name, rate, bills_pct, repair in scenarios:
        income_after = I * Decimal(str(rate))
        spending_after = S + H * Decimal(str(bills_pct)) / 100

        expected = reference_runway(
            B, spending_after, income_after, Decimal(str(repair))
        )

        actual = ResilienceScenarioService().simulate(
            profile,
            income_replacement_rate=rate,
            bills_increase_percent=bills_pct,
            one_off_cost=repair,
        )

        result = Decimal(str(actual["shocked"]["runway_months"]))

        passed = abs(result - expected) <= Decimal("0.051")

        if not passed:
            failures.append((account_id, name, str(expected), str(result)))

print("\n=== SCENARIO VALIDATION ===")
print("Accounts:", len(ACCOUNT_IDS))
print("Scenarios per account:", len(scenarios))
print("Comparisons:", len(ACCOUNT_IDS) * len(scenarios))
print("Failures:", len(failures))

for failure in failures:
    print("FAIL:", failure)

if failures:
    raise SystemExit(1)

print("PASS: Scenario calculations match the independent reference.")
