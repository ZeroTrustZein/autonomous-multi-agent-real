"""End-to-end integration and lifecycle pipeline tests for autonomous-multi-agent-real."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.portfolio.engine import PortfolioManager
from autonomous_multi_agent_real.portfolio.models import PortfolioStressScenario
from autonomous_multi_agent_real.reporting.exporter import DataExporter
from autonomous_multi_agent_real.storage.repository import DealRepository, get_benchmark_deals
from autonomous_multi_agent_real.types import (
    InvestmentDecision,
    UnderwritingResult,
)


def test_full_deal_underwriting_lifecycle():
    """Verify complete end-to-end multi-agent deal underwriting lifecycle."""
    benchmarks = get_benchmark_deals()
    assert len(benchmarks) >= 3

    deal = benchmarks[0]  # Austin Multifamily
    pipeline = DealPipeline(monte_carlo_iterations=150)
    result = pipeline.run(deal)

    # 1. Structural output completeness
    assert isinstance(result, UnderwritingResult)
    assert result.deal_id == deal.id
    assert result.deal_title == deal.title
    assert result.decision in (InvestmentDecision.APPROVED, InvestmentDecision.CONDITIONAL)
    assert 0.0 <= result.committee_score <= 100.0

    # 2. Agent reports
    assert len(result.agent_reports) >= 5
    for role_name in ("acquisition", "market_comps", "debt_financing", "cash_flow", "risk_simulation"):
        assert role_name in result.agent_reports
        rep = result.agent_reports[role_name]
        assert rep.confidence_score > 0.5
        assert len(rep.summary) > 0

    # 3. Cash flows and metrics
    assert len(result.cash_flows) == deal.hold_period_years
    for cf in result.cash_flows:
        assert cf.effective_gross_income > 0.0
        assert cf.net_operating_income > 0.0
        assert cf.debt_service > 0.0

    assert result.deal_metrics.levered_irr > 0.05
    assert result.deal_metrics.equity_multiple > 1.0

    # 4. Monte Carlo
    mc = result.monte_carlo
    assert mc.iterations == 150
    assert mc.p10_irr <= mc.p50_irr <= mc.p90_irr
    assert mc.var_95_irr is not None

    # 5. Waterfall
    wf = result.waterfall
    assert wf is not None
    assert wf.lp_irr > 0.0
    assert wf.lp_equity_multiple > 1.0
    assert len(wf.annual_distributions) == deal.hold_period_years

    # 6. Sensitivity & Breakeven
    sens = result.sensitivity
    assert sens is not None
    assert len(sens.irr_matrix) > 0

    be = result.breakeven
    assert be is not None
    assert be.breakeven_occupancy_pct > 0.0

    # 7. Tax Analysis
    tax = result.tax_analysis
    assert tax is not None
    assert tax.after_tax_irr > 0.0
    assert len(tax.annual_schedule) == deal.hold_period_years

    # 8. Deal Optimizer
    opt = result.pricing_optimization
    assert opt is not None
    assert opt.max_supportable_purchase_price > 0.0

    # 9. Compliance & Deliberation
    assert result.compliance_report is not None
    assert result.debate_transcript is not None
    assert result.debate_transcript.total_rounds >= 1


def test_async_deal_pipeline_execution():
    """Verify asynchronous pipeline execution and parity with sync run."""
    import asyncio

    deal = get_benchmark_deals()[1]  # Dallas Industrial
    pipeline = DealPipeline(monte_carlo_iterations=100)
    result = asyncio.run(pipeline.run_async(deal))

    assert result.deal_id == deal.id
    assert result.decision in (InvestmentDecision.APPROVED, InvestmentDecision.CONDITIONAL)
    assert len(result.cash_flows) == deal.hold_period_years
    assert result.waterfall is not None
    assert result.tax_analysis is not None


def test_multi_asset_portfolio_consolidation_and_stress():
    """Verify multi-asset portfolio rollup, cash flow aggregation, and stress testing."""
    benchmarks = get_benchmark_deals()
    pipeline = DealPipeline(monte_carlo_iterations=100)

    pm = PortfolioManager(
        portfolio_id="growth-fund-1",
        portfolio_name="Sunbelt Growth Fund I",
    )

    results = []
    for deal in benchmarks[:3]:
        res = pipeline.run(deal)
        results.append(res)
        pm.add_deal(deal, result=res)

    # Rollup generation
    rollup = pm.generate_rollup()
    assert rollup.deal_count == 3
    assert rollup.total_purchase_price > 10_000_000.0
    assert rollup.total_equity_invested > 3_000_000.0
    assert rollup.portfolio_levered_irr > 0.08
    assert rollup.portfolio_equity_multiple > 1.2
    assert len(rollup.allocations) == 3
    assert len(rollup.aggregate_annual_cash_flows) > 0

    # Test deal removal and re-addition
    deal_to_remove = benchmarks[0].id
    assert pm.remove_deal(deal_to_remove) is True
    assert pm.remove_deal("non-existent-deal") is False
    assert len(pm.get_deals()) == 2

    # Re-add deal
    pm.add_deal(benchmarks[0], result=results[0])
    assert len(pm.get_deals()) == 3

    # Stress testing across scenarios
    scenario_mild = PortfolioStressScenario(
        name="Mild Recession",
        occupancy_delta=-0.05,
        rent_growth_delta=-0.02,
        exit_cap_rate_delta=0.005,
    )
    risk_profile = pm.calculate_risk_profile(scenarios=[scenario_mild])
    assert len(risk_profile.stress_test_results) == 1
    stress_res = risk_profile.stress_test_results[0]
    assert stress_res.scenario_name == "Mild Recession"
    assert stress_res.stressed_portfolio_irr <= stress_res.base_portfolio_irr
    assert stress_res.irr_drop_basis_points >= 0.0

    # Data export for portfolio
    exporter = DataExporter()
    port_csv = exporter.export_portfolio_csv(rollup)
    assert "Deal ID,Deal Title,Property Type,Purchase Price" in port_csv
    for d in benchmarks[:3]:
        assert d.id in port_csv


def test_deal_repository_full_lifecycle(tmp_path: Path):
    """Verify repository deal creation, revision history, diffing, reverting, and persistence."""
    repo = DealRepository(storage_dir=tmp_path)
    initial_deals = repo.list_deals()
    assert len(initial_deals) >= 3

    # 1. Create and save a custom deal
    custom_deal = initial_deals[0].model_copy(deep=True)
    custom_deal.id = "austin-multifamily-revised"
    custom_deal.title = "Austin Revised Deal"
    custom_deal.purchase_price = 5_200_000.0
    repo.save_deal(custom_deal)

    assert repo.get_deal("austin-multifamily-revised") is not None

    # 2. Create versioned revisions
    rev1 = repo.create_revision(
        custom_deal,
        author="lead_analyst",
        change_summary="Initial model snapshot",
    )
    assert rev1.revision_number == 1
    assert rev1.deal_id == "austin-multifamily-revised"

    # Modify deal assumptions and create revision 2
    custom_deal.purchase_price = 5_000_000.0
    custom_deal.rehab_budget = 450_000.0
    rev2 = repo.create_revision(
        custom_deal,
        author="senior_partner",
        change_summary="Negotiated purchase price discount",
    )
    assert rev2.revision_number == 2

    # 3. List and inspect revisions
    history = repo.get_revisions("austin-multifamily-revised")
    assert len(history) == 2
    assert history[0].author == "lead_analyst"
    assert history[1].author == "senior_partner"

    # 4. Diff revisions
    diffs = repo.diff_revisions("austin-multifamily-revised", 1, 2)
    assert "purchase_price" in diffs
    assert diffs["purchase_price"]["rev_a"] == 5_200_000.0
    assert diffs["purchase_price"]["rev_b"] == 5_000_000.0

    # 5. Revert to revision 1
    reverted = repo.revert_to_revision("austin-multifamily-revised", 1)
    assert reverted is not None
    assert reverted.purchase_price == 5_200_000.0

    # 6. Delete deal
    assert repo.delete_deal("austin-multifamily-revised") is True
    assert repo.get_deal("austin-multifamily-revised") is None

    # 7. Portfolio persistence
    repo.save_portfolio(
        portfolio_id="core-fund-1",
        name="Core Real Estate Fund I",
        deal_ids=["austin-multifamily", "dallas-industrial"],
    )
    saved_port = repo.get_portfolio("core-fund-1")
    assert saved_port is not None
    assert saved_port["name"] == "Core Real Estate Fund I"
    assert len(repo.list_portfolios()) >= 1


def test_package_direct_cli_execution():
    """Verify python -m autonomous_multi_agent_real --help executes without error."""
    result = subprocess.run(
        [sys.executable, "-m", "autonomous_multi_agent_real", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Autonomous Multi-Agent Real Estate Underwriting" in result.stdout
    assert "Commands:" in result.stdout
