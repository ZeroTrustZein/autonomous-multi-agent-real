"""Investment committee synthesis and underwriting memorandum agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autonomous_multi_agent_real.agents.base import BaseAgent
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
    InvestmentDecision,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext


class InvestmentCommitteeAgent(BaseAgent):
    """Synthesizes swarm agent findings, computes composite deal score, and issues verdict."""

    def __init__(self, target_score_pass: float = 75.0):
        super().__init__(
            role=AgentRole.INVESTMENT_COMMITTEE,
            name="Investment Committee Synthesis Agent",
            description="Aggregates all agent findings, scores the opportunity (0-100), and formulates final decision.",
        )
        self.target_score_pass = target_score_pass

    def calculate_deal_score(self, context: DealWorkflowContext) -> float:
        """Calculate composite 0-100 underwriting score across 4 pillars."""
        score = 0.0
        metrics = context.deal_metrics
        debt = context.debt_sizing
        sim = context.monte_carlo

        if metrics:
            # 1. Return Pillar (max 35 pts)
            irr = metrics.levered_irr
            if irr >= 0.18:
                score += 20.0
            elif irr >= 0.14:
                score += 15.0
            elif irr >= 0.10:
                score += 10.0
            else:
                score += max(0.0, irr * 100.0)

            em = metrics.equity_multiple
            if em >= 2.0:
                score += 15.0
            elif em >= 1.7:
                score += 12.0
            elif em >= 1.4:
                score += 8.0
            else:
                score += max(0.0, (em - 1.0) * 15.0)

        if debt:
            # 2. Debt Safety Pillar (max 25 pts)
            dscr = debt.dscr_year1
            if dscr >= 1.40:
                score += 15.0
            elif dscr >= 1.25:
                score += 12.0
            elif dscr >= 1.15:
                score += 7.0
            else:
                score += 2.0

            ltv = debt.ltv_ratio
            if ltv <= 0.65:
                score += 10.0
            elif ltv <= 0.75:
                score += 8.0
            elif ltv <= 0.80:
                score += 5.0
            else:
                score += 1.0

        if sim:
            # 3. Downside Resilience Pillar (max 25 pts)
            if sim.probability_dscr_breach <= 0.01:
                score += 15.0
            elif sim.probability_dscr_breach <= 0.05:
                score += 10.0
            elif sim.probability_dscr_breach <= 0.10:
                score += 5.0

            if sim.p10_irr >= 0.10:
                score += 10.0
            elif sim.p10_irr >= 0.06:
                score += 7.0
            elif sim.p10_irr >= 0.02:
                score += 4.0

        # 4. Market & Basis Upside Pillar (max 15 pts)
        market_report = context.agent_reports.get(AgentRole.MARKET_COMPS.value)
        if market_report:
            upside = market_report.key_metrics.get("mark_to_market_upside_pct", 0.0)
            if upside >= 0.10:
                score += 10.0
            elif upside >= 0.05:
                score += 7.0
            else:
                score += 4.0

        rehab_ratio = (
            context.deal.rehab_budget / context.deal.purchase_price
            if context.deal.purchase_price > 0
            else 0.0
        )
        if 0.05 <= rehab_ratio <= 0.20:
            score += 5.0
        else:
            score += 3.0

        return round(min(100.0, max(0.0, score)), 1)

    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport:
        deal_score = self.calculate_deal_score(context)

        # Collect risk flags from other agents
        all_flags = []
        for role, rep in context.agent_reports.items():
            if role != self.role.value:
                all_flags.extend(rep.risk_flags)

        # Determine decision
        if deal_score >= self.target_score_pass and len(all_flags) <= 2:
            verdict = InvestmentDecision.APPROVED
            agent_status = AgentDecisionStatus.APPROVED
        elif deal_score >= 60.0:
            verdict = InvestmentDecision.CONDITIONAL
            agent_status = AgentDecisionStatus.CONDITIONAL
        else:
            verdict = InvestmentDecision.REJECTED
            agent_status = AgentDecisionStatus.REJECTED

        recommendations = [
            f"Consensus Verdict: {verdict.value.upper()} with overall composite score of {deal_score}/100.",
        ]
        if verdict == InvestmentDecision.APPROVED:
            recommendations.append(
                "Issue non-binding letter of intent (LOI) with 30-day inspection period."
            )
        elif verdict == InvestmentDecision.CONDITIONAL:
            recommendations.append(
                "Require 5-8% purchase price reduction or seller credit to satisfy return hurdles."
            )
        else:
            recommendations.append("Pass on acquisition due to inadequate risk-adjusted returns.")

        summary = (
            f"Investment Committee synthesized swarm reports: Deal scored {deal_score}/100. "
            f"Consensus Verdict: {verdict.value.upper()}. Total identified risk flags: {len(all_flags)}."
        )

        return AgentAnalysisReport(
            agent_role=self.role,
            agent_name=self.name,
            status=agent_status,
            summary=summary,
            confidence_score=0.96,
            key_metrics={
                "composite_deal_score": deal_score,
                "investment_decision": verdict.value,
                "total_upstream_risk_flags": len(all_flags),
            },
            risk_flags=all_flags,
            recommendations=recommendations,
        )
