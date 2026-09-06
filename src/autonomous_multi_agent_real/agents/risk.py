"""Monte Carlo stochastic risk modeling and stress testing agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autonomous_multi_agent_real.agents.base import BaseAgent
from autonomous_multi_agent_real.engine.monte_carlo import MonteCarloEngine
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext


class RiskMonteCarloAgent(BaseAgent):
    """Executes stochastic simulations across rent, vacancy, expenses, and exit cap rate."""

    def __init__(self, iterations: int = 1000, seed: int = 42):
        super().__init__(
            role=AgentRole.RISK_SIMULATION,
            name="Risk & Monte Carlo Agent",
            description="Executes 1,000+ stochastic iterations to compute return percentiles, VaR, and default probabilities.",
        )
        self.iterations = iterations
        self.engine = MonteCarloEngine(seed=seed)

    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport:
        deal = context.deal
        debt = context.debt_sizing
        if debt is None:
            raise ValueError("Debt sizing must be completed before running risk simulations.")

        # Execute simulation
        sim_result = self.engine.simulate(
            deal=deal,
            debt_sizing=debt,
            iterations=self.iterations,
        )
        context.monte_carlo = sim_result

        risk_flags = []
        recommendations = []

        if sim_result.probability_dscr_breach > 0.05:
            risk_flags.append(
                f"Elevated default risk: {sim_result.probability_dscr_breach:.1%} chance of DSCR breaching covenant (< 1.0x)."
            )
            recommendations.append(
                "Increase interest reserve escrow to absorb unexpected occupancy drawdowns."
            )

        if sim_result.probability_negative_irr > 0.03:
            risk_flags.append(
                f"Capital loss risk: {sim_result.probability_negative_irr:.1%} probability of negative cumulative return."
            )

        if sim_result.p10_irr < 0.07:
            risk_flags.append(
                f"Severe downside case: 10th percentile IRR is {sim_result.p10_irr:.1%}, below cost of capital."
            )
            recommendations.append("Negotiate a lower acquisition basis or cap loan LTV to 65%.")

        if not risk_flags:
            status = AgentDecisionStatus.APPROVED
            recommendations.append(
                "Downside tail risk is well contained across 1,000 stochastic scenarios."
            )
        elif len(risk_flags) == 1:
            status = AgentDecisionStatus.CONDITIONAL
        else:
            status = AgentDecisionStatus.FLAGGED

        confidence_score = 0.95

        metrics = {
            "iterations": sim_result.iterations,
            "mean_irr": sim_result.mean_levered_irr,
            "median_irr_p50": sim_result.p50_irr,
            "downside_irr_p10": sim_result.p10_irr,
            "upside_irr_p90": sim_result.p90_irr,
            "probability_negative_irr": sim_result.probability_negative_irr,
            "probability_dscr_breach": sim_result.probability_dscr_breach,
            "mean_equity_multiple": sim_result.mean_equity_multiple,
            "p10_equity_multiple": sim_result.p10_equity_multiple,
        }

        summary = (
            f"Simulated {sim_result.iterations:,} runs: Median IRR: {sim_result.p50_irr:.1%}, "
            f"P10-P90 range: [{sim_result.p10_irr:.1%}, {sim_result.p90_irr:.1%}], "
            f"DSCR breach prob: {sim_result.probability_dscr_breach:.1%}. Status: {status.value.upper()}."
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
