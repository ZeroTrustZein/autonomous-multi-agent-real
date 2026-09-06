"""Private equity distribution waterfall engine (GP/LP promote structures)."""

from __future__ import annotations

from typing import List, Optional

from autonomous_multi_agent_real.engine.financial import (
    calculate_equity_multiple,
    calculate_irr,
)
from autonomous_multi_agent_real.types import (
    WaterfallResult,
    WaterfallStructure,
    WaterfallTier,
    WaterfallYearDistribution,
)


def get_default_waterfall_structure(
    preferred_return_rate: float = 0.08,
    lp_equity_pct: float = 0.90,
    gp_equity_pct: float = 0.10,
) -> WaterfallStructure:
    """Create a standard institutional real estate waterfall structure."""
    return WaterfallStructure(
        preferred_return_rate=preferred_return_rate,
        lp_equity_pct=lp_equity_pct,
        gp_equity_pct=gp_equity_pct,
        tiers=[
            WaterfallTier(
                name="Return of Capital & Preferred Return",
                hurdle_irr=preferred_return_rate,
                lp_share=lp_equity_pct,
                gp_share=gp_equity_pct,
            ),
            WaterfallTier(
                name="Tier 1 Promote (80/20 to 14% IRR)",
                hurdle_irr=0.14,
                lp_share=0.80,
                gp_share=0.20,
            ),
            WaterfallTier(
                name="Tier 2 Promote (70/30 to 18% IRR)",
                hurdle_irr=0.18,
                lp_share=0.70,
                gp_share=0.30,
            ),
            WaterfallTier(
                name="Residual Promote (50/50 > 18% IRR)",
                hurdle_irr=999.0,
                lp_share=0.50,
                gp_share=0.50,
            ),
        ],
    )


class WaterfallEngine:
    """Computes LP/GP cash distributions, preferred return, and sponsor promote."""

    def __init__(self, structure: Optional[WaterfallStructure] = None):
        self.structure = structure or get_default_waterfall_structure()

    def calculate(
        self,
        total_equity: float,
        annual_cash_flows: List[float],
    ) -> WaterfallResult:
        """Calculate multi-tier cash distribution between LP and GP.

        annual_cash_flows: List of net cash flows received at the end of each year
        (Years 1..N, where Year N includes terminal sale proceeds).
        """
        if total_equity <= 0.0 or not annual_cash_flows:
            return WaterfallResult(
                lp_equity_invested=0.0,
                gp_equity_invested=0.0,
                lp_total_distributions=0.0,
                gp_total_distributions=0.0,
                gp_total_promote=0.0,
                lp_irr=0.0,
                lp_equity_multiple=0.0,
                gp_irr=0.0,
                gp_equity_multiple=0.0,
                annual_distributions=[],
            )

        lp_equity = round(total_equity * self.structure.lp_equity_pct, 2)
        gp_equity = round(total_equity * self.structure.gp_equity_pct, 2)

        pref_rate = self.structure.preferred_return_rate

        lp_unreturned = lp_equity
        gp_unreturned = gp_equity
        lp_pref_accrued = 0.0
        gp_pref_accrued = 0.0

        lp_distributions: List[float] = []
        gp_distributions: List[float] = []
        gp_promotes: List[float] = []
        yearly_records: List[WaterfallYearDistribution] = []

        total_years = len(annual_cash_flows)

        for yr_idx, cash_flow in enumerate(annual_cash_flows, start=1):
            is_final_year = yr_idx == total_years
            avail = max(0.0, cash_flow)

            # 1. Accrue preferred return on unreturned capital
            lp_pref_accrued += lp_unreturned * pref_rate
            gp_pref_accrued += gp_unreturned * pref_rate

            yr_lp_dist = 0.0
            yr_gp_dist = 0.0
            yr_gp_promote = 0.0

            # Step A: Pay accrued preferred return
            total_pref_due = lp_pref_accrued + gp_pref_accrued
            if total_pref_due > 0.0 and avail > 0.0:
                pref_paid = min(avail, total_pref_due)
                ratio_lp = lp_pref_accrued / total_pref_due if total_pref_due > 0 else 0.5
                lp_pref_payment = pref_paid * ratio_lp
                gp_pref_payment = pref_paid * (1.0 - ratio_lp)

                lp_pref_accrued -= lp_pref_payment
                gp_pref_accrued -= gp_pref_payment
                yr_lp_dist += lp_pref_payment
                yr_gp_dist += gp_pref_payment
                avail -= pref_paid

            # Step B: Return of Capital (pay down unreturned principal)
            # Standard: return capital in final disposition or when operating cash flows allow
            total_unreturned = lp_unreturned + gp_unreturned
            if (
                total_unreturned > 0.0
                and avail > 0.0
                and (is_final_year or avail > total_unreturned)
            ):
                cap_returned = min(avail, total_unreturned)
                ratio_lp = lp_unreturned / total_unreturned if total_unreturned > 0 else 0.5
                lp_cap_pay = cap_returned * ratio_lp
                gp_cap_pay = cap_returned * (1.0 - ratio_lp)

                lp_unreturned = max(0.0, lp_unreturned - lp_cap_pay)
                gp_unreturned = max(0.0, gp_unreturned - gp_cap_pay)
                yr_lp_dist += lp_cap_pay
                yr_gp_dist += gp_cap_pay
                avail -= cap_returned

            # Step C: Excess cash flow distributed through Promote Tiers
            if avail > 0.0:
                # If unreturned capital still remains (e.g. non-terminal year), distribute pro-rata
                if (lp_unreturned + gp_unreturned) > 0.0 and not is_final_year:
                    lp_share = self.structure.lp_equity_pct
                    gp_share = self.structure.gp_equity_pct
                    yr_lp_dist += avail * lp_share
                    yr_gp_dist += avail * gp_share
                else:
                    # In terminal disposition or once capital is fully returned:
                    # Distribute through promote tiers
                    remaining_pool = avail
                    # Select applicable tier based on projected LP returns or tier progression
                    active_tier = self._select_promote_tier(
                        lp_equity=lp_equity,
                        historical_lp_flows=lp_distributions + [yr_lp_dist],
                        remaining_pool=remaining_pool,
                    )

                    lp_portion = remaining_pool * active_tier.lp_share
                    gp_portion = remaining_pool * active_tier.gp_share

                    # Promote is the GP portion received in excess of GP's pro-rata equity percentage
                    gp_pro_rata = remaining_pool * self.structure.gp_equity_pct
                    tier_promote = max(0.0, gp_portion - gp_pro_rata)

                    yr_lp_dist += lp_portion
                    yr_gp_dist += gp_portion
                    yr_gp_promote += tier_promote

            lp_distributions.append(round(yr_lp_dist, 2))
            gp_distributions.append(round(yr_gp_dist, 2))
            gp_promotes.append(round(yr_gp_promote, 2))

            yearly_records.append(
                WaterfallYearDistribution(
                    year=yr_idx,
                    total_distributable_cash=round(cash_flow, 2),
                    lp_distribution=round(yr_lp_dist, 2),
                    gp_distribution=round(yr_gp_dist, 2),
                    gp_promote=round(yr_gp_promote, 2),
                    lp_unreturned_capital=round(lp_unreturned, 2),
                    gp_unreturned_capital=round(gp_unreturned, 2),
                )
            )

        lp_total_dist = round(sum(lp_distributions), 2)
        gp_total_dist = round(sum(gp_distributions), 2)
        gp_total_promote = round(sum(gp_promotes), 2)

        # Calculate final IRRs and multiples
        lp_stream = [-lp_equity] + lp_distributions
        gp_stream = [-gp_equity] + gp_distributions

        lp_irr = calculate_irr(lp_stream)
        gp_irr = calculate_irr(gp_stream)
        lp_multiple = calculate_equity_multiple(lp_equity, lp_total_dist)
        gp_multiple = calculate_equity_multiple(gp_equity, gp_total_dist)

        return WaterfallResult(
            lp_equity_invested=lp_equity,
            gp_equity_invested=gp_equity,
            lp_total_distributions=lp_total_dist,
            gp_total_distributions=gp_total_dist,
            gp_total_promote=gp_total_promote,
            lp_irr=round(lp_irr, 4),
            lp_equity_multiple=round(lp_multiple, 3),
            gp_irr=round(gp_irr, 4),
            gp_equity_multiple=round(gp_multiple, 3),
            annual_distributions=yearly_records,
        )

    def _select_promote_tier(
        self,
        lp_equity: float,
        historical_lp_flows: List[float],
        remaining_pool: float,
    ) -> WaterfallTier:
        """Determine appropriate promote tier based on LP hurdle IRR."""
        if not self.structure.tiers:
            return WaterfallTier(
                name="Pro Rata",
                hurdle_irr=999.0,
                lp_share=self.structure.lp_equity_pct,
                gp_share=self.structure.gp_equity_pct,
            )

        # Estimate what LP IRR would be if LP gets 100% of remaining pool
        test_stream = (
            [-lp_equity] + historical_lp_flows[:-1] + [historical_lp_flows[-1] + remaining_pool]
        )
        est_irr = calculate_irr(test_stream)

        # Find the tier that matches the estimated return level
        for tier in self.structure.tiers:
            if est_irr <= tier.hurdle_irr:
                return tier

        return self.structure.tiers[-1]
