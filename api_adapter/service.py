from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from functools import cached_property
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.runway import RunwayCalculator  # noqa: E402
from app.services.cashflow_forecast import CashflowEvent, CashflowForecastService  # noqa: E402
from app.services.dashboard_service import DashboardService # noqa: E402
from app.services.expense_detector import ExpenseDetector # noqa: E402
from app.services.income_detector import IncomeDetector # noqa: E402
from app.services.projected_balance import ProjectedBalanceService # noqa: E402
from app.services.scenario_simulator import ScenarioSimulatorService # noqa: E402

FIXED_COLUMNS = ("household_bills", "insurance", "loan_payments")
EVERYDAY_COLUMNS = ("cash_withdrawals_genuine", "card_withdrawals", "transfers_out_other")
CATEGORY_LABELS = {
    "household_bills": "Household bills",
    "insurance": "Insurance",
    "loan_payments": "Loan payments",
    "bank_fees": "Bank fees",
    "cash_withdrawals_genuine": "Cash withdrawals",
    "card_withdrawals": "Card purchases",
    "transfers_out_other": "Other transfers out",
}
MONTH_NAMES = {name.lower(): number for number, name in enumerate(
    ("", "January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December")
) if name}
AMOUNT_PATTERN = re.compile(
    r"(?<![\w.])(?:\$|cad\s*)?(\d[\d,]*(?:\.\d{1,2})?)(?![\w.])",
    re.IGNORECASE,
)
WORD_AMOUNT_PATTERN = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
    r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand)\s+(?:dollars?|bucks?)\b",
    re.IGNORECASE,
)
WORD_AMOUNTS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100, "thousand": 1000,
}
DATE_PATTERN = re.compile(
    r"\b("
    r"(?:20\d{2}-\d{1,2}-\d{1,2})|"
    r"(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)(?:\s+20\d{2})?"
    r")\b",
    re.IGNORECASE,
)
RELATIVE_DATE_PATTERN = re.compile(r"\b(?:next|this) month\b", re.IGNORECASE)


class AccountNotFoundError(LookupError):
    pass


def _add_month(day: date, months: int = 1) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def _label(value: Any, fallback: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return fallback
    return str(value)


class AdapterAccountService:
    """Translate frontend requests into account numbers the judges can verify.

    Profile numbers follow the challenge formulas exactly:
    I = median money_in, F = median(bills + insurance + loan), S = median money_out,
    B = mean avg_daily_balance over the last 6 months, H = median household_bills,
    P = loan monthly_payment when the loan status is C or D.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.state_path = self.data_dir.parent / "astro_state.json"
        self._budget_requests, self._budget_preferences = self._load_state()
        self.scenario_simulator = ScenarioSimulatorService()

    def _load_state(self) -> tuple[dict[int, list[str]], dict[int, dict[str, Any]]]:
        if not self.state_path.exists():
            return {}, {}
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"[Astro] Could not load persistent state: {error}", flush=True)
            return {}, {}
        if not isinstance(raw, dict):
            raise ValueError("Astro state must be a JSON object")
        # Migrate the original account_id -> prompt-list format.
        if "requests" not in raw:
            requests_raw, preferences_raw = raw, {}
        else:
            requests_raw = raw.get("requests", {})
            preferences_raw = raw.get("preferences", {})
        if not isinstance(requests_raw, dict) or not isinstance(preferences_raw, dict):
            raise ValueError("Astro state requests and preferences must be JSON objects")
        state = {}
        for account_id, prompts in requests_raw.items():
            try:
                parsed_account_id = int(account_id)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Astro state has an invalid account ID: {account_id}") from error
            if not isinstance(prompts, list):
                raise ValueError(f"Astro state for account {account_id} must be a list")
            state[parsed_account_id] = [str(prompt) for prompt in prompts]
        preferences = {}
        for account_id, preference in preferences_raw.items():
            try:
                parsed_account_id = int(account_id)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Astro preferences have an invalid account ID: {account_id}") from error
            if not isinstance(preference, dict):
                raise ValueError(f"Astro preference for account {account_id} must be an object")
            preferences[parsed_account_id] = preference
        return state, preferences

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = {
            "requests": {
                str(account_id): prompts
                for account_id, prompts in self._budget_requests.items()
            },
            "preferences": {
                str(account_id): preference
                for account_id, preference in self._budget_preferences.items()
            },
        }
        temporary_path = self.state_path.with_suffix(".tmp")
        try:
            temporary_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
            temporary_path.replace(self.state_path)
        except OSError as error:
            print(f"[Astro] Could not save persistent state: {error}", flush=True)
            raise ValueError("Astro could not save the budget state") from error

    # ------------------------------------------------------------------ data
    @cached_property
    def _accounts(self) -> pd.DataFrame:
        for candidate in (self.data_dir / "accounts.parquet", self.data_dir.parent / "raw" / "data" / "accounts.csv"):
            if candidate.exists():
                return pd.read_parquet(candidate) if candidate.suffix == ".parquet" else pd.read_csv(candidate)
        raise FileNotFoundError("accounts dataset not found")

    @cached_property
    def _tables(self) -> dict[str, pd.DataFrame]:
        tables = {}
        for name in ("transactions", "monthly_summary", "loans", "standing_orders"):
            tables[name] = pd.read_parquet(self.data_dir / f"{name}.parquet")
        tables["transactions"]["date"] = pd.to_datetime(tables["transactions"]["date"])
        tables["monthly_summary"] = tables["monthly_summary"].sort_values(["account_id", "month"])
        return tables

    def _load(self, account_id: int) -> dict[str, pd.DataFrame]:
        if account_id <= 0 or not (self._accounts["account_id"] == account_id).any():
            raise AccountNotFoundError(f"Account {account_id} was not found")
        tables = {name: table[table["account_id"] == account_id].copy() for name, table in self._tables.items()}
        if tables["transactions"].empty or tables["monthly_summary"].empty:
            raise AccountNotFoundError(f"Account {account_id} has no usable data")
        return tables

    @cached_property
    def _peer_profiles(self) -> pd.DataFrame:
        summary = self._tables["monthly_summary"].copy()
        summary["fixed"] = summary[list(FIXED_COLUMNS)].sum(axis=1)
        summary["everyday"] = summary[list(EVERYDAY_COLUMNS)].sum(axis=1)
        grouped = summary.groupby("account_id")
        peers = grouped[["money_in", "money_out", "fixed", "everyday", "household_bills"]].median()
        peers["buffer"] = grouped["avg_daily_balance"].apply(lambda values: values.tail(6).mean())
        return peers

    # --------------------------------------------------------------- profile
    def profile(self, tables: dict[str, pd.DataFrame]) -> dict[str, float]:
        summary = tables["monthly_summary"].sort_values("month")
        loans = tables["loans"]
        active_loans = loans[loans["status"].astype(str).str.upper().isin(["C", "D"])]
        everyday = summary[list(EVERYDAY_COLUMNS)].sum(axis=1)
        return {
            "income": float(summary["money_in"].median()),
            "fixed_costs": float(summary[list(FIXED_COLUMNS)].sum(axis=1).median()),
            "spending": float(summary["money_out"].median()),
            "buffer": float(summary["avg_daily_balance"].tail(6).mean()),
            "household_bills": float(summary["household_bills"].median()),
            "loan_payment": float(active_loans["monthly_payment"].sum()) if not active_loans.empty else 0.0,
            "everyday_spending": float(everyday.median()),
        }

    def _percentile(self, column: str, value: float) -> float:
        peers = self._peer_profiles[column].dropna()
        return float((peers < value).mean() * 100) if len(peers) else 50.0

    def benchmarks(self, account_id: int, profile: dict[str, float]) -> list[dict[str, Any]]:
        peers = self._peer_profiles
        rows = [
            ("Monthly income", "money_in", profile["income"], True),
            ("Monthly spending", "money_out", profile["spending"], False),
            ("Everyday spending", "everyday", profile["everyday_spending"], False),
            ("Cash buffer", "buffer", profile["buffer"], True),
        ]
        output = []
        for label, column, value, higher_is_better in rows:
            median = float(peers[column].median())
            diff = ((value - median) / median * 100) if median else 0.0
            output.append({
                "label": label,
                "you": value,
                "peer_median": median,
                "difference_pct": diff,
                "percentile": self._percentile(column, value),
                "is_good": diff >= 0 if higher_is_better else diff <= 0,
            })
        return output

    # -------------------------------------------------------------- timeline
    def timeline(self, transactions: pd.DataFrame) -> dict[str, Any]:
        current = transactions["date"].max().date()
        credits = transactions[
            transactions["direction"].astype(str).str.lower().str.contains("credit")
            & (transactions["operation"].astype(str).str.lower() != "interest")
        ]
        if credits.empty:
            raise ValueError("Account data does not contain an income date")
        payday = credits["date"].max().date()
        next_payday = _add_month(payday)
        while next_payday <= current:
            next_payday = _add_month(next_payday)
        # Heena's income detector: if it finds a recurring income, use its forecast date.
        income_patterns = IncomeDetector().detect(transactions)
        pay_period_frequency = income_patterns[0].frequency if income_patterns else "monthly"
        if income_patterns:
            forecast = CashflowForecastService().forecast(
                income_patterns, [], current + timedelta(days=1), current + timedelta(days=62))
            if forecast:
                next_payday = forecast[0].date
        period_length = (next_payday - payday).days
        debits = transactions[
            transactions["direction"].astype(str).str.lower().str.contains("debit")
            & (transactions["date"].dt.date > payday)
            & (transactions["date"].dt.date <= current)
        ]
        spent = float(debits["amount"].abs().sum())
        expected = float(credits.sort_values("date").iloc[-1]["amount"])
        pay_period_days = []
        for offset in range(period_length + 1):
            day = payday + timedelta(days=offset)
            day_transactions = transactions[transactions["date"].dt.date == day]
            amount = float(day_transactions["signed_amount"].sum()) if not day_transactions.empty else 0.0
            labels = []
            if day == payday:
                labels.append("Last payday")
            if day == current:
                labels.append("Today")
            if day == next_payday:
                labels.append("Next payday")
            pay_period_days.append({
                "date": day.isoformat(),
                "label": " · ".join(labels),
                "amount": amount,
            })
        return {
            "current_date": current.isoformat(),
            "last_payday": payday.isoformat(),
            "next_payday": next_payday.isoformat(),
            "pay_period_frequency": pay_period_frequency,
            "pay_period_days": pay_period_days,
            "days_until_payday": max((next_payday - current).days, 0),
            "pay_period_day": max(min((current - payday).days + 1, period_length), 1),
            "pay_period_length": period_length,
            "expected_deposit": expected,
            "spent_since_payday": spent,
            "flexible_spending_remaining": max(expected - spent, 0.0),
            "overspent_since_payday": max(spent - expected, 0.0),
        }

    def _standing_orders(self, tables: dict[str, pd.DataFrame], current: date) -> list[dict[str, Any]]:
        """Upcoming bills from Heena's ExpenseDetector + CashflowForecastService (next 45 days)."""
        patterns = [
            pattern for pattern in ExpenseDetector().detect(tables["transactions"])
            if pattern.typical_amount >= 20  # hide tiny statement fees from the bill list
        ]
        events = CashflowForecastService().forecast(
            [], patterns, current + timedelta(days=1), current + timedelta(days=45))
        output, seen = [], set()
        for event in events:
            if event.source_key in seen:
                continue
            seen.add(event.source_key)
            output.append({
                "name": event.category.capitalize(),
                "purpose": event.category.capitalize(),
                "amount": abs(float(event.amount)),
                "due_date": event.date.isoformat(),
                "key": event.source_key,
            })
        if not output:  # fall back to the bank's standing-order table
            for _, order in tables["standing_orders"].sort_values("amount", ascending=False).iterrows():
                output.append({
                    "name": _label(order["purpose"], "Standing order").capitalize(),
                    "purpose": _label(order["purpose"], "Standing order").capitalize(),
                    "amount": float(order["amount"]), "due_date": None, "key": str(order["order_id"]),
                })
        return sorted(output, key=lambda row: (row["due_date"] or "9999", -row["amount"]))

    # ------------------------------------------------------------- endpoints
    @staticmethod
    def _runway(profile: dict[str, float], *, income: float | None = None, spending: float | None = None) -> float:
        result = RunwayCalculator.calculate(
            max(profile["buffer"], 0.0),
            0.0,
            max(profile["spending"] if spending is None else spending, 0.0),
            max(profile["income"] if income is None else income, 0.0),
        )
        return result.runway_months

    @staticmethod
    def _balance_history(summary: pd.DataFrame) -> list[dict[str, Any]]:
        history = []
        for _, row in summary.sort_values("month").tail(12).iterrows():
            balance = row["month_end_balance"]
            if pd.isna(balance):
                continue
            history.append({
                "month": str(row["month"]),
                "balance": float(balance),
            })
        return history

    def home(self, account_id: int) -> dict[str, Any]:
        tables = self._load(account_id)
        transactions = tables["transactions"].sort_values(["date", "transaction_id"], ascending=False)
        summary_table = tables["monthly_summary"].sort_values("month")
        summary = summary_table.iloc[-1]
        timeline = self.timeline(tables["transactions"])
        current = date.fromisoformat(timeline["current_date"])
        next_payday = date.fromisoformat(timeline["next_payday"])
        orders = self._standing_orders(tables, current)
        profile = self.profile(tables)
        target = round(profile["spending"] * 6, -2)
        return {
            "account_id": account_id,
            **timeline,
            "summary_month": str(summary["month"]),
            "balance": float(summary["month_end_balance"]),
            "baseline_runway": self._runway(profile),
            "balance_history": self._balance_history(summary_table),
            "profile": profile,
            "latest_month": {
                "income": float(summary["money_in"]),
                "spending": float(summary["money_out"]),
                "flexible_spending_left": max(float(summary["money_in"] - summary["money_out"]), 0),
            },
            "upcoming_expenses": orders,
            "due_before_payday": sum(
                order["amount"] for order in orders
                if order["due_date"] is None or date.fromisoformat(order["due_date"]) <= next_payday
            ),
            "savings_goal": {
                "name": "6-month safety net",
                "target": target,
                "current": profile["buffer"],
                "progress_pct": min(profile["buffer"] / target * 100, 100) if target else 0,
                "rationale": "Six months of your typical spending, so a job loss on EI does not empty the account.",
            },
            "benchmarks": self.benchmarks(account_id, profile),
            "standing_orders": orders,
            "recent_transactions": [
                {
                    "date": row["date"].date().isoformat(),
                    "direction": row["direction"],
                    "purpose": _label(row["purpose"], str(row["operation"])),
                    "amount": float(row["amount"]),
                    "signed_amount": float(row["signed_amount"]),
                    "balance": float(row["balance"]),
                }
                for _, row in transactions.head(10).iterrows()
            ],
        }

    def plans(self, account_id: int) -> dict[str, Any]:
        tables = self._load(account_id)
        profile = self.profile(tables)
        target = round(profile["spending"] * 6, -2)
        current = max(profile["buffer"], 0.0)
        remaining = max(target - current, 0.0)
        monthly_saving = max(profile["income"] - profile["spending"], 0.0)
        months_to_goal = remaining / monthly_saving if monthly_saving > 0 else None
        goal_plan = {
            "name": "6-month safety net",
            "target": target,
            "current": current,
            "progress_pct": min(current / target * 100, 100) if target else 0.0,
            "monthly_saving": monthly_saving,
            "months_to_goal": months_to_goal,
            "steps": [
                "Keep essential bills and loan payments covered first.",
                "Move the monthly saving amount to a separate safety buffer after payday.",
                "Review the target whenever income or recurring spending changes.",
            ],
        }

        baseline_runway = self._runway(profile, income=0.0)
        everyday_cut = min(profile["everyday_spending"], profile["spending"] * 0.2)
        fixed_cut = min(profile["fixed_costs"] * 0.1, profile["spending"])
        actions = [
            {
                "title": "Pause everyday spending",
                "detail": f"Temporarily remove about ${everyday_cut:,.0f}/month of cash and card spending.",
                "spending": max(profile["spending"] - everyday_cut, 0.0),
            },
            {
                "title": "Reduce fixed commitments",
                "detail": f"Target about ${fixed_cut:,.0f}/month through payment relief or lower recurring costs.",
                "spending": max(profile["spending"] - fixed_cut, 0.0),
            },
        ]
        backup_actions = []
        for action in actions:
            action_runway = self._runway(profile, income=0.0, spending=action["spending"])
            backup_actions.append({
                "title": action["title"],
                "detail": action["detail"],
                "runway_months": action_runway,
                "months_gained": max(action_runway - baseline_runway, 0.0),
            })
        backup_actions.sort(key=lambda action: action["months_gained"], reverse=True)
        combined_spending = max(profile["spending"] - everyday_cut - fixed_cut, 0.0)
        combined_runway = self._runway(profile, income=0.0, spending=combined_spending)

        return {
            "account_id": account_id,
            "profile": profile,
            "goal_plan": goal_plan,
            "backup_plan": {
                "trigger": "If income stopped today, your current buffer would cover essential spending for",
                "runway_without_actions": baseline_runway,
                "runway_with_top_actions": combined_runway,
                "actions": backup_actions,
            },
        }

    def calendar(self, account_id: int) -> dict[str, Any]:
        tables = self._load(account_id)
        transactions = tables["transactions"]
        timeline = self.timeline(transactions)
        current = date.fromisoformat(timeline["current_date"])
        window = transactions[transactions["date"].dt.date > _add_month(current, -12)]
        events = [
            {
                "date": row["date"].date().isoformat(),
                "type": "income" if "credit" in str(row["direction"]).lower() else "expense",
                "label": _label(row["purpose"], str(row["operation"])).capitalize(),
                "amount": float(row["amount"]),
                "source": "transaction",
            }
            for _, row in window.sort_values("date", ascending=False).iterrows()
            if str(row["operation"]).lower() != "interest"
        ]
        for order in self._standing_orders(tables, current):
            events.append({
                "date": order["due_date"], "type": "standing_order", "label": order["name"],
                "amount": order["amount"], "source": "standing_order",
            })
        events.append({
            "date": timeline["next_payday"], "type": "payday", "label": "Expected payday",
            "amount": timeline["expected_deposit"], "source": "forecast",
        })

        summary = tables["monthly_summary"].sort_values("month").tail(12)
        peer_everyday = float(self._peer_profiles["everyday"].median())
        months = []
        for _, row in summary.iterrows():
            fixed = float(sum(row[column] for column in FIXED_COLUMNS) + row["bank_fees"])
            everyday = float(sum(row[column] for column in EVERYDAY_COLUMNS))
            months.append({
                "month": str(row["month"]),
                "income": float(row["money_in"]),
                "bills": fixed,
                "everyday": everyday,
                "spending": float(row["money_out"]),
                "saved": float(row["money_in"] - row["money_out"]),
                "everyday_vs_peers_pct": (everyday - peer_everyday) / peer_everyday * 100 if peer_everyday else 0.0,
            })

        debits = transactions[transactions["direction"].astype(str).str.lower().str.contains("debit")]
        daily = debits.groupby(debits["date"].dt.date)["amount"].sum()
        last_seven = [
            {"date": (current - timedelta(days=offset)).isoformat(),
             "amount": float(daily.get(current - timedelta(days=offset), 0.0))}
            for offset in range(6, -1, -1)
        ]
        return {
            "account_id": account_id, "as_of": timeline["current_date"], **timeline,
            "events": events, "months": months, "last_seven_days": last_seven,
            "peer_everyday_median": peer_everyday,
        }

    def _budget_plan(
        self,
        account_id: int,
        tables: dict[str, pd.DataFrame],
    ) -> list[dict[str, Any]]:
        profile = self.profile(tables)
        latest = tables["monthly_summary"].sort_values("month").iloc[-1]
        everyday_now = float(sum(latest[column] for column in EVERYDAY_COLUMNS))
        everyday_limit = round(profile["everyday_spending"] * 0.9, -1)
        fixed_now = float(sum(latest[column] for column in FIXED_COLUMNS))
        leftover = profile["income"] - profile["fixed_costs"] - everyday_limit
        # Half of what is left after bills; if nothing is left, a starter goal of 5% of income.
        save_target = max(round(max(leftover, 0) * 0.5, -1), round(profile["income"] * 0.05, -1))
        saved_now = max(float(latest["money_in"] - latest["money_out"]), 0.0)
        plan = [
            {
                "name": "Everyday spending",
                "monthly_savings": everyday_now,
                "monthly_limit": everyday_limit,
                "rationale": "10% under your typical cash and card spending. Cutting here adds runway without touching bills.",
            },
            {
                "name": "Fixed bills and loan",
                "monthly_savings": fixed_now,
                "monthly_limit": max(round(profile["fixed_costs"], -1), 1.0),
                "rationale": "Bills, insurance and loan payments. These are locked in, so the plan protects them first.",
            },
            {
                "name": "Monthly savings",
                "monthly_savings": saved_now,
                "monthly_limit": max(save_target, 1.0),
                "rationale": (
                    "Half of what is left after bills and the everyday limit goes to your safety net."
                    if leftover > 0 else
                    "Money is tight after bills, so start small: 5% of your income goes to your safety net."
                ),
            },
        ]
        preference = self._budget_preferences.get(account_id)
        if preference and preference.get("amount") is not None:
            amount = float(preference["amount"])
            cadence = str(preference.get("cadence", "month"))
            periods_per_month = {
                "week": 52 / 12,
                "biweekly": 26 / 12,
                "month": 1,
                "paycheck": 1,
            }.get(cadence, 1)
            monthly_target = amount * periods_per_month
            plan.append({
                "name": f"Requested savings ({cadence})",
                "monthly_savings": 0.0,
                "monthly_limit": monthly_target,
                "rationale": (
                    f"Your requested target is ${amount:,.0f} per {cadence}. "
                    f"That is approximately ${monthly_target:,.0f} per month."
                ),
            })
        return plan

    def budgets(self, account_id: int) -> dict[str, Any]:
        tables = self._load(account_id)
        summary = tables["monthly_summary"].sort_values("month").iloc[-1]
        return {
            "account_id": account_id,
            "month": str(summary["month"]),
            **self.timeline(tables["transactions"]),
            "total_income": float(summary["money_in"]),
            "total_spending": float(summary["money_out"]),
            "categories": [
                {"name": CATEGORY_LABELS[name], "amount": float(summary[name])}
                for name in CATEGORY_LABELS if float(summary[name]) > 0
            ],
            "goals": self._budget_plan(account_id, tables) if self._budget_requests.get(account_id) else [],
        }

    @staticmethod
    def _requested_amount(prompt: str) -> float | None:
        without_dates = DATE_PATTERN.sub("", prompt)
        word_match = WORD_AMOUNT_PATTERN.search(without_dates)
        if word_match:
            words = word_match.group(0).lower().replace(" dollars", "").replace(" dollar", "")
            words = words.replace(" bucks", "").replace(" buck", "").split()
            total = 0
            current = 0
            for word in words:
                value = WORD_AMOUNTS[word]
                if value in (100, 1000):
                    current = max(current, 1) * value
                    total += current
                    current = 0
                else:
                    current += value
            return float(total + current)
        for match in AMOUNT_PATTERN.finditer(without_dates):
            value = float(match.group(1).replace(",", ""))
            prefix = without_dates[max(0, match.start() - 4):match.start()].lower()
            is_currency = "$" in prefix or "cad" in prefix
            if not is_currency and 1900 <= value <= 2099:
                continue
            return value
        return None

    @staticmethod
    def _question_kind(prompt: str, amount: float | None, requested_date: date | None) -> str:
        text = prompt.lower()
        if re.search(r"\b(afford|buy|purchase|cost)\b", text) or (
            amount is not None and re.search(r"\bspend\b", text)
        ):
            return "purchase"
        if amount is not None and any(word in text for word in ("save", "saving", "set aside")):
            return "savings_target"
        if requested_date is not None and re.search(
            r"\b(balance|forecast|projection|projected|outlook)\b", text
        ):
            return "forecast"
        if re.search(r"\b(bills|fixed costs|expenses|spending|spend|income|earn|salary|buffer|savings|balance|summary|overview)\b", text):
            return "summary"
        return "other"

    @staticmethod
    def _is_budget_request(prompt: str) -> bool:
        text = prompt.lower()
        return (
            "budget" in text
            or bool(re.search(r"\b(create|make|build|set up|setup)\b.{0,30}\b(plan|budget)\b", text))
        )

    @staticmethod
    def _budget_cadence(prompt: str) -> str:
        text = prompt.lower()
        if "biweekly" in text or "every two weeks" in text:
            return "biweekly"
        if "weekly" in text or "per week" in text:
            return "week"
        if "per paycheck" in text or "each paycheck" in text or "every paycheck" in text:
            return "paycheck"
        return "month"

    @staticmethod
    def _display_date(value: date) -> str:
        return value.strftime("%B ") + str(value.day) + value.strftime(", %Y")

    @staticmethod
    def _requested_date(prompt: str, current: date) -> date | None:
        relative = RELATIVE_DATE_PATTERN.search(prompt)
        if relative:
            month = _add_month(current.replace(day=1)) if relative.group().lower() == "next month" else current
            return month
        match = DATE_PATTERN.search(prompt)
        if not match:
            return None
        value = match.group(1).lower()
        if re.fullmatch(r"20\d{2}-\d{1,2}-\d{1,2}", value):
            return date.fromisoformat(value)
        parts = value.split()
        month = MONTH_NAMES[parts[0]]
        year = int(parts[1]) if len(parts) == 2 else current.year
        if len(parts) == 1 and month <= current.month:
            year += 1
        return date(year, month, 1)

    def _question_calculation(
        self,
        account_id: int,
        prompt: str,
        tables: dict[str, pd.DataFrame],
        profile: dict[str, float],
    ) -> tuple[str, dict[str, Any], list[str]]:
        amount = self._requested_amount(prompt)
        timeline = self.timeline(tables["transactions"])
        current = date.fromisoformat(timeline["current_date"])
        requested_date = self._requested_date(prompt, current)
        question_kind = self._question_kind(prompt, amount, requested_date)
        trace = ["account_profile", "income_detector", "expense_detector", "payday_calculator"]
        details: dict[str, Any] = {
            "requested_amount": amount,
            "requested_date": requested_date.isoformat() if requested_date else None,
            "data_as_of": current.isoformat(),
            "next_payday": timeline["next_payday"],
            "days_until_payday": timeline["days_until_payday"],
            "question_kind": question_kind,
        }

        if question_kind == "summary":
            text = prompt.lower()
            if re.search(r"\b(bills|fixed costs)\b", text):
                message = f"Your typical fixed costs are ${profile['fixed_costs']:,.0f} per month, including household bills, insurance, and loan payments."
            elif re.search(r"\b(spending|spend|expenses)\b", text):
                message = f"You typically spend ${profile['spending']:,.0f} per month based on your account history."
            elif re.search(r"\b(income|earn|salary)\b", text):
                message = f"Your typical income is ${profile['income']:,.0f} per month based on your account history."
            else:
                message = ""
            gap = profile["spending"] - profile["income"]
            return (
                message or f"You typically bring in ${profile['income']:,.0f} and spend "
                f"${profile['spending']:,.0f} a month, with a ${profile['buffer']:,.0f} buffer."
                + (
                    f" That is about ${gap:,.0f} more spending than income each month."
                    if gap > 0 else " You usually have money left over."
                ),
                details,
                trace,
            )

        if question_kind == "other":
            return (
                "I can't answer that question from the available financial calculations. "
                "Try asking about income, spending, a budget, or the cost of a planned purchase.",
                details,
                trace,
            )

        if question_kind == "purchase" and amount is None:
            return (
                "How much will the purchase or trip cost? Please include the amount and timing "
                "in your question so I can estimate its impact.",
                details,
                trace,
            )

        if requested_date is None:
            requested_date = date.fromisoformat(timeline["next_payday"])
            details["requested_date"] = requested_date.isoformat()

        latest_month = str(tables["monthly_summary"].sort_values("month").iloc[-1]["month"])
        year, month = (int(part) for part in latest_month.split("-")[:2])
        balance_date = date(year, month, monthrange(year, month)[1])
        forecast_start = balance_date + timedelta(days=1)
        if requested_date < forecast_start:
            raise ValueError(
                f"The requested date must be on or after {forecast_start.isoformat()}, "
                "the start of the available forecast"
            )
        dashboard = DashboardService().get_dashboard(
            account_id=account_id,
            start_date=forecast_start,
            end_date=requested_date,
        )
        trace.append("balance_projection")
        projection = dashboard["projected_balance"]
        if projection is None:
            raise ValueError("A future balance projection is unavailable for this account")

        planned_cost = amount if question_kind == "purchase" else 0.0
        projection_events = [
            CashflowEvent(
                date=date.fromisoformat(event["date"]),
                category=event["category"],
                amount=float(event["amount"]),
                event_type=event["event_type"],
                source_key=f"forecast:{index}",
            )
            for index, event in enumerate(dashboard["events"])
        ]
        base_projection = ProjectedBalanceService().project(
            starting_balance=dashboard["balance"]["historical_month_end_balance"],
            events=projection_events,
        )
        projected_balance_before = base_projection["projected_ending_balance"]
        if planned_cost:
            projection_events.append(CashflowEvent(
                date=requested_date,
                category="Astro one-off purchase",
                amount=-planned_cost,
                event_type="one_off_expense",
                source_key="astro_one_off_purchase",
            ))
        projection = ProjectedBalanceService().project(
            starting_balance=dashboard["balance"]["historical_month_end_balance"],
            events=projection_events,
        )
        projected_balance = projection["projected_ending_balance"]
        balance_after = projected_balance
        details["projection_scope"] = (
            "detected_recurring_events_plus_requested_purchase"
            if planned_cost else "detected_recurring_events_only"
        )
        details.update({
            "projected_balance_before_purchase": projected_balance_before,
            "projected_balance_after_purchase": balance_after,
            "safe_to_spend": dashboard["safe_to_spend"],
            "payday_spending": dashboard["payday_spending"],
        })
        if dashboard["payday_spending"]["status"] == "estimated":
            trace.append("payday_spending")

        runway = RunwayCalculator.calculate(
            max(projected_balance, 0.0),
            0.0,
            profile["spending"],
            profile["income"],
        )
        details["runway_after_purchase_months"] = runway.runway_months
        trace.append("runway_calculator")

        if question_kind == "forecast":
            message = (
                f"By {self._display_date(requested_date)}, your recurring-income and recurring-expense "
                f"projection is ${projected_balance:,.0f}, before variable spending. "
                f"Your estimated runway is {runway.runway_months:,.1f} months."
            )
        elif question_kind == "purchase" and balance_after >= 0:
            message = (
                f"A ${amount:,.0f} purchase on {self._display_date(requested_date)} would leave about "
                f"${balance_after:,.0f} in the projected balance, before variable spending. "
                f"Your estimated runway after it would be {runway.runway_months:,.1f} months. "
                "This estimate does not establish whether the purchase is affordable."
            )
        elif question_kind == "purchase":
            message = (
                f"A ${amount:,.0f} purchase on {self._display_date(requested_date)} would put the projected "
                f"balance about ${abs(balance_after):,.0f} below zero before variable spending. "
                f"Your estimated runway after it would be {runway.runway_months:,.1f} months."
            )
        else:
            message = (
                f"By {self._display_date(requested_date)}, the projected balance is about "
                f"${balance_after:,.0f} before setting aside your ${amount:,.0f} savings target "
                f"and before variable spending. Your estimated runway would be "
                f"{runway.runway_months:,.1f} months."
            )
        if RELATIVE_DATE_PATTERN.search(prompt):
            message += (
                f" The timing is based on your latest account data from "
                f"{self._display_date(current)}"
                + (" and assumes the first day of next month." if "next month" in prompt.lower() else ".")
            )
        details["conclusion"] = "informational"
        return message, details, trace

    def scenario(self, account_id: int, shocks: list[dict[str, float]]) -> dict[str, Any]:
        tables = self._load(account_id)
        profile = self.profile(tables)
        latest_month = str(
            tables["monthly_summary"].sort_values("month").iloc[-1]["month"]
        )
        year, month = (int(part) for part in latest_month.split("-")[:2])
        start_date = date(year, month, monthrange(year, month)[1]) + timedelta(days=1)
        end_date = _add_month(start_date, 3) - timedelta(days=1)
        dashboard = DashboardService().get_dashboard(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
        )
        if (
            dashboard["projected_balance"] is None
            or dashboard["variable_spending"]["status"] != "estimated"
        ):
            raise ValueError("Scenario projection is unavailable for this account")

        events = [
            {
                "date": event["date"],
                "amount": event["amount"],
                "event_type": event["event_type"],
                "category": event["category"],
            }
            for event in dashboard["events"]
        ]
        simulated = self.scenario_simulator.simulate_shocks(
            starting_balance=dashboard["balance"]["historical_month_end_balance"],
            events=events,
            start_date=start_date,
            end_date=end_date,
            monthly_variable_outflow=dashboard["variable_spending"]["conservative_monthly_estimate"],
            shocks=shocks,
        )
        months = max((end_date - start_date).days / 30.44, 1)
        income = sum(
            event["amount"] for event in simulated["scenario_events"]
            if event["amount"] > 0
        ) / months
        spending = (
            sum(
                -event["amount"] for event in simulated["scenario_events"]
                if event["amount"] < 0
            ) / months
            + simulated["monthly_variable_outflow"]
        )
        buffer = dashboard["balance"]["historical_month_end_balance"]
        one_off = simulated["one_off_costs"]
        result = RunwayCalculator.calculate(max(buffer, 0.0), one_off, spending, income)
        timeline = self.timeline(tables["transactions"])
        return {
            "account_id": account_id, "current_date": timeline["current_date"],
            "next_payday": timeline["next_payday"], "days_until_payday": timeline["days_until_payday"],
            "runway_months": result.runway_months, "income_after": income,
            "spending_after": spending, "loan_payment": profile["loan_payment"], "buffer": buffer,
            "one_off_costs": one_off, "income_after_shock": income,
            "spending_after_shock": spending, "gap": result.gap, "runway": result.runway_months,
            "profile": profile,
        }

    def assistant(self, account_id: int, prompt: str) -> dict[str, Any]:
        tables = self._load(account_id)
        profile = self.profile(tables)
        is_budget_request = self._is_budget_request(prompt)
        if is_budget_request:
            self._budget_requests.setdefault(account_id, []).append(prompt)
            amount = self._requested_amount(prompt)
            self._budget_preferences[account_id] = {
                "amount": amount,
                "cadence": self._budget_cadence(prompt),
            }
            self._save_state()
            plan = self._budget_plan(account_id, tables)
            requested_goal = plan[-1] if amount is not None else None
            savings_target = (
                f"${requested_goal['monthly_limit']:,.0f}/month"
                if requested_goal
                else f"${plan[2]['monthly_limit']:,.0f}/month"
            )
            message = (
                f"Done. I built a plan from your activity: keep everyday spending under "
                f"${plan[0]['monthly_limit']:,.0f}/month and aim to save "
                f"{savings_target}. "
                "See it on the Budget tab."
            )
            calculation_data = {
                "budget_plan": plan,
                "requested_savings_amount": amount,
                "requested_savings_cadence": self._budget_cadence(prompt),
            }
            trace = ["account_profile", "budget_planner"]
        else:
            message, calculation_data, trace = self._question_calculation(
                account_id, prompt, tables, profile
            )
        calculation_data.setdefault("conclusion", "budget_created" if is_budget_request else "informational")
        if calculation_data.get("question_kind") == "purchase" and calculation_data["requested_amount"] is None:
            ai_message, gemini_status = None, "not_needed"
        else:
            ai_message, gemini_status = self._ask_gemini(
                prompt, profile, message, calculation_data
            )
        if ai_message:
            message, trace = ai_message, trace + ["gemini"]
        else:
            trace.append(f"gemini_{gemini_status}")
        return {
            "message": message,
            "data": {
                "account_id": account_id,
                "prompt": prompt,
                "gemini_status": gemini_status,
                **profile,
                **calculation_data,
            },
            "tool_trace": trace,
        }

    @staticmethod
    def _numeric_values(value: str) -> set[float]:
        return {
            float(match.replace(",", ""))
            for match in re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", value)
        }

    @classmethod
    def _valid_gemini_text(
        cls,
        text: str,
        profile: dict[str, float],
        engine_answer: str,
        calculation_data: dict[str, Any],
    ) -> str | None:
        try:
            response = json.loads(text)
        except json.JSONDecodeError:
            return None
        if (
            not isinstance(response, dict)
            or set(response) != {"answer", "conclusion"}
            or not isinstance(response.get("answer"), str)
        ):
            return None
        answer = response["answer"].strip()
        if not answer or len(answer) > 1000 or any(
            ord(char) < 32 and char not in "\n\t" for char in answer
        ):
            return None
        if response.get("conclusion") != calculation_data.get("conclusion"):
            return None
        allowed = cls._numeric_values(
            engine_answer
            + json.dumps(profile)
            + json.dumps(calculation_data, default=str)
        )
        if not cls._numeric_values(answer).issubset(allowed):
            return None
        return answer

    @classmethod
    def _ask_gemini(
        cls,
        prompt: str,
        profile: dict[str, float],
        engine_answer: str,
        calculation_data: dict[str, Any],
    ) -> tuple[str | None, str]:
        """Astro's voice via Gemini; all financial facts come from the engine."""
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            return None, "disabled"
        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        if model != "gemini-3.5-flash":
            print(f"[Astro] Unsupported GEMINI_MODEL {model}; using gemini-3.5-flash", flush=True)
            model = "gemini-3.5-flash"
        fallback_model = "gemini-3.1-flash"
        instructions = (
            "You are Astro, a friendly Canadian banking assistant in the Horizon app. "
            "Return JSON with exactly two fields: answer (a 2-3 sentence string) and conclusion. "
            "Use the supplied conclusion exactly. Use ONLY the numbers in the account profile, engine answer, "
            "and verified calculation details; "
            "never invent figures or change the engine's conclusion. Explain the specific customer question "
            "using the verified calculation details. Preserve the engine's limitations, assumptions and dates. "
            "Amounts are CAD unless explicitly stated otherwise."
        )
        body = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "generationConfig": {"responseMimeType": "application/json"},
            "contents": [{"role": "user", "parts": [{"text": (
                f"Account profile: {json.dumps({k: round(v, 2) for k, v in profile.items()})}\n"
                f"Engine answer: {engine_answer}\nCustomer question: {prompt}"
                f"\nCalculation details: {json.dumps(calculation_data, default=str)}"
            )}]}],
        }
        try:
            import httpx
            models = [model]
            if fallback_model != model:
                models.append(fallback_model)
            for index, candidate_model in enumerate(models):
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent",
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=body, timeout=20,
                )
                if response.status_code == 200:
                    parts = response.json()["candidates"][0]["content"]["parts"]
                    text = "".join(part.get("text", "") for part in parts).strip()
                    validated_answer = cls._valid_gemini_text(
                        text, profile, engine_answer, calculation_data
                    )
                    if not validated_answer:
                        print("[Astro] Gemini response failed validation", flush=True)
                        return None, "rejected"
                    return validated_answer, "used"
                transient = response.status_code == 429 or response.status_code >= 500
                if not transient or index == len(models) - 1:
                    print(f"[Astro] Gemini error {response.status_code}: {response.text[:300]}", flush=True)
                    return None, "error"
                print(
                    f"[Astro] Gemini model {candidate_model} returned {response.status_code}; "
                    f"trying {models[index + 1]}",
                    flush=True,
                )
            return None, "error"
        except Exception as error:  # fall back to the engine's own answer
            print(f"[Astro] Gemini call failed: {error}", flush=True)
            return None, "error"
