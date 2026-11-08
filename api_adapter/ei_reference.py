from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from pathlib import Path

import pandas as pd


class EIReferenceError(ValueError):
    """The local EI reference cannot be used for this account."""


class EIReference:
    def __init__(self, data_dir: Path, accounts: pd.DataFrame):
        self.data_dir = data_dir
        self.accounts = accounts

    def lookup(self, account_id: int, hours: int | None = None) -> dict:
        district_path = self.data_dir / "districts.parquet"
        rules_path = self.data_dir.parent / "external" / "ei_regular_benefits.csv"
        try:
            districts = pd.read_parquet(district_path)
            rules = pd.read_csv(rules_path)
        except (OSError, ValueError) as error:
            raise EIReferenceError("Local district or EI reference data could not be loaded") from error

        try:
            account = self.accounts.loc[self.accounts["account_id"] == account_id]
            if len(account) != 1 or pd.isna(account.iloc[0]["district_id"]):
                raise EIReferenceError("The account has no unique district")
            district = districts.loc[districts["district_id"] == account.iloc[0]["district_id"]]
            if len(district) != 1:
                raise EIReferenceError("The account district was not found uniquely")
            district = district.iloc[0]
            rate = float(district["unemployment_rate_2023"])
            if not isfinite(rate) or not 0 <= rate <= 100:
                raise EIReferenceError("The district unemployment rate is unavailable or invalid")

            def rule(name: str) -> float:
                rows = rules.loc[(rules["section"] == "rules") & (rules["item"] == name)]
                if len(rows) != 1:
                    raise EIReferenceError(f"EI rule {name} is missing or ambiguous")
                value = float(rows.iloc[0]["value"])
                if not isfinite(value) or value < 0:
                    raise EIReferenceError(f"EI rule {name} is invalid")
                return value

            benefit_rate = rule("benefit_rate")
            max_weekly_benefit = rule("max_weekly_benefit")
            if benefit_rate > 1:
                raise EIReferenceError("EI benefit rate is invalid")

            # The reference brackets are reported to one decimal place.
            rounded_rate = float(Decimal(str(rate)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
            result = {
                "district_id": int(district["district_id"]),
                "district_name": str(district["district_name"]),
                "district_region": str(district["region"]),
                "unemployment_rate_pct": rate,
                "unemployment_rate_year": 2023,
                "rule_rate_pct": rounded_rate,
                "benefit_rate": benefit_rate,
                "max_weekly_benefit": max_weekly_benefit,
                "rules_year": 2026,
                "weeks_payable": None,
                "weeks_payable_range": None,
                "insurable_hours": hours,
                "reference_type": "historical_non_canadian_district_proxy",
            }
            candidates = rules.loc[
                (rules["section"] == "weeks_payable")
                & (pd.to_numeric(rules["unemp_rate_min_pct"], errors="coerce") <= rounded_rate)
                & (pd.to_numeric(rules["unemp_rate_max_pct"], errors="coerce") >= rounded_rate)
            ]
            if candidates["unemp_rate_max_pct"].nunique() > 1:
                candidates = candidates.loc[
                    pd.to_numeric(candidates["unemp_rate_max_pct"], errors="coerce") == rounded_rate
                ]
            if candidates.empty:
                raise EIReferenceError("The EI table has no unique unemployment-rate bracket")
            if hours is not None:
                candidates = candidates.loc[
                    (pd.to_numeric(candidates["insurable_hours_min"], errors="coerce") <= hours)
                    & (pd.to_numeric(candidates["insurable_hours_max"], errors="coerce") >= hours)
                ]
                if len(candidates) != 1:
                    raise EIReferenceError("The EI table has no unique match for these hours and district rate")
                weeks = float(candidates.iloc[0]["value"])
                if not weeks.is_integer() or weeks < 0:
                    raise EIReferenceError("The EI payable-weeks value is invalid")
                result["weeks_payable"] = int(weeks)
            else:
                values = pd.to_numeric(candidates["value"], errors="coerce")
                if values.isna().any() or any(not isfinite(value) or value < 0 or value % 1 for value in values):
                    raise EIReferenceError("The EI payable-weeks values are invalid")
                eligible = values[values > 0]
                if eligible.empty:
                    raise EIReferenceError("The EI table has no positive payable-weeks values for this rate")
                result["weeks_payable_range"] = [int(eligible.min()), int(eligible.max())]
            return result
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, EIReferenceError):
                raise
            raise EIReferenceError("Local district or EI reference data is invalid") from error
