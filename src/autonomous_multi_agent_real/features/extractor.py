"""Feature extraction pipeline for real estate underwriting models and streaming data."""

from __future__ import annotations

import math
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from autonomous_multi_agent_real.features.registry import FeatureRegistry, get_default_registry
from autonomous_multi_agent_real.features.types import (
    FeatureRecord,
    FeatureStreamEvent,
    FeatureTimeWindow,
    FeatureVector,
)


class WindowedAggregator:
    """Sliding time-window and exponential moving average (EMA) aggregation engine for streaming features."""

    def __init__(
        self,
        window_seconds: float = 3600.0,
        ema_alpha: float = 0.2,
    ) -> None:
        self.window_seconds = window_seconds
        self.ema_alpha = ema_alpha
        # Deque of tuples: (timestamp_epoch, value)
        self._history: deque[tuple[float, float]] = deque()
        self._ema: Optional[float] = None

    def add(self, value: float, dt: Optional[datetime] = None) -> None:
        """Add a numeric sample with an optional timestamp."""
        ts = dt.timestamp() if dt is not None else datetime.now(timezone.utc).timestamp()
        self._history.append((ts, float(value)))

        # Update Exponential Moving Average
        if self._ema is None:
            self._ema = float(value)
        else:
            self._ema = self.ema_alpha * float(value) + (1.0 - self.ema_alpha) * self._ema

        # Evict old samples outside window
        self._prune(ts)

    def _prune(self, current_ts: float) -> None:
        cutoff = current_ts - self.window_seconds
        while self._history and self._history[0][0] <= cutoff:
            self._history.popleft()

    @property
    def count(self) -> int:
        return len(self._history)

    @property
    def values(self) -> List[float]:
        return [v for _, v in self._history]

    @property
    def mean(self) -> Optional[float]:
        vals = self.values
        return (sum(vals) / len(vals)) if vals else None

    @property
    def min_value(self) -> Optional[float]:
        vals = self.values
        return min(vals) if vals else None

    @property
    def max_value(self) -> Optional[float]:
        vals = self.values
        return max(vals) if vals else None

    @property
    def std_dev(self) -> Optional[float]:
        vals = self.values
        if len(vals) < 2:
            return 0.0 if vals else None
        avg = sum(vals) / len(vals)
        variance = sum((x - avg) ** 2 for x in vals) / (len(vals) - 1)
        return math.sqrt(variance)

    @property
    def ema(self) -> Optional[float]:
        return self._ema

    @property
    def momentum(self) -> Optional[float]:
        """Difference between newest and oldest observation in the current window."""
        if len(self._history) < 2:
            return 0.0 if self._history else None
        return self._history[-1][1] - self._history[0][1]

    def to_dict(self, prefix: str = "") -> Dict[str, Optional[float]]:
        """Return snapshot dictionary of window aggregations."""
        p = f"{prefix}_" if prefix else ""
        return {
            f"{p}count": float(self.count),
            f"{p}mean": self.mean,
            f"{p}min": self.min_value,
            f"{p}max": self.max_value,
            f"{p}std": self.std_dev,
            f"{p}ema": self.ema,
            f"{p}momentum": self.momentum,
        }


class FeatureExtractor:
    """Core feature engineering engine for extracting structured features from deal objects, underwriting results, and streams."""

    def __init__(self, registry: Optional[FeatureRegistry] = None) -> None:
        self.registry = registry if registry is not None else get_default_registry()
        # Entity-feature keyed windowed aggregators: (entity_id, feature_name, window_enum) -> WindowedAggregator
        self._aggregators: Dict[tuple[str, str, str], WindowedAggregator] = {}

    def extract_from_deal(
        self,
        deal: Any,
        metadata: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
    ) -> FeatureVector:
        """Extract baseline property, operating expense, and initial basis features from a deal representation."""
        ts = as_of or datetime.now(timezone.utc)
        deal_id = (
            getattr(deal, "id", None)
            or getattr(deal, "deal_id", None)
            or (deal.get("id") if isinstance(deal, dict) else "unknown_deal")
        )
        raw_features: Dict[str, Any] = {}

        # 1. Attribute resolution (supports Pydantic PropertyDeal or dict)
        if isinstance(deal, dict):
            unit_mix = deal.get("unit_mix", [])
            unit_count = (
                sum(u.get("count", 0) for u in unit_mix) if unit_mix else deal.get("total_units", 0)
            )
            sqft = float(deal.get("gross_square_feet", 0.0))
            price = float(deal.get("purchase_price", 0.0))
            rehab = float(deal.get("rehab_budget", 0.0))
            occupancy = float(deal.get("current_occupancy_pct", 0.95))
            market_occupancy = float(deal.get("market_occupancy_pct", 0.95))
            rent_growth = float(deal.get("annual_rent_growth_pct", 0.03))
            expense_growth = float(deal.get("annual_expense_growth_pct", 0.025))
            exit_cap = float(deal.get("exit_cap_rate", 0.065))
            hold_years = int(deal.get("hold_period_years", 5))

            # Current rents
            curr_monthly_rent = 0.0
            mkt_monthly_rent = 0.0
            for u in unit_mix:
                cnt = u.get("count", 0)
                curr_monthly_rent += cnt * u.get("current_rent", 0.0)
                mkt_monthly_rent += cnt * u.get("market_rent", 0.0)

            # Expenses
            exp_data = deal.get("expenses", {})
            taxes = exp_data.get("property_taxes", 0.0)
            ins = exp_data.get("insurance", 0.0)
            rm = exp_data.get("repairs_and_maintenance", 0.0)
            mgmt_pct = exp_data.get("property_management_pct", 0.08)
            reserves = exp_data.get("replacement_reserves_per_unit", 250.0) * unit_count
            fixed_opex = (
                taxes
                + ins
                + rm
                + reserves
                + exp_data.get("utilities", 0.0)
                + exp_data.get("admin_and_legal", 0.0)
            )

            # Financing
            fin = deal.get("financing", {})
            interest_rate = fin.get("interest_rate", 0.065)
            max_ltv = fin.get("max_ltv", 0.75)
            min_dscr = fin.get("min_dscr", 1.25)
            amort_years = fin.get("amortization_years", 30)
        else:
            # Pydantic or object model
            unit_count = getattr(deal, "total_units", 0)
            sqft = float(getattr(deal, "gross_square_feet", 0.0))
            price = float(getattr(deal, "purchase_price", 0.0))
            rehab = float(getattr(deal, "rehab_budget", 0.0))
            occupancy = float(getattr(deal, "current_occupancy_pct", 0.95))
            market_occupancy = float(getattr(deal, "market_occupancy_pct", 0.95))
            rent_growth = float(getattr(deal, "annual_rent_growth_pct", 0.03))
            expense_growth = float(getattr(deal, "annual_expense_growth_pct", 0.025))
            exit_cap = float(getattr(deal, "exit_cap_rate", 0.065))
            hold_years = int(getattr(deal, "hold_period_years", 5))

            curr_monthly_rent = float(getattr(deal, "total_current_monthly_rent", 0.0))
            mkt_monthly_rent = float(getattr(deal, "total_market_monthly_rent", 0.0))

            expenses_obj = getattr(deal, "expenses", None)
            if expenses_obj is not None:
                mgmt_pct = float(getattr(expenses_obj, "property_management_pct", 0.08))
                if hasattr(expenses_obj, "fixed_annual_expenses"):
                    fixed_opex = float(expenses_obj.fixed_annual_expenses(unit_count))
                else:
                    fixed_opex = (
                        getattr(expenses_obj, "property_taxes", 0.0)
                        + getattr(expenses_obj, "insurance", 0.0)
                        + getattr(expenses_obj, "repairs_and_maintenance", 0.0)
                    )
            else:
                mgmt_pct = 0.08
                fixed_opex = 0.0

            fin_obj = getattr(deal, "financing", None)
            if fin_obj is not None:
                interest_rate = float(getattr(fin_obj, "interest_rate", 0.065))
                max_ltv = float(getattr(fin_obj, "max_ltv", 0.75))
                min_dscr = float(getattr(fin_obj, "min_dscr", 1.25))
                amort_years = int(getattr(fin_obj, "amortization_years", 30))
            else:
                interest_rate = 0.065
                max_ltv = 0.75
                min_dscr = 1.25
                amort_years = 30

        # Calculations
        gross_potential_rent = curr_monthly_rent * 12.0
        vacancy_loss = gross_potential_rent * (1.0 - occupancy)
        egi = gross_potential_rent - vacancy_loss
        total_opex = fixed_opex + (egi * mgmt_pct)
        in_place_noi = max(0.0, egi - total_opex)

        # Market stabilized pro-forma estimate
        mkt_gpr = mkt_monthly_rent * 12.0
        mkt_egi = mkt_gpr * market_occupancy
        mkt_opex = fixed_opex + (mkt_egi * mgmt_pct)
        stabilized_noi = max(0.0, mkt_egi - mkt_opex)

        raw_features["unit_count"] = unit_count
        raw_features["total_square_feet"] = sqft
        raw_features["purchase_price"] = price
        raw_features["rehab_budget"] = rehab
        raw_features["current_occupancy_pct"] = occupancy
        raw_features["market_occupancy_pct"] = market_occupancy
        raw_features["annual_rent_growth_rate"] = rent_growth
        raw_features["annual_expense_growth_rate"] = expense_growth
        raw_features["exit_cap_rate"] = exit_cap
        raw_features["hold_period_years"] = hold_years
        raw_features["interest_rate"] = interest_rate
        raw_features["max_ltv"] = max_ltv
        raw_features["min_dscr"] = min_dscr
        raw_features["amortization_years"] = amort_years

        raw_features["in_place_gross_rent"] = gross_potential_rent
        raw_features["in_place_noi"] = in_place_noi
        raw_features["stabilized_noi"] = stabilized_noi
        raw_features["operating_expenses"] = total_opex
        raw_features["expense_ratio"] = (total_opex / egi) if egi > 0 else 0.0
        raw_features["in_place_cap_rate"] = (in_place_noi / price) if price > 0 else 0.0

        if sqft > 0:
            raw_features["in_place_rent_per_sqft"] = gross_potential_rent / sqft
            raw_features["market_rent_per_sqft"] = mkt_gpr / sqft
            raw_features["price_per_sqft"] = price / sqft

        if unit_count > 0:
            raw_features["avg_unit_sqft"] = sqft / unit_count
            raw_features["opex_per_unit"] = total_opex / unit_count
            raw_features["rehab_per_unit"] = rehab / unit_count
            raw_features["price_per_unit"] = price / unit_count
            raw_features["purchase_price_per_unit"] = price / unit_count

        loss_to_lease = max(0.0, mkt_monthly_rent - curr_monthly_rent) * 12.0
        raw_features["loss_to_lease_annual"] = loss_to_lease
        raw_features["loss_to_lease_pct"] = (loss_to_lease / mkt_gpr) if mkt_gpr > 0 else 0.0

        # Compute all derived features registered in the registry
        enriched = self.registry.compute_derived(raw_features)

        return FeatureVector(
            entity_id=str(deal_id),
            entity_type="deal",
            features=enriched,
            timestamp=ts,
            schema_version="1.0.0",
            metadata=metadata or {},
        )

    def extract_from_underwrite(
        self,
        deal: Any,
        underwrite_result: Any,
        metadata: Optional[Dict[str, Any]] = None,
        as_of: Optional[datetime] = None,
    ) -> FeatureVector:
        """Enrich deal features with outputs from financial underwriting, debt sizing, and risk simulations."""
        base_vector = self.extract_from_deal(deal, metadata=metadata, as_of=as_of)
        features = dict(base_vector.features)

        # 1. Debt Sizing
        debt_sizing = getattr(underwrite_result, "debt_sizing", None) or (
            underwrite_result.get("debt_sizing") if isinstance(underwrite_result, dict) else None
        )
        if debt_sizing:
            if isinstance(debt_sizing, dict):
                loan_amt = float(debt_sizing.get("loan_amount", 0.0))
                eq_req = float(debt_sizing.get("equity_required", 0.0))
                ltv = float(debt_sizing.get("ltv_ratio", 0.0))
                dscr = float(debt_sizing.get("dscr_year1", 0.0))
                dy = float(debt_sizing.get("debt_yield_pct", 0.0))
                debt_service = float(debt_sizing.get("annual_debt_service", 0.0))
            else:
                loan_amt = float(getattr(debt_sizing, "loan_amount", 0.0))
                eq_req = float(getattr(debt_sizing, "equity_required", 0.0))
                ltv = float(getattr(debt_sizing, "ltv_ratio", 0.0))
                dscr = float(getattr(debt_sizing, "dscr_year1", 0.0))
                dy = float(getattr(debt_sizing, "debt_yield_pct", 0.0))
                debt_service = float(getattr(debt_sizing, "annual_debt_service", 0.0))

            features["loan_amount"] = loan_amt
            features["equity_required"] = eq_req
            features["ltv_ratio"] = ltv
            features["dscr_year1"] = dscr
            features["underwritten_dscr"] = dscr
            features["debt_yield"] = dy
            features["annual_debt_service"] = debt_service

        # 2. Deal Metrics (Returns)
        deal_metrics = getattr(underwrite_result, "deal_metrics", None) or (
            underwrite_result.get("deal_metrics") if isinstance(underwrite_result, dict) else None
        )
        if deal_metrics:
            if isinstance(deal_metrics, dict):
                features["unlevered_irr"] = float(deal_metrics.get("unlevered_irr", 0.0))
                features["levered_irr"] = float(deal_metrics.get("levered_irr", 0.0))
                features["equity_multiple"] = float(deal_metrics.get("equity_multiple", 0.0))
                features["net_present_value"] = float(deal_metrics.get("net_present_value", 0.0))
                features["average_cash_on_cash"] = float(
                    deal_metrics.get("average_cash_on_cash", 0.0)
                )
                features["peak_capital_at_risk"] = float(
                    deal_metrics.get("peak_capital_at_risk", 0.0)
                )
            else:
                features["unlevered_irr"] = float(getattr(deal_metrics, "unlevered_irr", 0.0))
                features["levered_irr"] = float(getattr(deal_metrics, "levered_irr", 0.0))
                features["equity_multiple"] = float(getattr(deal_metrics, "equity_multiple", 0.0))
                features["net_present_value"] = float(
                    getattr(deal_metrics, "net_present_value", 0.0)
                )
                features["average_cash_on_cash"] = float(
                    getattr(deal_metrics, "average_cash_on_cash", 0.0)
                )
                features["peak_capital_at_risk"] = float(
                    getattr(deal_metrics, "peak_capital_at_risk", 0.0)
                )

        # 3. Monte Carlo Risk Simulation
        mc = getattr(underwrite_result, "monte_carlo", None) or (
            underwrite_result.get("monte_carlo") if isinstance(underwrite_result, dict) else None
        )
        if mc:
            if isinstance(mc, dict):
                features["mean_irr"] = float(mc.get("mean_levered_irr") or mc.get("mean_irr", 0.0))
                features["std_irr"] = float(mc.get("std_levered_irr") or mc.get("std_irr", 0.0))
                features["p10_irr"] = float(mc.get("p10_irr", 0.0))
                features["p50_irr"] = float(mc.get("p50_irr", 0.0))
                features["p90_irr"] = float(mc.get("p90_irr", 0.0))
                prob_neg = float(
                    mc.get("probability_negative_irr") or mc.get("probability_of_loss", 0.0)
                )
                features["probability_negative_irr"] = prob_neg
                features["default_probability"] = prob_neg
                features["probability_dscr_breach"] = float(mc.get("probability_dscr_breach", 0.0))
                features["var_95"] = float(mc.get("var_95_irr") or mc.get("var_95", 0.0))
                features["cvar_95"] = float(mc.get("cvar_95_irr") or mc.get("cvar_95", 0.0))
            else:
                features["mean_irr"] = float(
                    getattr(mc, "mean_levered_irr", None) or getattr(mc, "mean_irr", 0.0)
                )
                features["std_irr"] = float(
                    getattr(mc, "std_levered_irr", None) or getattr(mc, "std_irr", 0.0)
                )
                features["p10_irr"] = float(getattr(mc, "p10_irr", 0.0))
                features["p50_irr"] = float(getattr(mc, "p50_irr", 0.0))
                features["p90_irr"] = float(getattr(mc, "p90_irr", 0.0))
                prob_neg = float(
                    getattr(mc, "probability_negative_irr", None)
                    or getattr(mc, "probability_of_loss", 0.0)
                )
                features["probability_negative_irr"] = prob_neg
                features["default_probability"] = prob_neg
                features["probability_dscr_breach"] = float(
                    getattr(mc, "probability_dscr_breach", 0.0)
                )
                features["var_95"] = float(
                    getattr(mc, "var_95_irr", None) or getattr(mc, "var_95", 0.0)
                )
                features["cvar_95"] = float(
                    getattr(mc, "cvar_95_irr", None) or getattr(mc, "cvar_95", 0.0)
                )

        # 4. Breakeven Metrics
        be = getattr(underwrite_result, "breakeven", None) or (
            underwrite_result.get("breakeven") if isinstance(underwrite_result, dict) else None
        )
        if be:
            if isinstance(be, dict):
                features["break_even_occupancy"] = float(be.get("breakeven_occupancy_pct", 0.0))
                features["breakeven_rent_per_unit"] = float(be.get("breakeven_rent_per_unit", 0.0))
            else:
                features["break_even_occupancy"] = float(
                    getattr(be, "breakeven_occupancy_pct", 0.0)
                )
                features["breakeven_rent_per_unit"] = float(
                    getattr(be, "breakeven_rent_per_unit", 0.0)
                )

        # 5. Waterfall Structure Return Shares
        wf = getattr(underwrite_result, "waterfall", None) or (
            underwrite_result.get("waterfall") if isinstance(underwrite_result, dict) else None
        )
        if wf:
            if isinstance(wf, dict):
                features["lp_net_irr"] = float(wf.get("lp_irr") or wf.get("lp_net_irr", 0.0))
                features["gp_net_irr"] = float(wf.get("gp_irr") or wf.get("gp_net_irr", 0.0))
                features["lp_equity_multiple"] = float(wf.get("lp_equity_multiple", 0.0))
                features["gp_equity_multiple"] = float(wf.get("gp_equity_multiple", 0.0))
                features["total_promote_dollars"] = float(
                    wf.get("gp_total_promote") or wf.get("total_promote_dollars", 0.0)
                )
            else:
                features["lp_net_irr"] = float(
                    getattr(wf, "lp_irr", None) or getattr(wf, "lp_net_irr", 0.0)
                )
                features["gp_net_irr"] = float(
                    getattr(wf, "gp_irr", None) or getattr(wf, "gp_net_irr", 0.0)
                )
                features["lp_equity_multiple"] = float(getattr(wf, "lp_equity_multiple", 0.0))
                features["gp_equity_multiple"] = float(getattr(wf, "gp_equity_multiple", 0.0))
                features["total_promote_dollars"] = float(
                    getattr(wf, "gp_total_promote", None)
                    or getattr(wf, "total_promote_dollars", 0.0)
                )

        # 6. Committee Synthesis & Composite Score
        committee_score = getattr(underwrite_result, "committee_score", None) or (
            underwrite_result.get("committee_score")
            if isinstance(underwrite_result, dict)
            else None
        )
        if committee_score is not None:
            features["composite_deal_score"] = float(committee_score)

        # Re-run derived feature computation
        enriched = self.registry.compute_derived(features)

        return base_vector.model_copy(update={"features": enriched})

    def extract_records(
        self,
        deal: Any,
        underwrite_result: Optional[Any] = None,
        source: str = "feature_extractor",
    ) -> List[FeatureRecord]:
        """Decompose extraction into individual atomic FeatureRecord objects."""
        if underwrite_result is not None:
            vec = self.extract_from_underwrite(deal, underwrite_result)
        else:
            vec = self.extract_from_deal(deal)

        records: List[FeatureRecord] = []
        for name, val in vec.features.items():
            records.append(
                FeatureRecord(
                    entity_id=vec.entity_id,
                    entity_type=vec.entity_type,
                    feature_name=name,
                    value=val,
                    timestamp=vec.timestamp,
                    source=source,
                )
            )
        return records

    def extract_from_stream_event(
        self,
        event: FeatureStreamEvent,
        source: str = "stream_event",
    ) -> List[FeatureRecord]:
        """Convert a FeatureStreamEvent payload into atomic FeatureRecord elements."""
        records: List[FeatureRecord] = []
        payload = event.payload
        entity_id = getattr(event, "entity_id", None) or str(
            payload.get("entity_id") or payload.get("deal_id") or "stream_unknown"
        )
        entity_type = getattr(event, "entity_type", None) or str(
            payload.get("entity_type") or "deal"
        )
        ts = (
            getattr(event, "event_time", None)
            or getattr(event, "timestamp", None)
            or datetime.now(timezone.utc)
        )

        # If payload contains nested features dict
        feat_dict = payload.get("features", payload)
        for k, v in feat_dict.items():
            if k in ("entity_id", "deal_id", "entity_type", "timestamp", "event_time"):
                continue
            records.append(
                FeatureRecord(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    feature_name=k,
                    value=v,
                    timestamp=ts,
                    source=source,
                )
            )
        return records

    def update_window_aggregation(
        self,
        entity_id: str,
        feature_name: str,
        value: float,
        window: FeatureTimeWindow = FeatureTimeWindow.HOURLY,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Optional[float]]:
        """Update streaming time-window statistics for a given feature."""
        # Map time window enum to seconds
        seconds_map = {
            FeatureTimeWindow.REALTIME: 60.0,
            FeatureTimeWindow.HOURLY: 3600.0,
            FeatureTimeWindow.DAILY: 86400.0,
            FeatureTimeWindow.WEEKLY: 604800.0,
            FeatureTimeWindow.MONTHLY: 2592000.0,
        }
        duration = seconds_map.get(window, 3600.0)
        key = (entity_id, feature_name, window.value)
        if key not in self._aggregators:
            self._aggregators[key] = WindowedAggregator(window_seconds=duration)

        agg = self._aggregators[key]
        agg.add(value, dt=timestamp)
        return agg.to_dict(prefix=f"{feature_name}_{window.value}")

    def extract_deal_features(
        self,
        deal: Any,
        context: Optional[Any] = None,
        as_of: Optional[datetime] = None,
    ) -> FeatureVector:
        """Alias for extract_from_deal or extract_from_underwrite depending on context availability."""
        if context is not None:
            return self.extract_from_underwrite(deal, underwrite_result=context, as_of=as_of)
        return self.extract_from_deal(deal, as_of=as_of)

    def extract_deal_records(
        self,
        deal: Any,
        context: Optional[Any] = None,
        source: str = "feature_extractor",
    ) -> List[FeatureRecord]:
        """Alias for extract_records passing deal and optional context."""
        return self.extract_records(deal, underwrite_result=context, source=source)
