"""Market comparables and rental rate benchmarking agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autonomous_multi_agent_real.agents.base import BaseAgent
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext


class MarketCompsAgent(BaseAgent):
    """Benchmarks in-place rents against market comparables and analyzes loss-to-lease."""

    def __init__(self):
        super().__init__(
            role=AgentRole.MARKET_COMPS,
            name="Market Comps & Rent Agent",
            description="Analyzes market rent comps, loss-to-lease upside, submarket occupancy, and cap rate spreads.",
        )

    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport:
        deal = context.deal
        current_monthly = deal.total_current_monthly_rent
        market_monthly = deal.total_market_monthly_rent

        monthly_loss_to_lease = max(0.0, market_monthly - current_monthly)
        annual_loss_to_lease = monthly_loss_to_lease * 12.0
        upside_pct = (monthly_loss_to_lease / current_monthly) if current_monthly > 0 else 0.0

        risk_flags = []
        recommendations = []

        if deal.annual_rent_growth_pct > 0.05:
            risk_flags.append(
                f"Aggressive rent growth modeled at {deal.annual_rent_growth_pct:.1%}/yr exceeds historical 3.0-4.0% submarket trend."
            )
            recommendations.append(
                "Stress-test returns with conservative 2.5% long-term rent growth."
            )

        if deal.exit_cap_rate < 0.045:
            risk_flags.append(
                f"Aggressive terminal exit cap rate of {deal.exit_cap_rate:.2%}; reflects high vulnerability to cap rate expansion."
            )
            recommendations.append("Expand exit cap rate by at least 50 bps over entry cap rate.")

        if upside_pct > 0.12:
            recommendations.append(
                f"Capture substantial {upside_pct:.1%} loss-to-lease (${annual_loss_to_lease:,.0f}/yr) via interior turn program."
            )
        elif upside_pct < 0.02:
            risk_flags.append(
                "Rents are near top-of-market with minimal organic mark-to-market upside (< 2%)."
            )

        if len(risk_flags) >= 2:
            status = AgentDecisionStatus.FLAGGED
        elif len(risk_flags) == 1:
            status = AgentDecisionStatus.CONDITIONAL
        else:
            status = AgentDecisionStatus.APPROVED

        confidence_score = 0.90

        metrics = {
            "current_monthly_rent": round(current_monthly, 2),
            "market_monthly_rent": round(market_monthly, 2),
            "monthly_loss_to_lease": round(monthly_loss_to_lease, 2),
            "annual_loss_to_lease": round(annual_loss_to_lease, 2),
            "mark_to_market_upside_pct": round(upside_pct, 4),
            "modeled_rent_growth_pct": round(deal.annual_rent_growth_pct, 4),
            "exit_cap_rate": round(deal.exit_cap_rate, 4),
            "submarket_occupancy_pct": round(deal.market_occupancy_pct, 4),
        }

        summary = (
            f"Mark-to-market rent analysis indicates ${annual_loss_to_lease:,.0f}/yr upside ({upside_pct:.1%}). "
            f"Submarket occupancy: {deal.market_occupancy_pct:.1%}. Status: {status.value.upper()}."
        )

        return AgentAnalysisReport(
            agent_role=self.role,
            agent_name=self.name,
            status=status,
            summary=summary,
            confidence_score=confidence_score,
            key_metrics=metrics,
            risk_flags=risk_flags,
            recommendations=recommendations,
        )
