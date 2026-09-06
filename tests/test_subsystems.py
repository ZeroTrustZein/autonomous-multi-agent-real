"""Comprehensive test suite for Stage 4 subsystems: collaboration, rules, portfolio, reporting, and storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from autonomous_multi_agent_real.cli.main import cli
from autonomous_multi_agent_real.collaboration.debate import (
    DeliberationEngine,
    DeliberationTopic,
)
from autonomous_multi_agent_real.collaboration.protocol import (
    AgentMessage,
    Blackboard,
    MessageBus,
    MessageType,
)
from autonomous_multi_agent_real.engine.state import DealWorkflowContext
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.portfolio.engine import PortfolioManager
from autonomous_multi_agent_real.reporting.exporter import DataExporter
from autonomous_multi_agent_real.reporting.memo import InvestmentMemoGenerator
from autonomous_multi_agent_real.rules.engine import (
    RuleEngine,
    get_default_institutional_rules,
)
from autonomous_multi_agent_real.rules.models import (
    RuleCategory,
    RuleDefinition,
    RuleSeverity,
)
from autonomous_multi_agent_real.storage.repository import (
    DealRepository,
    get_benchmark_deals,
)
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
    DebtSizingResult,
    PropertyDeal,
    PropertyType,
)

# --------------------------------------------------------------------------
# 1. Collaboration & Protocol Subsystem Tests
# --------------------------------------------------------------------------


def test_message_bus_publish_subscribe_and_wildcards():
    """Verify in-memory message broker with wildcard pattern routing."""
    bus = MessageBus()
    received: list[AgentMessage] = []

    def debt_handler(msg: AgentMessage):
        received.append(msg)

    # Subscribe to wildcard pattern
    bus.subscribe("debt.*", debt_handler)

    msg1 = AgentMessage(
        sender="acquisition",
        recipient="debt_financing",
        message_type=MessageType.PROPOSAL,
        topic="debt.sizing",
        content="Requesting loan sizing under 75% LTV",
        payload={"ltv": 0.75},
    )
    msg2 = AgentMessage(
        sender="risk_simulation",
        recipient="*",
        message_type=MessageType.CHALLENGE,
        topic="market.rent",
        content="Rent growth is unrealistic",
    )
    msg3 = AgentMessage(
        sender="cash_flow",
        recipient="debt_financing",
        message_type=MessageType.QUERY,
        topic="debt.dscr",
        content="Is DSCR above 1.25x?",
    )

    bus.publish(msg1)
    bus.publish(msg2)
    bus.publish(msg3)

    # Received should capture debt.sizing and debt.dscr, but not market.rent
    assert len(received) == 2
    assert received[0].topic == "debt.sizing"
    assert received[1].topic == "debt.dscr"

    # History verification
    all_history = bus.get_history()
    assert len(all_history) == 3

    debt_history = bus.get_history(topic="debt.*")
    assert len(debt_history) == 2

    # Unsubscribe
    bus.unsubscribe("debt.*", debt_handler)
    bus.publish(msg1)
    assert len(received) == 2  # No new messages delivered to handler


def test_blackboard_facts_flags_and_locks():
    """Verify shared blackboard memory, risk flags, and mutual exclusion locking."""
    bb = Blackboard()

    # Fact storage
    bb.set_fact("purchase_price", 5000000.0, author="acquisition")
    assert bb.get_fact("purchase_price") == 5000000.0
    assert bb.get_fact("non_existent", default=42) == 42

    meta = bb.get_fact_metadata("purchase_price")
    assert meta is not None
    assert meta["author"] == "acquisition"

    # Risk flags
    bb.post_flag("High rehab execution risk", author="acquisition", severity="warning")
    bb.post_flag("DSCR below 1.15x covenant", author="debt", severity="error")

    all_flags = bb.get_flags()
    assert len(all_flags) == 2
    error_flags = bb.get_flags(severity="error")
    assert len(error_flags) == 1
    assert error_flags[0]["author"] == "debt"

    # Resource locks
    assert bb.acquire_lock("exit_cap_rate", agent_name="cashflow") is True
    assert bb.is_locked("exit_cap_rate") is True
    # Another agent cannot acquire the same lock
    assert bb.acquire_lock("exit_cap_rate", agent_name="risk") is False
    # Same agent can re-acquire
    assert bb.acquire_lock("exit_cap_rate", agent_name="cashflow") is True
    # Wrong agent cannot release lock
    assert bb.release_lock("exit_cap_rate", agent_name="risk") is False
    # Correct agent releases lock
    assert bb.release_lock("exit_cap_rate", agent_name="cashflow") is True
    assert bb.is_locked("exit_cap_rate") is False

    # Snapshot
    snap = bb.snapshot()
    assert "facts" in snap
    assert "flags" in snap
    assert snap["facts"]["purchase_price"] == 5000000.0


def test_deliberation_engine_challenges_and_debate(sample_deal: PropertyDeal):
    """Verify cross-agent challenge identification, structured debate rounds, and consensus."""
    engine = DeliberationEngine()
    ctx = DealWorkflowContext(deal=sample_deal)

    # Populate basic mock sizing and reports
    ctx.debt_sizing = DebtSizingResult(
        loan_amount=2500000.0,
        equity_required=1780000.0,
        monthly_payment=15000.0,
        annual_debt_service=180000.0,
        ltv_ratio=0.625,
        dscr_year1=1.22,  # Triggers cashflow challenge (< 1.30)
        debt_yield_pct=0.088,
        binding_constraint="LTV",
    )
    ctx.agent_reports[AgentRole.ACQUISITION.value] = AgentAnalysisReport(
        agent_role=AgentRole.ACQUISITION,
        agent_name="Acquisition Agent",
        status=AgentDecisionStatus.APPROVED,
        summary="Acquisition approved",
        confidence_score=0.95,
    )
    ctx.agent_reports[AgentRole.MARKET_COMPS.value] = AgentAnalysisReport(
        agent_role=AgentRole.MARKET_COMPS,
        agent_name="Market Comps Agent",
        status=AgentDecisionStatus.APPROVED,
        summary="Comps aligned",
        confidence_score=0.92,
    )

    challenges = engine.identify_challenges(ctx)
    assert len(challenges) > 0
    # At least one challenge on exit cap rate or DSCR
    topics = [c.topic for c in challenges]
    assert (
        DeliberationTopic.EXIT_VALUATION in topics or DeliberationTopic.LEVERAGE_AND_DEBT in topics
    )

    transcript = engine.conduct_deliberation(ctx)
    assert transcript.total_rounds >= 1
    assert transcript.consensus_score > 0.0
    assert transcript.final_verdict is not None
    assert len(transcript.rounds[0].challenges) == len(challenges)
    assert transcript.rounds[0].challenges[0].resolved is True


# --------------------------------------------------------------------------
# 2. Compliance & Rule Engine Subsystem Tests
# --------------------------------------------------------------------------


def test_default_institutional_rules():
    """Verify default rule set covers all institutional policy categories."""
    rules = get_default_institutional_rules()
    categories = {r.category for r in rules}
    assert RuleCategory.LEVERAGE in categories
    assert RuleCategory.DEBT_SERVICE in categories
    assert RuleCategory.RESERVE_ADEQUACY in categories
    assert RuleCategory.RETURN_HURDLE in categories


def test_rule_engine_evaluation_pass_and_breach(sample_deal: PropertyDeal):
    """Verify rule evaluations, error counting, and remediation guidance."""
    rule_engine = RuleEngine()
    ctx = DealWorkflowContext(deal=sample_deal)

    # Debt sizing that passes covenants
    ctx.debt_sizing = DebtSizingResult(
        loan_amount=2800000.0,
        equity_required=1480000.0,
        monthly_payment=17000.0,
        annual_debt_service=204000.0,
        ltv_ratio=0.70,
        dscr_year1=1.35,
        debt_yield_pct=0.09,
        binding_constraint="LTV",
    )

    report = rule_engine.evaluate(ctx)
    assert report.is_compliant is True
    assert report.error_count == 0
    assert report.compliance_score == 100.0

    # Introduce covenant breach: high LTV (0.85) and low DSCR (1.10)
    ctx.debt_sizing.ltv_ratio = 0.85
    ctx.debt_sizing.dscr_year1 = 1.10

    breach_report = rule_engine.evaluate(ctx)
    assert breach_report.is_compliant is False
    assert breach_report.error_count >= 1
    assert breach_report.compliance_score < 100.0

    # Verify remediation text is populated on failed rules
    failed_results = [r for r in breach_report.results if not r.passed]
    assert len(failed_results) > 0
    for fr in failed_results:
        assert fr.remediation is not None
        assert len(fr.remediation) > 0


def test_custom_rule_registration(sample_deal: PropertyDeal):
    """Verify dynamic addition and removal of custom institutional rules."""
    engine = RuleEngine()
    custom_rule = RuleDefinition(
        id="CUST-EXP-01",
        name="Maximum Property Tax Ratio",
        category=RuleCategory.OPERATIONAL_SAFETY,
        severity=RuleSeverity.WARNING,
        description="Property taxes must not exceed 2.0% of purchase price.",
        threshold=0.02,
        operator="<=",
        remediation="Appeal local tax assessment.",
    )

    engine.register_rule(
        custom_rule,
        extractor=lambda ctx: ctx.deal.expenses.property_taxes / ctx.deal.purchase_price,
    )

    ctx = DealWorkflowContext(deal=sample_deal)
    # Taxes = 50,000 / 4,000,000 = 0.0125 <= 0.02 (passes)
    rep1 = engine.evaluate(ctx)
    cust_res = next(r for r in rep1.results if r.rule_id == "CUST-EXP-01")
    assert cust_res.passed is True

    # Artificially raise taxes to trigger warning
    sample_deal.expenses.property_taxes = 120000.0  # 120k / 4M = 0.03 > 0.02
    rep2 = engine.evaluate(ctx)
    cust_res2 = next(r for r in rep2.results if r.rule_id == "CUST-EXP-01")
    assert cust_res2.passed is False

    # Remove rule
    assert engine.remove_rule("CUST-EXP-01") is True
    assert engine.remove_rule("CUST-EXP-01") is False


# --------------------------------------------------------------------------
# 3. Portfolio Management Subsystem Tests
# --------------------------------------------------------------------------


def test_portfolio_manager_deal_management():
    """Verify adding, retrieving, and removing deals from portfolio."""
    mgr = PortfolioManager(portfolio_id="test-fund", portfolio_name="Test Value-Add Fund")
    deals = get_benchmark_deals()
    assert len(deals) >= 3

    mgr.add_deal(deals[0])
    mgr.add_deal(deals[1])
    assert len(mgr.get_deals()) == 2

    assert mgr.remove_deal(deals[0].id) is True
    assert len(mgr.get_deals()) == 1
    assert mgr.remove_deal("non-existent-deal") is False


def test_portfolio_rollup_cash_flows_and_irr():
    """Verify multi-asset cash flow aggregation, portfolio IRR, and HHI."""
    mgr = PortfolioManager()
    for deal in get_benchmark_deals():
        mgr.add_deal(deal)

    rollup = mgr.generate_rollup()
    assert rollup.deal_count == 3
    assert rollup.total_units > 0
    assert rollup.total_purchase_price > 10000000.0
    assert rollup.total_equity_invested > 0.0
    assert rollup.total_debt_funded > 0.0

    # Portfolio returns
    assert rollup.portfolio_levered_irr > 0.05
    assert rollup.portfolio_equity_multiple > 1.2
    assert len(rollup.aggregate_annual_cash_flows) >= 6
    assert rollup.aggregate_annual_cash_flows[0] < 0  # Year 0 initial equity outflow

    # Asset allocations
    assert len(rollup.allocations) == 3
    total_weights = sum(a.weight_by_equity for a in rollup.allocations)
    assert pytest.approx(total_weights, 0.01) == 1.0


def test_portfolio_risk_profile_and_stress_testing():
    """Verify portfolio concentration HHI and macro stress testing."""
    mgr = PortfolioManager()
    for deal in get_benchmark_deals():
        mgr.add_deal(deal)

    risk = mgr.calculate_risk_profile()
    assert risk.hhi_concentration_index > 0.0
    assert risk.diversification_rating in ("High", "Moderate", "Concentrated")
    assert len(risk.stress_test_results) == 3

    for st in risk.stress_test_results:
        assert st.scenario_name is not None
        assert st.base_portfolio_irr > 0.0
        # Stressed IRR should be lower than base
        assert st.stressed_portfolio_irr <= st.base_portfolio_irr
        assert st.irr_drop_basis_points >= 0.0


# --------------------------------------------------------------------------
# 4. Reporting & Exporter Subsystem Tests
# --------------------------------------------------------------------------


def test_investment_memo_generation(sample_deal: PropertyDeal):
    """Verify Markdown Underwriting Memorandum rendering and completeness."""
    pipeline = DealPipeline(monte_carlo_iterations=100)
    result = pipeline.run(sample_deal)

    gen = InvestmentMemoGenerator()
    memo = gen.generate_memo(
        deal=sample_deal,
        result=result,
        compliance_report=result.compliance_report,
    )

    assert "# INVESTMENT COMMITTEE UNDERWRITING MEMORANDUM" in memo
    assert sample_deal.title in memo
    assert "## 1. Executive Summary & Investment Thesis" in memo
    assert "## 2. Sources & Uses of Capital" in memo
    assert "## 3. Financial Metrics & Returns Summary" in memo
    assert "## 4. Multi-Year Operating Pro-Forma Schedule" in memo
    assert "## 7. Stochastic Monte Carlo Risk Analysis" in memo
    assert "## 8. Institutional Credit Policy & Compliance Audit" in memo
    assert "## 11. Investment Committee Action & Sign-Off" in memo


def test_data_exporter_csv_and_json(sample_deal: PropertyDeal):
    """Verify CSV and JSON exporting functions."""
    pipeline = DealPipeline(monte_carlo_iterations=100)
    result = pipeline.run(sample_deal)

    exporter = DataExporter()

    # Cash flows CSV
    cf_csv = exporter.export_cashflows_csv(result)
    assert "Gross Potential Rent" in cf_csv
    assert "Net Cash Flow" in cf_csv
    assert len(cf_csv.strip().split("\n")) == sample_deal.hold_period_years + 1

    # Waterfall CSV
    wf_csv = exporter.export_waterfall_csv(result)
    if result.waterfall:
        assert "Total Distributable Cash" in wf_csv
        assert "GP Promote" in wf_csv

    # Sensitivity CSV
    sens_csv = exporter.export_sensitivity_csv(result)
    if result.sensitivity:
        assert "Rent Growth / Exit Cap" in sens_csv

    # JSON export
    raw_json = exporter.export_underwriting_json(result)
    parsed = json.loads(raw_json)
    assert parsed["deal_id"] == sample_deal.id
    assert parsed["committee_score"] == result.committee_score


# --------------------------------------------------------------------------
# 5. Storage Repository Enhancements Tests
# --------------------------------------------------------------------------


def test_deal_repository_query_filtering(tmp_path: Path):
    """Verify querying repository deals with combined filters."""
    repo = DealRepository(storage_dir=tmp_path)

    # Filter by property type
    mf_deals = repo.query_deals(property_type=PropertyType.MULTI_FAMILY)
    assert len(mf_deals) >= 1
    assert all(d.property_type == PropertyType.MULTI_FAMILY for d in mf_deals)

    # Filter by price range
    budget_deals = repo.query_deals(max_price=5000000.0)
    assert len(budget_deals) >= 1
    assert all(d.purchase_price <= 5000000.0 for d in budget_deals)

    # Filter by search text
    austin_deals = repo.query_deals(search_text="austin")
    assert len(austin_deals) == 1
    assert austin_deals[0].id == "austin-multifamily"


def test_deal_repository_revisions_and_diffing(tmp_path: Path, sample_deal: PropertyDeal):
    """Verify versioned snapshots, revision history, and revision diffing."""
    repo = DealRepository(storage_dir=tmp_path)
    repo.save_deal(sample_deal)

    # Create Revision 1
    rev1 = repo.create_revision(sample_deal, author="analyst_1", change_summary="Initial intake")
    assert rev1.revision_number == 1

    # Modify deal and create Revision 2
    modified_deal = sample_deal.model_copy(deep=True)
    modified_deal.purchase_price = 4500000.0  # was 4,000,000
    modified_deal.exit_cap_rate = 0.070  # was 0.065
    rev2 = repo.create_revision(
        modified_deal, author="senior_vp", change_summary="Higher purchase price & cap"
    )
    assert rev2.revision_number == 2

    # Verify history
    revs = repo.get_revisions(sample_deal.id)
    assert len(revs) == 2

    # Diff revisions
    diff = repo.diff_revisions(sample_deal.id, 1, 2)
    assert "purchase_price" in diff
    assert diff["purchase_price"]["rev_a"] == 4000000.0
    assert diff["purchase_price"]["rev_b"] == 4500000.0
    assert "exit_cap_rate" in diff

    # Revert to Revision 1
    restored = repo.revert_to_revision(sample_deal.id, 1)
    assert restored is not None
    assert restored.purchase_price == 4000000.0
    current = repo.get_deal(sample_deal.id)
    assert current is not None
    assert current.purchase_price == 4000000.0


def test_deal_repository_portfolio_persistence(tmp_path: Path):
    """Verify saving and listing portfolios in repository."""
    repo = DealRepository(storage_dir=tmp_path)
    repo.save_portfolio(
        portfolio_id="tx-fund",
        name="Texas Multi-Asset Growth Fund",
        deal_ids=["austin-multifamily", "dallas-industrial"],
    )

    port = repo.get_portfolio("tx-fund")
    assert port is not None
    assert port["name"] == "Texas Multi-Asset Growth Fund"
    assert len(port["deal_ids"]) == 2

    ports = repo.list_portfolios()
    assert len(ports) == 1
    assert ports[0]["id"] == "tx-fund"


# --------------------------------------------------------------------------
# 6. Pipeline Subsystem Integration Tests
# --------------------------------------------------------------------------


def test_pipeline_executes_deliberation_and_compliance(sample_deal: PropertyDeal):
    """Verify DealPipeline automatically executes deliberation and compliance audit."""
    pipeline = DealPipeline(monte_carlo_iterations=100)
    result = pipeline.run(sample_deal)

    # Deliberation transcript attached
    assert result.debate_transcript is not None
    assert result.debate_transcript.deal_id == sample_deal.id
    assert result.debate_transcript.total_rounds >= 1

    # Compliance report attached
    assert result.compliance_report is not None
    assert result.compliance_report.deal_id == sample_deal.id
    assert result.compliance_report.rules_checked >= 5


# --------------------------------------------------------------------------
# 7. CLI Subsystems Commands Tests
# --------------------------------------------------------------------------


def test_cli_audit_command():
    """Test CLI audit command output."""
    runner = CliRunner()
    res = runner.invoke(cli, ["audit", "--deal-id", "austin-multifamily"])
    assert res.exit_code == 0
    assert "Credit Policy Compliance Audit" in res.output
    assert "Policy Rule Breakdown" in res.output


def test_cli_portfolio_command():
    """Test CLI portfolio aggregation command."""
    runner = CliRunner()
    res = runner.invoke(cli, ["portfolio"])
    assert res.exit_code == 0
    assert "Portfolio Investment Summary" in res.output
    assert "Portfolio Asset Allocations" in res.output


def test_cli_memo_command(tmp_path: Path):
    """Test CLI memo generation command."""
    runner = CliRunner()
    memo_file = tmp_path / "test_memo.md"
    res = runner.invoke(cli, ["memo", "--deal-id", "austin-multifamily", "--out", str(memo_file)])
    assert res.exit_code == 0
    assert memo_file.exists()
    content = memo_file.read_text(encoding="utf-8")
    assert "INVESTMENT COMMITTEE UNDERWRITING MEMORANDUM" in content


def test_cli_export_command(tmp_path: Path):
    """Test CLI export command for CSV and JSON formats."""
    runner = CliRunner()

    # Cashflow CSV export
    cf_file = tmp_path / "cashflows.csv"
    res1 = runner.invoke(
        cli, ["export", "--deal-id", "austin-multifamily", "-f", "cashflow", "-o", str(cf_file)]
    )
    assert res1.exit_code == 0
    assert cf_file.exists()
    assert "Effective Gross Income" in cf_file.read_text(encoding="utf-8")

    # JSON export
    json_file = tmp_path / "result.json"
    res2 = runner.invoke(
        cli, ["export", "--deal-id", "austin-multifamily", "-f", "json", "-o", str(json_file)]
    )
    assert res2.exit_code == 0
    assert json_file.exists()
    parsed = json.loads(json_file.read_text(encoding="utf-8"))
    assert parsed["deal_id"] == "austin-multifamily"
