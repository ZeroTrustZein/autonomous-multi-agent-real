"""Portfolio management, multi-asset aggregation, and joint stress testing engine."""

from __future__ import annotations

from typing import Dict, List, Optional

from autonomous_multi_agent_real.engine.financial import calculate_irr, calculate_npv
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.portfolio.models import (
    PortfolioDealAllocation,
    PortfolioRiskProfile,
    PortfolioRollup,
    PortfolioStressResult,
    PortfolioStressScenario,
)
from autonomous_multi_agent_real.types import PropertyDeal, UnderwritingResult


class PortfolioManager:
    """Manages an investment portfolio of commercial and residential real estate assets."""

    def __init__(
        self,
        portfolio_id: str = "main-portfolio",
        portfolio_name: str = "Flagship Real Estate Opportunity Fund",
    ):
        self.portfolio_id = portfolio_id
        self.portfolio_name = portfolio_name
        self._deals: Dict[str, PropertyDeal] = {}
        self._results: Dict[str, UnderwritingResult] = {}

    def add_deal(self, deal: PropertyDeal, result: Optional[UnderwritingResult] = None) -> None:
        """Add a deal to the portfolio."""
        self._deals[deal.id] = deal
        if result is not None:
            self._results[deal.id] = result

    def remove_deal(self, deal_id: str) -> bool:
        """Remove a deal from the portfolio by ID."""
        if deal_id in self._deals:
            del self._deals[deal_id]
            self._results.pop(deal_id, None)
            return True
        return False

    def get_deals(self) -> List[PropertyDeal]:
        """Return list of all portfolio deals."""
        return list(self._deals.values())

    def get_results(self) -> Dict[str, UnderwritingResult]:
        """Return dict of underwriting results."""
        return dict(self._results)

    def underwrite_all(self, iterations: int = 500) -> Dict[str, UnderwritingResult]:
        """Execute underwriting pipeline across all portfolio deals."""
        pipeline = DealPipeline(monte_carlo_iterations=iterations)
        for deal in self._deals.values():
            if deal.id not in self._results:
                self._results[deal.id] = pipeline.run(deal)
        return dict(self._results)

    def generate_rollup(self) -> PortfolioRollup:
        """Aggregate operational and financial performance across all portfolio assets."""
        if not self._deals:
            return PortfolioRollup(
                portfolio_id=self.portfolio_id,
                portfolio_name=self.portfolio_name,
                deal_count=0,
                total_units=0,
                total_gross_square_feet=0.0,
                total_purchase_price=0.0,
                total_equity_invested=0.0,
                total_debt_funded=0.0,
                weighted_ltv=0.0,
                weighted_dscr=0.0,
                weighted_exit_cap=0.0,
                portfolio_levered_irr=0.0,
                portfolio_unlevered_irr=0.0,
                portfolio_equity_multiple=0.0,
                portfolio_npv=0.0,
            )

        # Ensure all deals have underwriting results
        self.underwrite_all()

        total_units = sum(d.total_units for d in self._deals.values())
        total_sqft = sum(d.gross_square_feet for d in self._deals.values())
        total_price = sum(d.purchase_price for d in self._deals.values())
        total_equity = sum(res.debt_sizing.equity_required for res in self._results.values())
        total_debt = sum(res.debt_sizing.loan_amount for res in self._results.values())

        # Find maximum hold years
        max_years = max((d.hold_period_years for d in self._deals.values()), default=5)

        # Aggregate levered and unlevered cash flows
        aggregate_levered_flows = [0.0] * (max_years + 1)
        aggregate_unlevered_flows = [0.0] * (max_years + 1)

        # Year 0 initial investments
        aggregate_levered_flows[0] = -total_equity
        aggregate_unlevered_flows[0] = -sum(d.total_acquisition_basis for d in self._deals.values())

        for deal_id, res in self._results.items():
            deal = self._deals[deal_id]
            for cf in res.cash_flows:
                yr = cf.year
                if yr <= max_years:
                    aggregate_levered_flows[yr] += cf.net_cash_flow
                    # Unlevered flow is NOI - capex + exit proceeds
                    unlev_cf = (
                        cf.net_operating_income - cf.capital_expenditures
                    ) + cf.exit_sale_proceeds
                    aggregate_unlevered_flows[yr] += unlev_cf

        port_lev_irr = calculate_irr(aggregate_levered_flows)
        port_unlev_irr = calculate_irr(aggregate_unlevered_flows)
        total_distributions = sum(aggregate_levered_flows[1:])
        port_em = total_distributions / total_equity if total_equity > 0 else 0.0
        port_npv = calculate_npv(0.08, aggregate_levered_flows)

        # Weighted metrics
        weighted_ltv = (total_debt / total_price) if total_price > 0 else 0.0
        weighted_dscr_sum = sum(
            res.debt_sizing.dscr_year1 * res.debt_sizing.equity_required
            for res in self._results.values()
        )
        weighted_dscr = (weighted_dscr_sum / total_equity) if total_equity > 0 else 0.0

        weighted_cap_sum = sum(
            deal.exit_cap_rate * deal.purchase_price for deal in self._deals.values()
        )
        weighted_exit_cap = (weighted_cap_sum / total_price) if total_price > 0 else 0.0

        # Asset allocations and breakdowns
        allocations: List[PortfolioDealAllocation] = []
        asset_type_equity: Dict[str, float] = {}

        for deal_id, res in self._results.items():
            deal = self._deals[deal_id]
            eq = res.debt_sizing.equity_required
            pt = deal.property_type.value
            asset_type_equity[pt] = asset_type_equity.get(pt, 0.0) + eq

            weight = eq / total_equity if total_equity > 0 else 0.0
            allocations.append(
                PortfolioDealAllocation(
                    deal_id=deal_id,
                    deal_title=deal.title,
                    property_type=pt,
                    purchase_price=deal.purchase_price,
                    equity_allocated=eq,
                    loan_amount=res.debt_sizing.loan_amount,
                    levered_irr=res.deal_metrics.levered_irr,
                    equity_multiple=res.deal_metrics.equity_multiple,
                    weight_by_equity=round(weight, 4),
                )
            )

        asset_type_breakdown = (
            {pt: round(amt / total_equity, 4) for pt, amt in asset_type_equity.items()}
            if total_equity > 0
            else {}
        )

        return PortfolioRollup(
            portfolio_id=self.portfolio_id,
            portfolio_name=self.portfolio_name,
            deal_count=len(self._deals),
            total_units=total_units,
            total_gross_square_feet=round(total_sqft, 1),
            total_purchase_price=round(total_price, 2),
            total_equity_invested=round(total_equity, 2),
            total_debt_funded=round(total_debt, 2),
            weighted_ltv=round(weighted_ltv, 4),
            weighted_dscr=round(weighted_dscr, 3),
            weighted_exit_cap=round(weighted_exit_cap, 4),
            portfolio_levered_irr=round(port_lev_irr, 4),
            portfolio_unlevered_irr=round(port_unlev_irr, 4),
            portfolio_equity_multiple=round(port_em, 3),
            portfolio_npv=round(port_npv, 2),
            aggregate_annual_cash_flows=[round(f, 2) for f in aggregate_levered_flows],
            asset_type_breakdown=asset_type_breakdown,
            allocations=allocations,
        )

    def calculate_risk_profile(
        self,
        scenarios: Optional[List[PortfolioStressScenario]] = None,
    ) -> PortfolioRiskProfile:
        """Calculate concentration index (HHI) and execute joint stress testing."""
        rollup = self.generate_rollup()

        # 1. HHI Concentration Index
        # HHI = sum of (market_share_pct * 100)^2
        hhi = 0.0
        for frac in rollup.asset_type_breakdown.values():
            pct = frac * 100.0
            hhi += pct * pct
        hhi = round(hhi, 1)

        if hhi < 1800:
            rating = "High"
        elif hhi <= 3500:
            rating = "Moderate"
        else:
            rating = "Concentrated"

        top_conc = max(rollup.asset_type_breakdown.values()) if rollup.asset_type_breakdown else 0.0

        # 2. Macro Stress Scenarios
        if scenarios is None:
            scenarios = [
                PortfolioStressScenario(
                    name="Macro Rate Spike (+150 bps)",
                    description="Federal Reserve tightens; financing rate rises 150 bps and exit cap expands 50 bps.",
                    interest_rate_delta=0.015,
                    exit_cap_rate_delta=0.005,
                ),
                PortfolioStressScenario(
                    name="Recessionary Vacancy Shock",
                    description="Economic contraction causes 4% occupancy contraction and -1.5% rent growth drop.",
                    occupancy_delta=-0.04,
                    rent_growth_delta=-0.015,
                ),
                PortfolioStressScenario(
                    name="Combined Stagflation",
                    description="Simultaneous rent slowdown, rate increase (+100 bps), and exit cap expansion (+75 bps).",
                    rent_growth_delta=-0.02,
                    occupancy_delta=-0.03,
                    interest_rate_delta=0.01,
                    exit_cap_rate_delta=0.0075,
                ),
            ]

        stress_results: List[PortfolioStressResult] = []
        base_irr = rollup.portfolio_levered_irr

        for sc in scenarios:
            res = self._run_stress_scenario(sc, base_irr)
            stress_results.append(res)

        return PortfolioRiskProfile(
            portfolio_id=self.portfolio_id,
            hhi_concentration_index=hhi,
            diversification_rating=rating,
            top_asset_type_concentration_pct=round(top_conc, 4),
            stress_test_results=stress_results,
        )

    def _run_stress_scenario(
        self,
        scenario: PortfolioStressScenario,
        base_irr: float,
    ) -> PortfolioStressResult:
        """Underwrite portfolio under shocked macro parameters."""
        pipeline = DealPipeline(monte_carlo_iterations=200)
        stressed_equity = 0.0
        max_years = max((d.hold_period_years for d in self._deals.values()), default=5)
        stressed_flows = [0.0] * (max_years + 1)
        breach_deals: List[str] = []
        loss_deals: List[str] = []
        min_dscrs: List[float] = []

        for deal in self._deals.values():
            # Clone and stress deal
            stressed_deal = deal.model_copy(deep=True)
            stressed_deal.current_occupancy_pct = max(
                0.50, min(1.0, stressed_deal.current_occupancy_pct + scenario.occupancy_delta)
            )
            stressed_deal.market_occupancy_pct = max(
                0.50, min(1.0, stressed_deal.market_occupancy_pct + scenario.occupancy_delta)
            )
            stressed_deal.annual_rent_growth_pct = max(
                -0.05, stressed_deal.annual_rent_growth_pct + scenario.rent_growth_delta
            )
            stressed_deal.exit_cap_rate = max(
                0.03, stressed_deal.exit_cap_rate + scenario.exit_cap_rate_delta
            )
            stressed_deal.financing.interest_rate = max(
                0.02, stressed_deal.financing.interest_rate + scenario.interest_rate_delta
            )

            res = pipeline.run(stressed_deal)
            eq = res.debt_sizing.equity_required
            stressed_equity += eq

            for cf in res.cash_flows:
                if cf.year <= max_years:
                    stressed_flows[cf.year] += cf.net_cash_flow
                min_dscrs.append(cf.dscr)

            if res.debt_sizing.dscr_year1 < 1.05 or any(cf.dscr < 1.0 for cf in res.cash_flows):
                breach_deals.append(deal.id)
            if res.deal_metrics.levered_irr < 0.0:
                loss_deals.append(deal.id)

        stressed_flows[0] = -stressed_equity
        stressed_irr = calculate_irr(stressed_flows)
        drop_bps = round((base_irr - stressed_irr) * 10000.0, 1)

        return PortfolioStressResult(
            scenario_name=scenario.name,
            base_portfolio_irr=round(base_irr, 4),
            stressed_portfolio_irr=round(stressed_irr, 4),
            irr_drop_basis_points=drop_bps,
            stressed_min_dscr=round(min(min_dscrs), 3) if min_dscrs else 1.0,
            dscr_breach_deals=breach_deals,
            capital_loss_deals=loss_deals,
        )
