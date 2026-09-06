"""Multi-agent challenge, committee debate, and consensus resolution protocol."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from autonomous_multi_agent_real.collaboration.protocol import (
    AgentMessage,
    Blackboard,
    MessageBus,
    MessageType,
)
from autonomous_multi_agent_real.types import (
    AgentRole,
    InvestmentDecision,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext


class DeliberationTopic(str, Enum):
    """Core underwriting debate topics."""

    CAPITAL_EXPENDITURE = "capital_expenditure"
    EXIT_VALUATION = "exit_valuation"
    RENT_GROWTH = "rent_growth"
    LEVERAGE_AND_DEBT = "leverage_and_debt"
    OCCUPANCY_STABILITY = "occupancy_stability"


class AgentChallenge(BaseModel):
    """Formal challenge raised by one agent against another agent's assumption."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    challenger: str = Field(..., description="Agent raising the challenge")
    target_agent: str = Field(..., description="Agent whose metric is contested")
    topic: DeliberationTopic
    contested_assumption: str
    evidence: str
    suggested_adjustment: str
    rebuttal_or_concession: Optional[str] = None
    resolved: bool = False
    conceded: bool = False


class DebateRound(BaseModel):
    """Single round of structured deliberation between swarm agents."""

    model_config = ConfigDict(extra="ignore")

    round_number: int
    challenges: List[AgentChallenge] = Field(default_factory=list)
    consensus_notes: List[str] = Field(default_factory=list)
    voting_tally: Dict[str, str] = Field(default_factory=dict)
    round_score: float = 0.0


class DebateTranscript(BaseModel):
    """Complete record of multi-agent debate and committee consensus."""

    model_config = ConfigDict(extra="ignore")

    deal_id: str
    total_rounds: int
    rounds: List[DebateRound] = Field(default_factory=list)
    challenges_count: int = 0
    concessions_count: int = 0
    final_verdict: InvestmentDecision
    consensus_score: float
    dissenting_opinions: List[Dict[str, str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeliberationEngine:
    """Orchestrates structured challenge-and-response deliberation between swarm agents."""

    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        blackboard: Optional[Blackboard] = None,
    ):
        self.bus = message_bus or MessageBus()
        self.blackboard = blackboard or Blackboard()

    def identify_challenges(self, context: DealWorkflowContext) -> List[AgentChallenge]:
        """Inspect context and agent reports to identify cross-agent friction points."""
        challenges: List[AgentChallenge] = []
        deal = context.deal
        debt = context.debt_sizing
        mc = context.monte_carlo

        # 1. Market Comps vs Acquisition: Rent Growth Aggressiveness
        if deal.annual_rent_growth_pct > 0.04:
            challenges.append(
                AgentChallenge(
                    challenger=AgentRole.MARKET_COMPS.value,
                    target_agent=AgentRole.ACQUISITION.value,
                    topic=DeliberationTopic.RENT_GROWTH,
                    contested_assumption=f"Rent growth modeled at {deal.annual_rent_growth_pct:.1%}/yr",
                    evidence="Submarket long-term trend average is 3.0-3.5%; premium may overestimate tenant absorption.",
                    suggested_adjustment="Model baseline at 3.0% with sensitivity up to 4.5%.",
                )
            )

        # 2. Risk Agent vs Cash Flow: Exit Cap Rate Compression
        if deal.exit_cap_rate <= 0.060:
            challenges.append(
                AgentChallenge(
                    challenger=AgentRole.RISK_SIMULATION.value,
                    target_agent=AgentRole.CASH_FLOW.value,
                    topic=DeliberationTopic.EXIT_VALUATION,
                    contested_assumption=f"Terminal exit cap rate of {deal.exit_cap_rate:.2%}",
                    evidence="Macro rate environment suggests terminal expansion of at least +50 bps over entry.",
                    suggested_adjustment="Expand terminal cap rate to at least 6.50% to prevent overstating exit proceeds.",
                )
            )

        # 3. Debt Agent vs Acquisition: Rehab contingency
        rehab_ratio = deal.rehab_budget / deal.purchase_price if deal.purchase_price > 0 else 0.0
        if rehab_ratio > 0.15:
            challenges.append(
                AgentChallenge(
                    challenger=AgentRole.DEBT_FINANCING.value,
                    target_agent=AgentRole.ACQUISITION.value,
                    topic=DeliberationTopic.CAPITAL_EXPENDITURE,
                    contested_assumption=f"Rehab budget of ${deal.rehab_budget:,.0f} ({rehab_ratio:.1%} of price)",
                    evidence="Heavy renovation poses construction delay and lease-up debt service risk.",
                    suggested_adjustment="Require 15% contingency escrow reserve ($"
                    + f"{deal.rehab_budget * 0.15:,.0f}) and guaranteed maximum price contract.",
                )
            )

        # 4. Cash Flow vs Debt: DSCR cushion
        if debt and debt.dscr_year1 < 1.30:
            challenges.append(
                AgentChallenge(
                    challenger=AgentRole.CASH_FLOW.value,
                    target_agent=AgentRole.DEBT_FINANCING.value,
                    topic=DeliberationTopic.LEVERAGE_AND_DEBT,
                    contested_assumption=f"Year 1 DSCR of {debt.dscr_year1:.2f}x",
                    evidence="Tight debt coverage leaves insufficient margin for economic vacancy shocks.",
                    suggested_adjustment="Lower loan sizing or add 6-12 months interest-only debt service period.",
                )
            )

        # 5. Risk Agent vs Occupancy Stability
        if mc and mc.probability_dscr_breach > 0.04:
            challenges.append(
                AgentChallenge(
                    challenger=AgentRole.RISK_SIMULATION.value,
                    target_agent=AgentRole.DEBT_FINANCING.value,
                    topic=DeliberationTopic.OCCUPANCY_STABILITY,
                    contested_assumption=f"Probability of DSCR covenant breach is {mc.probability_dscr_breach:.1%}",
                    evidence="Stochastic downside scenarios indicate vulnerability to 5% occupancy drop.",
                    suggested_adjustment="Establish operating deficit reserve funded from initial loan proceeds.",
                )
            )

        return challenges

    def conduct_deliberation(
        self,
        context: DealWorkflowContext,
        max_rounds: int = 2,
    ) -> DebateTranscript:
        """Run multi-agent debate rounds and formulate committee consensus."""
        challenges = self.identify_challenges(context)
        rounds: List[DebateRound] = []
        concessions_count = 0

        # Post initial facts onto blackboard
        self.blackboard.set_fact("deal_id", context.deal.id, author="system")
        self.blackboard.set_fact(
            "purchase_price", context.deal.purchase_price, author="acquisition"
        )
        if context.deal_metrics:
            self.blackboard.set_fact(
                "levered_irr", context.deal_metrics.levered_irr, author="cashflow"
            )
        if context.debt_sizing:
            self.blackboard.set_fact("dscr_year1", context.debt_sizing.dscr_year1, author="debt")

        # Round 1: Cross-examination & Rebuttals
        r1_challenges: List[AgentChallenge] = []
        r1_notes: List[str] = []

        for ch in challenges:
            # Publish challenge to message bus
            msg = AgentMessage(
                sender=ch.challenger,
                recipient=ch.target_agent,
                message_type=MessageType.CHALLENGE,
                topic=f"debate.{ch.topic.value}",
                content=f"Challenge on {ch.contested_assumption}: {ch.evidence}",
                payload={"suggested_adjustment": ch.suggested_adjustment},
            )
            self.bus.publish(msg)

            # Formulate automated resolution / concession logic
            if ch.topic in (
                DeliberationTopic.CAPITAL_EXPENDITURE,
                DeliberationTopic.OCCUPANCY_STABILITY,
            ):
                ch.rebuttal_or_concession = f"Target ({ch.target_agent}) CONCEDES: Agreed to establish proposed reserve/escrow requirement."
                ch.conceded = True
                ch.resolved = True
                concessions_count += 1
                r1_notes.append(
                    f"Resolved [{ch.topic.value}]: Conceded with covenant protective reserve."
                )
            else:
                ch.rebuttal_or_concession = f"Target ({ch.target_agent}) REBUTS with sensitivity defense: Baseline supported by comps; sensitivity matrix bounds downside."
                ch.conceded = False
                ch.resolved = True
                r1_notes.append(
                    f"Maintained [{ch.topic.value}]: Retained baseline with mandated downside sensitivity disclosure."
                )

            r1_challenges.append(ch)

        # Committee votes
        voting_tally: Dict[str, str] = {}
        for role, report in context.agent_reports.items():
            voting_tally[role] = report.status.value

        base_score = 75.0
        if context.deal_metrics:
            if context.deal_metrics.levered_irr >= 0.15:
                base_score += 10.0
            elif context.deal_metrics.levered_irr < 0.12:
                base_score -= 10.0
        if context.debt_sizing and context.debt_sizing.dscr_year1 < 1.25:
            base_score -= 5.0
        if concessions_count > 0:
            base_score += min(10.0, concessions_count * 3.0)

        round_score = round(min(100.0, max(0.0, base_score)), 1)

        rounds.append(
            DebateRound(
                round_number=1,
                challenges=r1_challenges,
                consensus_notes=r1_notes,
                voting_tally=voting_tally,
                round_score=round_score,
            )
        )

        # Committee Consensus Verdict Formulation
        dissenting: List[Dict[str, str]] = []
        for role, status in voting_tally.items():
            if status in ("rejected", "flagged"):
                rep = context.agent_reports.get(role)
                dissenting.append(
                    {
                        "agent": role,
                        "reason": rep.summary if rep else "Unresolved risk concerns",
                    }
                )

        if round_score >= 75.0 and len(dissenting) <= 1:
            verdict = InvestmentDecision.APPROVED
        elif round_score >= 58.0:
            verdict = InvestmentDecision.CONDITIONAL
        else:
            verdict = InvestmentDecision.REJECTED

        # Record deliberation conclusion in bus and blackboard
        self.bus.publish(
            AgentMessage(
                sender=AgentRole.INVESTMENT_COMMITTEE.value,
                recipient="*",
                message_type=MessageType.CONCURRENCE,
                topic="debate.consensus",
                content=f"Deliberation concluded with verdict: {verdict.value.upper()} (Score: {round_score}/100)",
                payload={"verdict": verdict.value, "score": round_score},
            )
        )
        self.blackboard.set_fact("final_verdict", verdict.value, author="committee")
        self.blackboard.set_fact("consensus_score", round_score, author="committee")

        return DebateTranscript(
            deal_id=context.deal.id,
            total_rounds=len(rounds),
            rounds=rounds,
            challenges_count=len(challenges),
            concessions_count=concessions_count,
            final_verdict=verdict,
            consensus_score=round_score,
            dissenting_opinions=dissenting,
        )
