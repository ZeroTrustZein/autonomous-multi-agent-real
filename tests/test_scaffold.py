"""Comprehensive scaffolding test suite verifying project modules, models, agents, and pipeline."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import autonomous_multi_agent_real
from autonomous_multi_agent_real.agents.acquisition import AcquisitionAgent
from autonomous_multi_agent_real.agents.cashflow import CashFlowAgent
from autonomous_multi_agent_real.agents.committee import InvestmentCommitteeAgent
from autonomous_multi_agent_real.agents.debt import DebtAgent
from autonomous_multi_agent_real.agents.market import MarketCompsAgent
from autonomous_multi_agent_real.agents.risk import RiskMonteCarloAgent
from autonomous_multi_agent_real.cli.main import cli
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
from autonomous_multi_agent_real.engine.state import DealWorkflowContext
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.storage.repository import DealRepository
from autonomous_multi_agent_real.types import (
    AgentDecisionStatus,
    AgentRole,
    InvestmentDecision,
    PropertyDeal,
    PropertyType,
    UnitMixItem,
)


def test_package_metadata():
    """Verify package version and exposed symbols."""
    assert autonomous_multi_agent_real.__version__ == "0.1.0"
    assert hasattr(autonomous_multi_agent_real, "DealPipeline")
    assert hasattr(autonomous_multi_agent_real, "PropertyDeal")
    assert hasattr(autonomous_multi_agent_real, "DealRepository")


def test_property_deal_models(sample_deal: PropertyDeal):
    """Test PropertyDeal properties and calculations."""
    assert sample_deal.total_units == 20
    assert sample_deal.property_type == PropertyType.MULTI_FAMILY
    # 12 * 1400 + 8 * 1850 = 16800 + 14800 = 31600 monthly
    assert sample_deal.total_current_monthly_rent == 31600.0
    assert sample_deal.total_current_annual_rent == 31600.0 * 12.0
    # Basis: 4,000,000 + 200,000 + (4,000,000 * 0.02) = 4,280,000
    assert sample_deal.total_acquisition_basis == 4280000.0


def test_unit_mix_item():
    """Test unit mix helper methods."""
    item = UnitMixItem(
        unit_type="Studio",
        count=5,
        square_feet=500.0,
        current_rent=1000.0,
        market_rent=1200.0,
    )
    assert item.total_monthly_current_rent() == 5000.0
    assert item.total_monthly_market_rent() == 6000.0
    assert item.loss_to_lease() == 1000.0


def test_financial_mortgage_calculations():
    """Test mortgage payment formula and edge cases."""
    pmt = calculate_monthly_mortgage_payment(
        principal=3000000.0,
        annual_interest_rate=0.06,
        amortization_years=30,
    )
    # Expected payment on $3M at 6% 30yr is approx $17,986.52
    assert 17900.0 < pmt < 18100.0

    # 0 principal
    assert calculate_monthly_mortgage_payment(0.0, 0.06, 30) == 0.0
    # 0 interest rate
    assert calculate_monthly_mortgage_payment(120000.0, 0.0, 10) == 1000.0


def test_loan_amortization_schedule():
    """Test multi-year amortization schedule generation."""
    sched = calculate_loan_amortization_schedule(
        principal=1000000.0,
        annual_interest_rate=0.06,
        amortization_years=25,
        hold_period_years=5,
        interest_only_months=12,
    )
    assert len(sched) == 5
    # Year 1 has 12 months IO -> 0 principal paid, balance stays $1M
    assert sched[0][0] == 0.0
    assert sched[0][2] == 1000000.0
    # Year 2 amortizes -> balance decreases
    assert sched[1][0] > 0.0
    assert sched[1][2] < 1000000.0
    # Year 5 balance is strictly less than Year 2
    assert sched[4][2] < sched[1][2]


def test_irr_and_npv():
    """Test IRR and NPV calculations."""
    flows = [-100.0, 20.0, 20.0, 20.0, 20.0, 120.0]
    irr = calculate_irr(flows)
    assert pytest.approx(irr, abs=1e-3) == 0.20

    npv = calculate_npv(0.10, flows)
    assert npv > 0.0

    # Test edge case: no positive cash flows
    assert calculate_irr([-100.0, -50.0]) == 0.0


def test_ratios_and_metrics():
    """Test cap rate, debt yield, DSCR, and equity multiple."""
    assert calculate_dscr(150000.0, 100000.0) == 1.50
    assert calculate_dscr(100.0, 0.0) == 99.99
    assert calculate_debt_yield(80000.0, 1000000.0) == 0.08
    assert calculate_cap_rate(65000.0, 1000000.0) == 0.065
    assert calculate_equity_multiple(500000.0, 1000000.0) == 2.0
    assert calculate_exit_sale_proceeds(100000.0, 0.05, 0.02) == 1960000.0


def test_individual_swarm_agents(sample_deal: PropertyDeal):
    """Test execution and reporting of each individual agent in sequence."""
    ctx = DealWorkflowContext(deal=sample_deal)

    # 1. Acquisition Agent
    acq_agent = AcquisitionAgent()
    acq_rep = acq_agent.analyze(ctx)
    assert acq_rep.agent_role == AgentRole.ACQUISITION
    assert acq_rep.status in [AgentDecisionStatus.APPROVED, AgentDecisionStatus.CONDITIONAL]
    ctx.add_agent_report(acq_rep)

    # 2. Market Comps Agent
    market_agent = MarketCompsAgent()
    mkt_rep = market_agent.analyze(ctx)
    assert mkt_rep.agent_role == AgentRole.MARKET_COMPS
    assert "annual_loss_to_lease" in mkt_rep.key_metrics
    ctx.add_agent_report(mkt_rep)

    # 3. Debt Agent
    debt_agent = DebtAgent()
    debt_rep = debt_agent.analyze(ctx)
    assert debt_rep.agent_role == AgentRole.DEBT_FINANCING
    assert ctx.debt_sizing is not None
    assert ctx.debt_sizing.loan_amount > 0
    ctx.add_agent_report(debt_rep)

    # 4. Cash Flow Agent
    cf_agent = CashFlowAgent()
    cf_rep = cf_agent.analyze(ctx)
    assert cf_rep.agent_role == AgentRole.CASH_FLOW
    assert len(ctx.cash_flows) == sample_deal.hold_period_years
    assert ctx.deal_metrics is not None
    assert ctx.deal_metrics.levered_irr > 0
    ctx.add_agent_report(cf_rep)

    # 5. Risk Agent
    risk_agent = RiskMonteCarloAgent(iterations=100)
    risk_rep = risk_agent.analyze(ctx)
    assert risk_rep.agent_role == AgentRole.RISK_SIMULATION
    assert ctx.monte_carlo is not None
    assert ctx.monte_carlo.iterations == 100
    ctx.add_agent_report(risk_rep)

    # 6. Committee Agent
    comm_agent = InvestmentCommitteeAgent()
    comm_rep = comm_agent.analyze(ctx)
    assert comm_rep.agent_role == AgentRole.INVESTMENT_COMMITTEE
    assert "composite_deal_score" in comm_rep.key_metrics
    assert comm_rep.key_metrics["composite_deal_score"] > 0


def test_monte_carlo_engine(sample_deal: PropertyDeal):
    """Test standalone Monte Carlo simulation engine."""
    ctx = DealWorkflowContext(deal=sample_deal)
    DebtAgent().analyze(ctx)
    assert ctx.debt_sizing is not None

    engine = MonteCarloEngine(seed=42)
    result = engine.simulate(deal=sample_deal, debt_sizing=ctx.debt_sizing, iterations=250)

    assert result.iterations == 250
    assert -0.5 < result.mean_levered_irr < 1.0
    assert result.p10_irr <= result.p50_irr <= result.p90_irr
    assert 0.0 <= result.probability_negative_irr <= 1.0
    assert 0.0 <= result.probability_dscr_breach <= 1.0
    assert len(result.distribution_quantiles) >= 5


def test_full_pipeline_run(pipeline: DealPipeline, sample_deal: PropertyDeal):
    """Test complete synchronous and asynchronous pipeline run."""
    result = pipeline.run(sample_deal)

    assert result.deal_id == sample_deal.id
    assert result.decision in [
        InvestmentDecision.APPROVED,
        InvestmentDecision.CONDITIONAL,
        InvestmentDecision.REJECTED,
    ]
    assert 0.0 <= result.committee_score <= 100.0
    assert len(result.cash_flows) == sample_deal.hold_period_years
    assert len(result.agent_reports) == 6
    assert result.debt_sizing.loan_amount > 0.0
    assert len(result.investment_thesis) >= 3
    assert result.execution_time_seconds > 0.0


def test_pipeline_async_run(pipeline: DealPipeline, sample_deal: PropertyDeal):
    """Test asynchronous pipeline execution."""
    import asyncio

    result = asyncio.run(pipeline.run_async(sample_deal))
    assert result.deal_id == sample_deal.id
    assert result.committee_score > 0


def test_deal_repository(deal_repo: DealRepository):
    """Test DealRepository listing, fetching, and saving."""
    deals = deal_repo.list_deals()
    assert len(deals) >= 3

    deal_ids = [d.id for d in deals]
    assert "austin-multifamily" in deal_ids
    assert "dallas-industrial" in deal_ids
    assert "phoenix-mixed-use" in deal_ids

    austin = deal_repo.get_deal("austin-multifamily")
    assert austin is not None
    assert austin.total_units == 24


def test_cli_commands():
    """Test CLI commands execution via Click CliRunner."""
    runner = CliRunner()

    # 1. list
    res_list = runner.invoke(cli, ["list"])
    assert res_list.exit_code == 0
    assert "Austin" in res_list.output or "austin-multifamily" in res_list.output

    # 2. underwrite benchmark deal
    res_uw = runner.invoke(
        cli, ["underwrite", "--deal-id", "austin-multifamily", "--iterations", "100"]
    )
    assert res_uw.exit_code == 0
    assert "Investment Committee" in res_uw.output
    assert "Multi-Year Pro-Forma" in res_uw.output

    # 3. simulate
    res_sim = runner.invoke(
        cli, ["simulate", "--deal-id", "austin-multifamily", "--iterations", "100"]
    )
    assert res_sim.exit_code == 0
    assert "Monte Carlo Simulation Report" in res_sim.output

    # 4. quick
    res_quick = runner.invoke(
        cli,
        [
            "quick",
            "--price",
            "2500000",
            "--units",
            "12",
            "--sqft",
            "9600",
            "--rent",
            "1500",
            "--market-rent",
            "1750",
        ],
    )
    assert res_quick.exit_code == 0
    assert "Quick Underwriting Summary" in res_quick.output
