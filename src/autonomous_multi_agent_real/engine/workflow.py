"""Deal underwriting pipeline workflow engine coordinating the agent swarm."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Dict, List, Optional

from autonomous_multi_agent_real.engine.state import DealWorkflowContext
from autonomous_multi_agent_real.types import (
    InvestmentDecision,
    PropertyDeal,
    UnderwritingResult,
    WorkflowStage,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.collaboration.debate import DeliberationEngine
    from autonomous_multi_agent_real.engine.optimizer import DealOptimizer
    from autonomous_multi_agent_real.engine.sensitivity import SensitivityEngine
    from autonomous_multi_agent_real.engine.tax import TaxEngine
    from autonomous_multi_agent_real.engine.waterfall import WaterfallEngine
    from autonomous_multi_agent_real.rules.engine import RuleEngine


class DealPipeline:
    """Orchestrates multi-agent execution DAG for real estate deal underwriting."""

    def __init__(
        self,
        monte_carlo_iterations: int = 1000,
        random_seed: int = 42,
        rule_engine: Optional[RuleEngine] = None,
        deliberation_engine: Optional[DeliberationEngine] = None,
        waterfall_engine: Optional[WaterfallEngine] = None,
        sensitivity_engine: Optional[SensitivityEngine] = None,
        tax_engine: Optional[TaxEngine] = None,
        optimizer: Optional[DealOptimizer] = None,
        feature_interceptor: Optional[Any] = None,
        feature_coordinator: Optional[Any] = None,
    ):
        from autonomous_multi_agent_real.agents.acquisition import AcquisitionAgent
        from autonomous_multi_agent_real.agents.cashflow import CashFlowAgent
        from autonomous_multi_agent_real.agents.committee import InvestmentCommitteeAgent
        from autonomous_multi_agent_real.agents.debt import DebtAgent
        from autonomous_multi_agent_real.agents.market import MarketCompsAgent
        from autonomous_multi_agent_real.agents.risk import RiskMonteCarloAgent
        from autonomous_multi_agent_real.collaboration.debate import (
            DeliberationEngine as DelibEngine,
        )
        from autonomous_multi_agent_real.engine.optimizer import DealOptimizer as Optimizer
        from autonomous_multi_agent_real.engine.sensitivity import SensitivityEngine as SensEngine
        from autonomous_multi_agent_real.engine.tax import TaxEngine as TxEngine
        from autonomous_multi_agent_real.engine.waterfall import WaterfallEngine as WfEngine
        from autonomous_multi_agent_real.rules.engine import RuleEngine as RlEngine

        self.acquisition_agent = AcquisitionAgent()
        self.market_agent = MarketCompsAgent()
        self.debt_agent = DebtAgent()
        self.cashflow_agent = CashFlowAgent()
        self.risk_agent = RiskMonteCarloAgent(iterations=monte_carlo_iterations, seed=random_seed)
        self.committee_agent = InvestmentCommitteeAgent()

        self.rule_engine = rule_engine or RlEngine()
        self.deliberation_engine = deliberation_engine or DelibEngine()
        self.waterfall_engine = waterfall_engine or WfEngine()
        self.sensitivity_engine = sensitivity_engine or SensEngine()
        self.tax_engine = tax_engine or TxEngine()
        self.optimizer = optimizer or Optimizer()

        if feature_coordinator is not None and feature_interceptor is None:
            self.feature_interceptor = feature_coordinator.get_pipeline_interceptor()
        else:
            self.feature_interceptor = feature_interceptor


    def run(self, deal: PropertyDeal) -> UnderwritingResult:
        """Synchronously execute the full underwriting workflow on a deal."""
        start_time = time.perf_counter()
        context = DealWorkflowContext(deal=deal)

        # Stage 1: Intake & Acquisition Screening
        context.current_stage = WorkflowStage.INTAKE
        context.record_event("stage_start", "Beginning Acquisition Intake screening")
        acq_report = self.acquisition_agent.analyze(context)
        context.add_agent_report(acq_report)

        # Stage 2: Market Comps Analysis
        context.current_stage = WorkflowStage.MARKET_ANALYSIS
        context.record_event("stage_start", "Beginning Market Comps and rent benchmarking")
        market_report = self.market_agent.analyze(context)
        context.add_agent_report(market_report)

        # Stage 3: Debt Sizing
        context.current_stage = WorkflowStage.DEBT_SIZING
        context.record_event("stage_start", "Beginning Senior Debt Sizing across constraints")
        debt_report = self.debt_agent.analyze(context)
        context.add_agent_report(debt_report)

        # Stage 4: Cash Flow Waterfall Simulation
        context.current_stage = WorkflowStage.CASH_FLOW_SIMULATION
        context.record_event("stage_start", "Beginning Pro-Forma Cash Flow and returns modeling")
        cashflow_report = self.cashflow_agent.analyze(context)
        context.add_agent_report(cashflow_report)

        # Execute institutional core calculation engines
        if context.debt_sizing and context.cash_flows:
            # 4a. GP/LP Equity Waterfall
            net_flows = [cf.net_cash_flow for cf in context.cash_flows]
            context.waterfall = self.waterfall_engine.calculate(
                total_equity=context.debt_sizing.equity_required,
                annual_cash_flows=net_flows,
            )

            # 4b. Sensitivity & Breakeven
            context.breakeven = self.sensitivity_engine.calculate_breakeven_metrics(
                deal=deal,
                debt_sizing=context.debt_sizing,
            )
            context.sensitivity = self.sensitivity_engine.generate_cap_vs_rent_growth_matrix(
                deal=deal,
                debt_sizing=context.debt_sizing,
            )

            # 4c. Tax Depreciation & After-Tax Returns
            annual_nois = [cf.net_operating_income for cf in context.cash_flows]
            exit_proceeds = context.cash_flows[-1].exit_sale_proceeds if context.cash_flows else 0.0
            context.tax_analysis = self.tax_engine.analyze(
                deal=deal,
                debt_sizing=context.debt_sizing,
                annual_nois=annual_nois,
                exit_gross_proceeds=exit_proceeds,
            )

            # 4d. Pricing & Hurdle Optimization
            context.pricing_optimization = self.optimizer.solve_max_offer_price(
                deal=deal,
                target_levered_irr=0.15,
            )

        # Stage 5: Stochastic Risk & Monte Carlo Modeling
        context.current_stage = WorkflowStage.RISK_MODELING
        context.record_event("stage_start", "Beginning Monte Carlo cash flow stress testing")
        risk_report = self.risk_agent.analyze(context)
        context.add_agent_report(risk_report)

        # Multi-Agent Deliberation & Cross-Agent Challenge Protocol
        context.debate_transcript = self.deliberation_engine.conduct_deliberation(context)
        context.record_event(
            "deliberation_complete",
            f"Deliberation concluded with {context.debate_transcript.challenges_count} challenges",
        )

        # Institutional Compliance & Credit Policy Audit
        context.compliance_report = self.rule_engine.evaluate(context)
        context.record_event(
            "compliance_complete",
            f"Compliance audit: {context.compliance_report.passed_count}/{context.compliance_report.rules_checked} rules passed",
        )

        # Stage 6: Investment Committee Consensus
        context.current_stage = WorkflowStage.COMMITTEE_SYNTHESIS
        context.record_event("stage_start", "Formulating Investment Committee consensus memorandum")
        comm_report = self.committee_agent.analyze(context)
        context.add_agent_report(comm_report)

        context.current_stage = WorkflowStage.COMPLETED
        context.record_event(
            "workflow_complete", "Deal underwriting workflow concluded successfully"
        )

        duration = time.perf_counter() - start_time

        # Extract synthesis products
        metrics = context.deal_metrics
        debt_sizing = context.debt_sizing
        monte_carlo = context.monte_carlo

        if not metrics or not debt_sizing or not monte_carlo:
            raise RuntimeError("Pipeline failed to generate all mandatory underwriting outputs.")

        raw_decision = comm_report.key_metrics.get("investment_decision", "conditional")
        decision = InvestmentDecision(raw_decision)
        score = float(comm_report.key_metrics.get("composite_deal_score", 0.0))

        # Build investment thesis & risks
        thesis = [
            f"Opportunity to acquire {deal.total_units} units in {deal.address} at ${deal.purchase_price / deal.total_units:,.0f}/unit.",
            f"Mark-to-market upside of {market_report.key_metrics.get('mark_to_market_upside_pct', 0.0):.1%} (${market_report.key_metrics.get('annual_loss_to_lease', 0.0):,.0f}/yr).",
            f"Modeled baseline returns: {metrics.levered_irr:.1%} Levered IRR and {metrics.equity_multiple:.2f}x Equity Multiple over {deal.hold_period_years}-year hold.",
            f"Debt sized with safe DSCR profile starting at {debt_sizing.dscr_year1:.2f}x on a {debt_sizing.ltv_ratio:.1%} LTV basis.",
        ]

        risks_and_mitigants: List[Dict[str, str]] = []
        for flag in comm_report.risk_flags[:4]:
            risks_and_mitigants.append(
                {
                    "risk": flag,
                    "mitigant": "Structural reserves, conservative leverage, and disciplined asset management.",
                }
            )

        executive_summary = (
            f"Deal '{deal.title}' evaluated by autonomous multi-agent swarm. "
            f"Committee composite score: {score}/100 -> Decision: {decision.value.upper()}. "
            f"Target Levered IRR: {metrics.levered_irr:.1%} (Monte Carlo P50: {monte_carlo.p50_irr:.1%}). "
            f"Equity required: ${debt_sizing.equity_required:,.0f}."
        )

        return UnderwritingResult(
            deal_id=deal.id,
            deal_title=deal.title,
            decision=decision,
            committee_score=score,
            deal_metrics=metrics,
            debt_sizing=debt_sizing,
            cash_flows=context.cash_flows,
            monte_carlo=monte_carlo,
            agent_reports=context.agent_reports,
            executive_summary=executive_summary,
            investment_thesis=thesis,
            key_risks_and_mitigants=risks_and_mitigants,
            execution_time_seconds=round(duration, 3),
            waterfall=context.waterfall,
            sensitivity=context.sensitivity,
            breakeven=context.breakeven,
            tax_analysis=context.tax_analysis,
            pricing_optimization=context.pricing_optimization,
            compliance_report=context.compliance_report,
            debate_transcript=context.debate_transcript,
        )

    async def run_async(self, deal: PropertyDeal) -> UnderwritingResult:
        """Asynchronous execution wrapper."""
        return self.run(deal)
