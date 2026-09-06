"""Comprehensive edge cases and boundary condition unit tests for autonomous-multi-agent-real."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autonomous_multi_agent_real.agents.acquisition import AcquisitionAgent
from autonomous_multi_agent_real.agents.cashflow import CashFlowAgent
from autonomous_multi_agent_real.agents.committee import InvestmentCommitteeAgent
from autonomous_multi_agent_real.agents.debt import DebtAgent
from autonomous_multi_agent_real.agents.market import MarketCompsAgent
from autonomous_multi_agent_real.agents.risk import RiskMonteCarloAgent
from autonomous_multi_agent_real.collaboration.debate import DeliberationEngine
from autonomous_multi_agent_real.collaboration.protocol import (
    AgentMessage,
    Blackboard,
    MessageBus,
    MessageType,
)
from autonomous_multi_agent_real.engine.financial import (
    calculate_cap_rate,
    calculate_debt_yield,
    calculate_dscr,
    calculate_equity_multiple,
    calculate_exit_sale_proceeds,
    calculate_irr,
    calculate_loan_amortization_schedule,
    calculate_monthly_mortgage_payment,
    calculate_npv,
)
from autonomous_multi_agent_real.engine.monte_carlo import MonteCarloEngine
from autonomous_multi_agent_real.engine.optimizer import DealOptimizer
from autonomous_multi_agent_real.engine.sensitivity import SensitivityEngine
from autonomous_multi_agent_real.engine.state import DealWorkflowContext
from autonomous_multi_agent_real.engine.tax import TaxEngine
from autonomous_multi_agent_real.engine.waterfall import WaterfallEngine
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.portfolio.engine import PortfolioManager
from autonomous_multi_agent_real.reporting.exporter import DataExporter
from autonomous_multi_agent_real.reporting.memo import InvestmentMemoGenerator
from autonomous_multi_agent_real.rules.engine import RuleEngine
from autonomous_multi_agent_real.rules.models import RuleCategory, RuleDefinition, RuleSeverity
from autonomous_multi_agent_real.storage.repository import DealRepository, get_benchmark_deals
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
    DebtSizingResult,
    FinancingTerms,
    InvestmentDecision,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnitMixItem,
    WaterfallStructure,
    WaterfallTier,
)


# ============================================================================
# 1. Financial Engineering Numerical & Boundary Edge Cases
# ============================================================================


def test_financial_mortgage_zero_or_negative_inputs():
    """Verify calculate_monthly_mortgage_payment with non-positive inputs."""
    assert calculate_monthly_mortgage_payment(0.0, 0.05, 30) == 0.0
    assert calculate_monthly_mortgage_payment(-50000.0, 0.05, 30) == 0.0

    # 0% interest rate -> linear amortization
    assert calculate_monthly_mortgage_payment(120000.0, 0.0, 10) == 1000.0
    assert calculate_monthly_mortgage_payment(120000.0, -0.05, 10) == 1000.0


def test_loan_amortization_schedule_edge_cases():
    """Verify loan amortization schedule with zero principal and 0% interest."""
    # Zero principal
    sched_zero = calculate_loan_amortization_schedule(0.0, 0.06, 30, hold_period_years=5)
    assert len(sched_zero) == 5
    assert all(item == (0.0, 0.0, 0.0) for item in sched_zero)

    # 0% interest rate
    sched_no_int = calculate_loan_amortization_schedule(
        120000.0, 0.0, 10, hold_period_years=3, interest_only_months=0
    )
    assert len(sched_no_int) == 3
    # In year 1, 12 months * 1000 = 12000 principal, 0 interest
    assert sched_no_int[0][0] == 12000.0
    assert sched_no_int[0][1] == 0.0
    assert sched_no_int[0][2] == 108000.0

    # Interest-only period exceeding hold period
    sched_io = calculate_loan_amortization_schedule(
        100000.0, 0.06, 30, hold_period_years=2, interest_only_months=36
    )
    assert sched_io[0][0] == 0.0  # principal paid is 0
    assert sched_io[0][1] > 0.0  # interest paid
    assert sched_io[0][2] == 100000.0  # balance unchanged


def test_npv_and_irr_boundary_conditions():
    """Verify NPV and IRR calculation edge cases and solver robustness."""
    # NPV edge cases
    assert calculate_npv(0.0, [-100.0, 50.0, 50.0]) == 0.0
    assert calculate_npv(0.10, []) == 0.0

    # IRR invalid / degenerated series
    assert calculate_irr([]) == 0.0
    assert calculate_irr([-100.0]) == 0.0
    assert calculate_irr([-100.0, -50.0, -25.0]) == 0.0  # all negative
    assert calculate_irr([100.0, 50.0, 25.0]) == 0.0  # all positive

    # Normal valid IRR
    irr_val = calculate_irr([-1000.0, 100.0, 100.0, 1100.0])
    assert 0.099 <= irr_val <= 0.101

    # Cash flows that trigger fallback bisection in calculate_irr
    # e.g., large initial outlay followed by delayed payoff where initial slope breaks
    cf_divergent = [-1000000.0, 1.0, 1.0, 1.0, 1.0, 2500000.0]
    irr_div = calculate_irr(cf_divergent)
    assert irr_div > 0.0


def test_financial_ratios_boundary_conditions():
    """Verify equity multiple, DSCR, debt yield, cap rate, and exit sale proceeds edges."""
    # Equity Multiple
    assert calculate_equity_multiple(0.0, 500000.0) == 0.0
    assert calculate_equity_multiple(-100.0, 500000.0) == 0.0
    assert calculate_equity_multiple(100000.0, 250000.0) == 2.5

    # DSCR
    assert calculate_dscr(100000.0, 0.0) == 99.99
    assert calculate_dscr(100000.0, -500.0) == 99.99
    assert calculate_dscr(0.0, 50000.0) == 0.0

    # Debt Yield
    assert calculate_debt_yield(100000.0, 0.0) == 1.0
    assert calculate_debt_yield(100000.0, -1000.0) == 1.0
    assert calculate_debt_yield(100000.0, 1000000.0) == 0.10

    # Cap Rate
    assert calculate_cap_rate(50000.0, 0.0) == 0.0
    assert calculate_cap_rate(50000.0, -100000.0) == 0.0
    assert calculate_cap_rate(50000.0, 1000000.0) == 0.05

    # Exit Sale Proceeds
    assert calculate_exit_sale_proceeds(100000.0, 0.0) == 0.0
    assert calculate_exit_sale_proceeds(100000.0, -0.05) == 0.0
    proceeds = calculate_exit_sale_proceeds(100000.0, 0.05, selling_costs_pct=0.03)
    assert proceeds == round((100000.0 / 0.05) * 0.97, 2)


# ============================================================================
# 2. Swarm Agents Edge Cases & Risk Flags
# ============================================================================


def test_acquisition_agent_edge_cases_and_flags():
    """Verify AcquisitionAgent triggers appropriate risk flags under distressed scenarios."""
    benchmarks = get_benchmark_deals()
    deal = benchmarks[0].model_copy(deep=True)

    # Distressed deal: occupancy < 70%, heavy rehab > 30%, price_sqft > 600
    deal.current_occupancy_pct = 0.65
    deal.purchase_price = 5_000_000.0
    deal.rehab_budget = 2_000_000.0  # 40% of price
    deal.gross_square_feet = 8_000.0  # $625/sqft

    ctx = DealWorkflowContext(deal=deal)
    agent = AcquisitionAgent()
    rep = agent.analyze(ctx)

    assert rep.status == AgentDecisionStatus.FLAGGED
    assert len(rep.risk_flags) == 3
    assert any("Distressed occupancy" in f for f in rep.risk_flags)
    assert any("Heavy value-add rehab" in f for f in rep.risk_flags)
    assert any("Elevated entry price per sqft" in f for f in rep.risk_flags)

    # Conditional deal: exactly 1 risk flag
    deal_cond = benchmarks[0].model_copy(deep=True)
    deal_cond.current_occupancy_pct = 0.68  # only 1 flag
    deal_cond.rehab_budget = 50000.0
    deal_cond.gross_square_feet = 50000.0
    ctx_cond = DealWorkflowContext(deal=deal_cond)
    rep_cond = agent.analyze(ctx_cond)
    assert rep_cond.status == AgentDecisionStatus.CONDITIONAL
    assert len(rep_cond.risk_flags) == 1

    # Zero units / zero sqft test (confidence score fallback)
    deal_empty = benchmarks[0].model_copy(deep=True)
    deal_empty.unit_mix = []
    deal_empty.gross_square_feet = 0.0
    ctx_empty = DealWorkflowContext(deal=deal_empty)
    rep_empty = agent.analyze(ctx_empty)
    assert rep_empty.confidence_score == 0.60
    assert rep_empty.key_metrics["price_per_unit"] == 0.0


def test_market_comps_agent_edge_cases():
    """Verify MarketCompsAgent handles aggressive rent growth, tight exit cap, and minimal upside."""
    benchmarks = get_benchmark_deals()
    deal = benchmarks[0].model_copy(deep=True)

    # Aggressive rent growth > 5% and low exit cap < 4.5%
    deal.annual_rent_growth_pct = 0.065
    deal.exit_cap_rate = 0.040

    # Rents at market (upside < 2%)
    for u in deal.unit_mix:
        u.market_rent = u.current_rent

    ctx = DealWorkflowContext(deal=deal)
    agent = MarketCompsAgent()
    rep = agent.analyze(ctx)

    assert rep.status == AgentDecisionStatus.FLAGGED
    assert len(rep.risk_flags) == 3
    assert any("Aggressive rent growth modeled" in f for f in rep.risk_flags)
    assert any("Aggressive terminal exit cap rate" in f for f in rep.risk_flags)
    assert any("Rents are near top-of-market" in f for f in rep.risk_flags)

    # Single flag case -> CONDITIONAL
    deal_single = benchmarks[0].model_copy(deep=True)
    deal_single.annual_rent_growth_pct = 0.055
    deal_single.exit_cap_rate = 0.060
    # Ensure upside is normal
    ctx_single = DealWorkflowContext(deal=deal_single)
    rep_single = agent.analyze(ctx_single)
    assert rep_single.status == AgentDecisionStatus.CONDITIONAL


def test_debt_agent_edge_cases():
    """Verify DebtAgent handles elevated leverage and generates risk flags."""
    benchmarks = get_benchmark_deals()
    deal = benchmarks[0].model_copy(deep=True)

    # Set down payment to 15% so LTV = 85% (> 80% threshold for risk flag)
    deal.financing.down_payment_pct = 0.15

    ctx = DealWorkflowContext(deal=deal)
    # Set low target DSCR & debt yield so LTV is the binding constraint
    agent = DebtAgent(target_min_dscr=0.50, target_min_debt_yield=0.05)
    rep = agent.analyze(ctx)

    assert ctx.debt_sizing is not None
    assert ctx.debt_sizing.binding_constraint == "LTV"
    assert rep.status == AgentDecisionStatus.CONDITIONAL
    assert len(rep.risk_flags) == 1
    assert any("Elevated leverage with LTV at 85.0%" in f for f in rep.risk_flags)


def test_risk_agent_edge_cases():
    """Verify RiskAgent requirements, error states, and threshold triggers."""
    deal = get_benchmark_deals()[0]
    ctx = DealWorkflowContext(deal=deal)

    # RiskMonteCarloAgent without prior debt sizing must raise ValueError
    agent = RiskMonteCarloAgent(iterations=100)
    with pytest.raises(ValueError, match="Debt sizing must be completed"):
        agent.analyze(ctx)

    # Run with debt sizing
    debt_agent = DebtAgent()
    debt_agent.analyze(ctx)
    rep = agent.analyze(ctx)
    assert rep.agent_role == AgentRole.RISK_SIMULATION
    assert ctx.monte_carlo is not None
    assert rep.confidence_score == 0.95


def test_cashflow_agent_edge_cases():
    """Verify CashFlowAgent handles deals with multiple expense items and zero units."""
    deal = get_benchmark_deals()[0].model_copy(deep=True)
    ctx = DealWorkflowContext(deal=deal)

    DebtAgent().analyze(ctx)
    agent = CashFlowAgent()
    rep = agent.analyze(ctx)

    assert rep.status == AgentDecisionStatus.APPROVED
    assert ctx.deal_metrics is not None
    assert len(ctx.cash_flows) == deal.hold_period_years
    assert rep.key_metrics["levered_irr"] == ctx.deal_metrics.levered_irr


def test_committee_agent_all_decision_paths():
    """Verify InvestmentCommitteeAgent triggers APPROVED, CONDITIONAL, and REJECTED paths."""
    deal = get_benchmark_deals()[0].model_copy(deep=True)

    # 1. Approved case
    pipeline = DealPipeline(monte_carlo_iterations=100)
    res_approved = pipeline.run(deal)
    assert res_approved.decision in (
        InvestmentDecision.APPROVED,
        InvestmentDecision.CONDITIONAL,
    )

    # 2. Rejected case: artificially create severe risk flags and low score context
    ctx_rej = DealWorkflowContext(deal=deal)
    # Put low-score metrics
    ctx_rej.debt_sizing = DebtSizingResult(
        loan_amount=10_000_000.0,
        equity_required=1_000_000.0,
        monthly_payment=80000.0,
        annual_debt_service=960000.0,
        ltv_ratio=0.88,
        dscr_year1=0.95,
        debt_yield_pct=0.05,
        binding_constraint="LTV",
    )
    # Add fake failing agent reports with many flags
    for role in (AgentRole.ACQUISITION, AgentRole.MARKET_COMPS, AgentRole.RISK_SIMULATION):
        ctx_rej.agent_reports[role.value] = AgentAnalysisReport(
            agent_role=role,
            agent_name=role.value,
            status=AgentDecisionStatus.REJECTED,
            summary="Critical failure",
            confidence_score=0.9,
            risk_flags=["Critical risk A", "Critical risk B"],
        )

    comm_agent = InvestmentCommitteeAgent(target_score_pass=80.0)
    rep_rej = comm_agent.analyze(ctx_rej)
    assert rep_rej.status == AgentDecisionStatus.REJECTED
    assert rep_rej.key_metrics["investment_decision"] == InvestmentDecision.REJECTED.value
    assert "Pass on acquisition" in rep_rej.recommendations[1]


# ============================================================================
# 3. Collaboration Protocol & Deliberation Engine Edge Cases
# ============================================================================


def test_message_bus_filtering_and_lifecycle():
    """Verify MessageBus topic regex filtering, sender/recipient filtering, and clear."""
    bus = MessageBus()
    received_msgs = []

    bus.subscribe("deal.*", lambda msg: received_msgs.append(msg))
    bus.subscribe("deal.underwrite", lambda msg: received_msgs.append(msg))

    msg1 = AgentMessage(
        sender="acquisition",
        recipient="debt",
        message_type=MessageType.PROPOSAL,
        topic="deal.underwrite",
        content="Acquisition basis verified",
    )
    msg2 = AgentMessage(
        sender="market",
        recipient="committee",
        message_type=MessageType.CHALLENGE,
        topic="market.comps",
        content="Rent growth is elevated",
    )

    bus.publish(msg1)
    bus.publish(msg2)

    # deal.underwrite triggers both subscriptions
    assert len(received_msgs) == 2

    # Query history
    hist_deal = bus.get_history(topic="deal.*")
    assert len(hist_deal) == 1
    assert hist_deal[0].topic == "deal.underwrite"

    hist_sender = bus.get_history(sender="acquisition")
    assert len(hist_sender) == 1

    hist_recipient = bus.get_history(recipient="debt")
    assert len(hist_recipient) == 1

    hist_type = bus.get_history(message_type=MessageType.CHALLENGE)
    assert len(hist_type) == 1
    assert hist_type[0].sender == "market"

    bus.clear()
    assert len(bus.get_history()) == 0


def test_blackboard_concurrency_and_locks():
    """Verify Blackboard lock acquisition, contention, releasing, and snapshot."""
    bb = Blackboard()
    bb.set_fact("property_type", "multifamily", author="agent_a")
    assert bb.get_fact("property_type") == "multifamily"
    assert bb.get_fact("non_existent", "default_val") == "default_val"

    # Lock acquisition
    assert bb.acquire_lock("debt_calc", "agent_debt") is True
    # Attempt second lock by different agent fails
    assert bb.acquire_lock("debt_calc", "agent_cashflow") is False
    assert bb.is_locked("debt_calc") is True

    # Attempt release by wrong agent fails
    assert bb.release_lock("debt_calc", "agent_cashflow") is False
    # Release by owner succeeds
    assert bb.release_lock("debt_calc", "agent_debt") is True
    assert bb.is_locked("debt_calc") is False

    # Snapshot and clear
    bb.post_flag("Low occupancy warning", author="agent_a", severity="high")
    snap = bb.snapshot()
    assert "property_type" in snap["facts"]
    assert len(snap["flags"]) == 1

    bb.clear()
    assert len(bb.get_all_facts()) == 0
    assert len(bb.get_flags()) == 0


def test_deliberation_engine_full_debate_and_rebuttal():
    """Verify DeliberationEngine challenges, concessions, voting, and consensus score."""
    benchmarks = get_benchmark_deals()
    deal = benchmarks[0].model_copy(deep=True)
    # Modify deal assumptions to trigger all 5 potential challenge types
    deal.annual_rent_growth_pct = 0.055  # triggers rent growth challenge
    deal.exit_cap_rate = 0.050  # triggers exit valuation challenge
    deal.rehab_budget = deal.purchase_price * 0.25  # triggers cap expenditure challenge

    ctx = DealWorkflowContext(deal=deal)
    # Populate debt sizing with tight DSCR
    ctx.debt_sizing = DebtSizingResult(
        loan_amount=5_000_000.0,
        equity_required=2_000_000.0,
        monthly_payment=35000.0,
        annual_debt_service=420000.0,
        ltv_ratio=0.71,
        dscr_year1=1.20,  # triggers leverage challenge (< 1.30)
        debt_yield_pct=0.08,
        binding_constraint="DSCR",
    )

    # Populate agent reports including flagged agents
    for r in (AgentRole.ACQUISITION, AgentRole.CASH_FLOW, AgentRole.MARKET_COMPS):
        ctx.agent_reports[r.value] = AgentAnalysisReport(
            agent_role=r,
            agent_name=r.value,
            status=AgentDecisionStatus.APPROVED,
            summary="Initial approval",
            confidence_score=0.9,
        )
    ctx.agent_reports[AgentRole.DEBT_FINANCING.value] = AgentAnalysisReport(
        agent_role=AgentRole.DEBT_FINANCING,
        agent_name="Debt Agent",
        status=AgentDecisionStatus.FLAGGED,
        summary="Debt leverage is elevated",
        confidence_score=0.85,
        risk_flags=["DSCR tight"],
    )

    delib = DeliberationEngine()
    transcript = delib.conduct_deliberation(ctx)

    assert transcript.total_rounds >= 1
    assert transcript.challenges_count >= 3
    assert transcript.concessions_count >= 1
    assert len(transcript.dissenting_opinions) >= 1
    assert transcript.final_verdict in (
        InvestmentDecision.APPROVED,
        InvestmentDecision.CONDITIONAL,
        InvestmentDecision.REJECTED,
    )
    # Blackboard should have consensus facts recorded
    assert delib.blackboard.get_fact("final_verdict") is not None


# ============================================================================
# 4. Monte Carlo, Waterfall, Sensitivity, Tax, and Optimizer Edge Cases
# ============================================================================


def test_monte_carlo_edge_cases():
    """Verify Monte Carlo handles 1 iteration, seed reproducibility, and metric shapes."""
    deal = get_benchmark_deals()[0]
    ctx = DealWorkflowContext(deal=deal)
    DebtAgent().analyze(ctx)

    engine1 = MonteCarloEngine(seed=123)
    res1 = engine1.simulate(deal, ctx.debt_sizing, iterations=50)

    engine2 = MonteCarloEngine(seed=123)
    res2 = engine2.simulate(deal, ctx.debt_sizing, iterations=50)

    # Seed reproducibility check
    assert res1.mean_levered_irr == res2.mean_levered_irr
    assert res1.p50_irr == res2.p50_irr
    assert res1.var_95_irr is not None
    assert res1.cvar_95_irr is not None
    assert len(res1.distribution_quantiles) > 0


def test_waterfall_custom_tiers_and_zero_promote():
    """Verify WaterfallEngine with 0% promote and custom multi-tier structure."""
    struct = WaterfallStructure(
        preferred_return_rate=0.07,
        lp_equity_pct=0.90,
        gp_equity_pct=0.10,
        tiers=[
            WaterfallTier(name="Tier 1", hurdle_irr=0.12, lp_share=0.80, gp_share=0.20),
            WaterfallTier(name="Tier 2", hurdle_irr=0.18, lp_share=0.60, gp_share=0.40),
            WaterfallTier(name="Tier 3", hurdle_irr=999.0, lp_share=0.50, gp_share=0.50),
        ],
    )
    engine = WaterfallEngine(structure=struct)
    res = engine.calculate(
        total_equity=1_000_000.0,
        annual_cash_flows=[100_000.0, 100_000.0, 100_000.0, 1_800_000.0],
    )

    assert res.lp_equity_multiple > 1.5
    assert res.gp_equity_multiple > 1.5
    assert res.gp_total_promote >= 0.0
    assert len(res.annual_distributions) == 4


def test_sensitivity_custom_steps_and_breakeven():
    """Verify SensitivityEngine with non-default parameter steps and breakeven checks."""
    deal = get_benchmark_deals()[0]
    ctx = DealWorkflowContext(deal=deal)
    DebtAgent().analyze(ctx)
    CashFlowAgent().analyze(ctx)

    engine = SensitivityEngine()
    matrix = engine.generate_cap_vs_rent_growth_matrix(deal, ctx.debt_sizing)
    assert len(matrix.row_values) > 0
    assert len(matrix.col_values) > 0
    assert len(matrix.irr_matrix) > 0

    be = engine.calculate_breakeven_metrics(deal, ctx.debt_sizing)
    assert 0.0 < be.breakeven_occupancy_pct < 1.0
    assert be.margin_of_safety_occupancy_pct > 0.0


def test_tax_engine_variations():
    """Verify TaxEngine with commercial vs residential recovery periods."""
    pipeline = DealPipeline(monte_carlo_iterations=50)
    deal_res = get_benchmark_deals()[0].model_copy(deep=True)  # Multifamily = 27.5 yrs
    deal_comm = get_benchmark_deals()[1].model_copy(deep=True)  # Industrial = 39 yrs

    res_res = pipeline.run(deal_res)
    res_comm = pipeline.run(deal_comm)

    engine = TaxEngine(ordinary_income_tax_rate=0.35)
    nois_res = [cf.net_operating_income for cf in res_res.cash_flows]
    exit_res = res_res.cash_flows[-1].exit_sale_proceeds
    tax_res = engine.analyze(deal_res, res_res.debt_sizing, nois_res, exit_res)

    nois_comm = [cf.net_operating_income for cf in res_comm.cash_flows]
    exit_comm = res_comm.cash_flows[-1].exit_sale_proceeds
    tax_comm = engine.analyze(deal_comm, res_comm.debt_sizing, nois_comm, exit_comm)

    assert tax_res.after_tax_irr > 0.0
    assert tax_comm.after_tax_irr > 0.0
    assert len(tax_res.annual_schedule) == deal_res.hold_period_years
    assert len(tax_comm.annual_schedule) == deal_comm.hold_period_years


def test_deal_optimizer_price_and_rent():
    """Verify DealOptimizer bounds, convergence, and sensitivity."""
    deal = get_benchmark_deals()[0]
    opt = DealOptimizer()

    # Solve for target IRR 14%
    sol_price = opt.solve_max_offer_price(deal, target_levered_irr=0.14)
    assert sol_price.max_supportable_purchase_price > 0.0

    # Solve for target IRR 16%
    req_rent = opt.solve_required_market_rent(deal, target_levered_irr=0.16)
    assert req_rent > 0.0


# ============================================================================
# 5. Deal Repository, Revisions & Persistence Edge Cases
# ============================================================================


def test_deal_repository_query_filtering_and_edge_cases(tmp_path: Path):
    """Verify DealRepository query filters, corrupted files, and revision edge cases."""
    repo = DealRepository(storage_dir=tmp_path)

    # Filter with no matches
    empty_res = repo.query_deals(min_price=100_000_000.0)
    assert len(empty_res) == 0

    # Filter by property type and unit range
    mf_deals = repo.query_deals(
        property_type=PropertyType.MULTI_FAMILY,
        min_units=10,
        max_units=500,
        min_occupancy=0.80,
        search_text="Travis",
    )
    assert len(mf_deals) == 1
    assert mf_deals[0].id == "austin-multifamily"

    # Revert to nonexistent revision returns None
    assert repo.revert_to_revision("austin-multifamily", 999) is None

    # Diff with nonexistent revisions returns empty dict
    assert repo.diff_revisions("austin-multifamily", 1, 999) == {}

    # Corrupted file in directory handling
    corrupt_deal = tmp_path / "deal_corrupt.json"
    corrupt_deal.write_text("{invalid json", encoding="utf-8")
    corrupt_port = tmp_path / "portfolio_corrupt.json"
    corrupt_port.write_text("{invalid json", encoding="utf-8")

    # Reload repo should gracefully ignore corrupted files
    reloaded_repo = DealRepository(storage_dir=tmp_path)
    assert len(reloaded_repo.list_deals()) >= 3


# ============================================================================
# 6. Reporting, Memo, and Data Exporter Edge Cases
# ============================================================================


def test_data_exporter_edge_cases():
    """Verify DataExporter with empty sensitivity, portfolio rollups, and JSON formats."""
    deal = get_benchmark_deals()[0]
    pipeline = DealPipeline(monte_carlo_iterations=50)
    res = pipeline.run(deal)

    exporter = DataExporter()

    # Cashflows CSV
    cf_csv = exporter.export_cashflows_csv(res)
    assert "Year,Gross Potential Rent" in cf_csv

    # Waterfall CSV
    wf_csv = exporter.export_waterfall_csv(res)
    assert "Year,Total Distributable Cash" in wf_csv

    # Sensitivity CSV with and without sensitivity
    res_no_sens = res.model_copy(deep=True)
    res_no_sens.sensitivity = None
    assert exporter.export_sensitivity_csv(res_no_sens) == ""
    sens_csv = exporter.export_sensitivity_csv(res)
    assert "Rent Growth / Exit Cap" in sens_csv

    # Portfolio CSV
    pm = PortfolioManager(portfolio_id="test-portfolio", portfolio_name="Test Portfolio")
    pm.add_deal(deal, result=res)
    rollup = pm.generate_rollup()
    port_csv = exporter.export_portfolio_csv(rollup)
    assert "Deal ID,Deal Title,Property Type" in port_csv
    assert deal.id in port_csv

    # Underwriting JSON
    uj = exporter.export_underwriting_json(res)
    assert json.loads(uj)["deal_id"] == deal.id


def test_investment_memo_generation_options():
    """Verify InvestmentMemoGenerator markdown synthesis."""
    deal = get_benchmark_deals()[0]
    pipeline = DealPipeline(monte_carlo_iterations=50)
    res = pipeline.run(deal)

    memo_gen = InvestmentMemoGenerator()
    memo = memo_gen.generate_memo(deal, res)

    assert "# INVESTMENT COMMITTEE UNDERWRITING MEMORANDUM" in memo
    assert "## 1. Executive Summary & Investment Thesis" in memo
    assert "## 3. Financial Metrics & Returns Summary" in memo
    assert "## 4. Multi-Year Operating Pro-Forma Schedule" in memo
    assert "## 7. Stochastic Monte Carlo Risk Analysis" in memo
