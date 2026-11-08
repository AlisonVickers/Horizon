from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from functools import cached_property
import json
import os
from pathlib import Path
import sys
from typing import Any

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.runway import RunwayCalculator  # noqa: E402
from app.services.cashflow_forecast import CashflowForecastService  # noqa: E402
from app.services.dashboard_service import DashboardService  # noqa: E402
from app.services.expense_detector import ExpenseDetector  # noqa: E402
from app.services.income_detector import IncomeDetector  # noqa: E402
from app.services.scenario_simulator import ScenarioSimulatorService  # noqa: E402

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

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self._budget_requests: dict[int, list[str]] = {}
        self.scenario_simulator = ScenarioSimulatorService()

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
        patterns = [
            pattern for pattern in ExpenseDetector().detect(tables["transactions"])
            if pattern.typical_amount >= 20
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
        if not output:
            for _, order in tables["standing_orders"].sort_values("amount", ascending=False).iterrows():
                output.append({
                    "name": _label(order["purpose"], "Standing order").capitalize(),
                    "purpose": _label(order["purpose"], "Standing order").capitalize(),
                    "amount": float(order["amount"]), "due_date": None, "key": str(order["order_id"]),
                })
        return sorted(output, key=lambda row: (row["due_date"] or "9999", -row["amount"]))

    def home(self, account_id: int) -> dict[str, Any]:
        tables = self._load(account_id)
        transactions = tables["transactions"].sort_values(["date", "transaction_id"], ascending=False)
        summary = tables["monthly_summary"].sort_values("month").iloc[-1]
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
            "balance_history": [
                {"month": str(row["month"]), "balance": float(row["month_end_balance"])}
                for _, row in tables["monthly_summary"].sort_values("month").tail(12).iterrows()
            ],
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
            "baseline_runway": RunwayCalculator.calculate(max(profile["buffer"], 0.0), 0.0, profile["spending"], profile["income"]).runway_months,
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

    def _budget_plan(self, tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
        profile = self.profile(tables)
        latest = tables["monthly_summary"].sort_values("month").iloc[-1]
        everyday_now = float(sum(latest[column] for column in EVERYDAY_COLUMNS))
        everyday_limit = round(profile["everyday_spending"] * 0.9, -1)
        fixed_now = float(sum(latest[column] for column in FIXED_COLUMNS))
        leftover = profile["income"] - profile["fixed_costs"] - everyday_limit
        save_target = max(round(max(leftover, 0) * 0.5, -1), round(profile["income"] * 0.05, -1))
        saved_now = max(float(latest["money_in"] - latest["money_out"]), 0.0)
        return [
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
            "goals": self._budget_plan(tables),
        }

    @staticmethod
    def _apply_shocks(profile: dict[str, float], shocks: list[dict[str, float]]) -> tuple[float, float, float]:
        income, spending, one_off = profile["income"], profile["spending"], 0.0
        for shock in shocks:
            name, value = shock["name"], float(shock["value"])
            if name == "job_loss_ei":
                income *= max(0.0, 1.0 - value)
            elif name == "pay_cut_pct":
                income *= max(0.0, 1.0 - value)
            elif name == "rent_up_pct":
                spending += profile["household_bills"] * value
            elif name == "one_off_costs":
                one_off += value
            elif name == "loan_payment_reduction":
                spending = max(0.0, spending - (profile["loan_payment"] if value <= 1 else value))
            elif name == "new_car_payment":
                spending += value
            elif name == "everyday_cut_pct":
                spending = max(0.0, spending - profile["everyday_spending"] * value)
            else:
                raise ValueError(f"Unsupported scenario shock: {name}")
        return income, spending, one_off

    def scenario(self, account_id: int, shocks: list[dict[str, float]]) -> dict[str, Any]:
        tables = self._load(account_id)
        profile = self.profile(tables)
        income, spending, one_off = self._apply_shocks(profile, shocks)
        buffer = profile["buffer"]
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

    def plans(self, account_id: int) -> dict[str, Any]:
        tables = self._load(account_id)
        profile = self.profile(tables)
        budget = self._budget_plan(tables)
        target = round(profile["spending"] * 6, -2)
        monthly_save = budget[2]["monthly_limit"]
        missing = max(target - profile["buffer"], 0.0)
        months_to_goal = (missing / monthly_save) if monthly_save > 0 else None

        def runway(shocks: list[dict[str, float]]) -> float:
            income, spending, one_off = self._apply_shocks(profile, shocks)
            return RunwayCalculator.calculate(max(profile["buffer"], 0.0), one_off, spending, income).runway_months

        base_shock = [{"name": "job_loss_ei", "value": 0.45}]
        base = runway(base_shock)
        actions = []
        candidates = [
            ("Cut everyday spending 10%", [{"name": "everyday_cut_pct", "value": 0.1}],
             f"Saves about ${profile['everyday_spending'] * 0.1:,.0f}/month on cash and card spending."),
            ("Cut everyday spending 25%", [{"name": "everyday_cut_pct", "value": 0.25}],
             f"Saves about ${profile['everyday_spending'] * 0.25:,.0f}/month. Harder, but buys real time."),
        ]
        if profile["loan_payment"] > 0:
            candidates.insert(0, ("Ask the bank to pause the loan", [{"name": "loan_payment_reduction", "value": 1}],
                                  f"Frees ${profile['loan_payment']:,.0f}/month while you look for work."))
        for title, extra, detail in candidates:
            months = runway(base_shock + extra)
            actions.append({"title": title, "detail": detail, "runway_months": months,
                            "months_gained": months - base, "_shocks": extra})
        actions.sort(key=lambda action: action["months_gained"], reverse=True)
        all_shocks = base_shock + [shock for action in actions[:2] for shock in action["_shocks"]]
        for action in actions:
            action.pop("_shocks")
        return {
            "account_id": account_id,
            "profile": profile,
            "goal_plan": {
                "name": "6-month safety net",
                "target": target,
                "current": profile["buffer"],
                "progress_pct": min(profile["buffer"] / target * 100, 100) if target else 0,
                "monthly_saving": monthly_save,
                "months_to_goal": months_to_goal,
                "steps": [
                    f"Keep everyday spending under ${budget[0]['monthly_limit']:,.0f}/month.",
                    f"Move ${monthly_save:,.0f} to savings each payday.",
                    "Protect bills and the loan first; they are paid before anything else.",
                ],
            },
            "backup_plan": {
                "trigger": "Job loss, EI pays 55% of income",
                "runway_without_actions": base,
                "runway_with_top_actions": runway(all_shocks),
                "actions": actions,
            },
        }

    def assistant(self, account_id: int, prompt: str) -> dict[str, Any]:
        tables = self._load(account_id)
        profile = self.profile(tables)
        text = prompt.lower()
        if any(word in text for word in ("budget", "save", "saving", "plan")):
            self._budget_requests.setdefault(account_id, []).append(prompt)
            plan = self._budget_plan(tables)
            message = (
                f"Done. I built a plan from your activity: keep everyday spending under "
                f"${plan[0]['monthly_limit']:,.0f}/month and aim to save ${plan[2]['monthly_limit']:,.0f}/month. "
                "See it on the Budget tab."
            )
        else:
            gap = profile["spending"] - profile["income"]
            message = (
                f"You typically bring in ${profile['income']:,.0f} and spend ${profile['spending']:,.0f} a month, "
                f"with a ${profile['buffer']:,.0f} buffer. "
                + (f"You run about ${gap:,.0f} short each month, so watch big withdrawals."
                   if gap > 0 else "You usually have money left over, which is a good sign.")
            )
        trace = ["account_profile", "budget_planner"]
        ai_message = self._ask_gemini(prompt, profile, message)
        if ai_message:
            message, trace = ai_message, trace + ["gemini"]
        return {
            "message": message,
            "data": {"account_id": account_id, "prompt": prompt, **profile},
            "tool_trace": trace,
        }

    @staticmethod
    def _ask_gemini(prompt: str, profile: dict[str, float], engine_answer: str) -> str | None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            return None
        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        instructions = (
            "You are Astro, a friendly Canadian banking assistant in the Horizon app. "
            "Answer in 2-3 short sentences. Use ONLY the numbers in the account profile and engine answer; "
            "never invent figures. Amounts are CAD per month. Not financial advice."
        )
        body = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [{"role": "user", "parts": [{"text": (
                f"Account profile: {json.dumps({k: round(v, 2) for k, v in profile.items()})}\n"
                f"Engine answer: {engine_answer}\nCustomer question: {prompt}"
            )}]}],
        }
        try:
            import httpx
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json=body, timeout=20,
            )
            if response.status_code != 200:
                print(f"[Astro] Gemini error {response.status_code}: {response.text[:300]}", flush=True)
                return None
            parts = response.json()["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
            return text or None
        except Exception as error:
            print(f"[Astro] Gemini call failed: {error}", flush=True)
            return None
