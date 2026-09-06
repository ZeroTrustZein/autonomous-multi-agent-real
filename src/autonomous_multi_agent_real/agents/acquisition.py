"""Acquisition and deal intake screening agent."""

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


class AcquisitionAgent(BaseAgent):
    """Evaluates initial property metrics, basis, square footage, and unit mix economics."""

    def __init__(self):
        super().__init__(
            role=AgentRole.ACQUISITION,
            name="Acquisition & Intake Agent",
            description="Evaluates purchase price, per-unit metrics, basis sanity, and unit mix economics.",
        )

    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport:
        deal = context.deal
        units = deal.total_units
        price = deal.purchase_price
        basis = deal.total_acquisition_basis

        price_per_unit = price / units if units > 0 else 0.0
        basis_per_unit = basis / units if units > 0 else 0.0
        price_per_sqft = price / deal.gross_square_feet if deal.gross_square_feet > 0 else 0.0
        basis_per_sqft = basis / deal.gross_square_feet if deal.gross_square_feet > 0 else 0.0

        current_annual_rent = deal.total_current_annual_rent
        grm = price / current_annual_rent if current_annual_rent > 0 else 0.0

        risk_flags = []
        recommendations = []

        if deal.current_occupancy_pct < 0.70:
            risk_flags.append(
                f"Distressed occupancy ({deal.current_occupancy_pct:.1%}); requires substantial lease-up bridge."
            )
            recommendations.append("Structure interest-only debt reserve during lease-up phase.")

        rehab_ratio = deal.rehab_budget / price if price > 0 else 0.0
        if rehab_ratio > 0.30:
            risk_flags.append(
                f"Heavy value-add rehab budget is {rehab_ratio:.1%} of purchase price; execution risk is high."
            )
            recommendations.append(
                "Require contractor guaranteed maximum price (GMP) contract and completion bond."
            )

        if price_per_sqft > 600.0:
            risk_flags.append(
                f"Elevated entry price per sqft (${price_per_sqft:,.2f}) relative to asset class baseline."
            )

        # Determine agent status
        if len(risk_flags) >= 2:
            status = AgentDecisionStatus.FLAGGED
        elif len(risk_flags) == 1:
            status = AgentDecisionStatus.CONDITIONAL
        else:
            status = AgentDecisionStatus.APPROVED
            recommendations.append("Proceed with deep market comps and debt sizing analysis.")

        confidence_score = 0.95 if units > 0 and deal.gross_square_feet > 0 else 0.60

        metrics = {
            "total_units": units,
            "gross_square_feet": deal.gross_square_feet,
            "purchase_price": price,
            "total_acquisition_basis": basis,
            "price_per_unit": round(price_per_unit, 2),
            "basis_per_unit": round(basis_per_unit, 2),
            "price_per_sqft": round(price_per_sqft, 2),
            "basis_per_sqft": round(basis_per_sqft, 2),
            "gross_rent_multiplier": round(grm, 2),
            "rehab_to_price_ratio": round(rehab_ratio, 3),
        }

        summary = (
            f"Screened {units}-unit property ({deal.gross_square_feet:,.0f} sqft) at "
            f"${price_per_unit:,.0f}/unit (${price_per_sqft:,.0f}/sqft). Total basis: ${basis:,.0f}. "
            f"GRM: {grm:.2f}x. Status: {status.value.upper()}."
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
