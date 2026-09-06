"""Comprehensive unit tests for core underwriting, waterfall, sensitivity, tax, and optimization engines."""

from __future__ import annotations

import pytest

from autonomous_multi_agent_real.engine.optimizer import DealOptimizer
from autonomous_multi_agent_real.engine.sensitivity import SensitivityEngine
from autonomous_multi_agent_real.engine.tax import TaxEngine
from autonomous_multi_agent_real.engine.waterfall import (
    WaterfallEngine,
    get_default_waterfall_structure,
)
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.types import (
    DebtSizingResult,
    PropertyDeal,
    WaterfallStructure,
    WaterfallTier,
)


@pytest.fixture
def sample_debt_sizing() -> DebtSizingResult:
    return DebtSizingResult(
        loan_amount=3000000.0,
        equity_required=1280000.0,
        monthly_payment=18962.03,
        annual_debt_service=227544.36,
        ltv_ratio=0.75,
        dscr_year1=1.42,
        debt_yield_pct=0.1077,
        binding_constraint="LTV",
    )


def test_waterfall_default_structure():
    """Verify default institutional waterfall parameters."""
    wf = get_default_waterfall_structure()
    assert wf.preferred_return_rate == 0.08
    assert wf.lp_equity_pct == 0.90
    assert wf.gp_equity_pct == 0.10
    assert len(wf.tiers) == 4
    assert wf.tiers[0].hurdle_irr == 0.08
    assert wf.tiers[1].gp_share == 0.20


def test_waterfall_zero_or_empty_cash_flows():
    """Verify edge cases for zero equity or empty cash flows."""
    engine = WaterfallEngine()
    res_zero = engine.calculate(0.0, [50000.0, 100000.0])
    assert res_zero.lp_equity_invested == 0.0
    assert res_zero.annual_distributions == []

    res_empty = engine.calculate(1000000.0, [])
    assert res_empty.lp_total_distributions == 0.0


def test_waterfall_distribution_mechanics():
    """Verify cash flow splits, return of capital, preferred returns, and sponsor promote."""
    engine = WaterfallEngine()
    total_equity = 1000000.0  # $900k LP, $100k GP
    # 5-year cash flow profile with terminal exit
    flows = [70000.0, 75000.0, 80000.0, 85000.0, 1500000.0]

    res = engine.calculate(total_equity=total_equity, annual_cash_flows=flows)

    assert res.lp_equity_invested == 900000.0
    assert res.gp_equity_invested == 100000.0
    assert len(res.annual_distributions) == 5

    # Total distributions must equal total cash flows
    total_in = sum(flows)
    total_out = res.lp_total_distributions + res.gp_total_distributions
    assert pytest.approx(total_out, abs=1.0) == total_in

    # Sponsor promote should be positive given strong exit
    assert res.gp_total_promote > 0.0
    # GP IRR should exceed LP IRR due to promote
    assert res.gp_irr >= res.lp_irr
    assert res.gp_equity_multiple >= res.lp_equity_multiple
    assert res.lp_equity_multiple > 1.0


def test_waterfall_custom_structure():
    """Verify custom promote tier execution."""
    custom = WaterfallStructure(
        preferred_return_rate=0.06,
        lp_equity_pct=0.80,
        gp_equity_pct=0.20,
        tiers=[
            WaterfallTier(name="Tier 1", hurdle_irr=0.06, lp_share=0.80, gp_share=0.20),
            WaterfallTier(name="Tier 2", hurdle_irr=999.0, lp_share=0.60, gp_share=0.40),
        ],
    )
    engine = WaterfallEngine(structure=custom)
    res = engine.calculate(500000.0, [40000.0, 45000.0, 800000.0])

    assert res.lp_equity_invested == 400000.0
    assert res.gp_equity_invested == 100000.0
    assert res.gp_total_promote > 0.0


def test_sensitivity_matrix_generation(
    sample_deal: PropertyDeal, sample_debt_sizing: DebtSizingResult
):
    """Test 2D sensitivity grid varying exit cap rates and rent growth rates."""
    engine = SensitivityEngine()
    matrix = engine.generate_cap_vs_rent_growth_matrix(
        deal=sample_deal,
        debt_sizing=sample_debt_sizing,
        exit_caps=[0.055, 0.065, 0.075],
        rent_growths=[0.02, 0.03, 0.04],
    )

    assert matrix.row_parameter == "exit_cap_rate"
    assert matrix.col_parameter == "annual_rent_growth"
    assert len(matrix.irr_matrix) == 3
    assert len(matrix.irr_matrix[0]) == 3

    # Monotonicity checks:
    # 1. Lower cap rate (row 0 vs row 2) gives higher exit price -> higher IRR
    assert matrix.irr_matrix[0][1] > matrix.irr_matrix[2][1]
    # 2. Higher rent growth (col 2 vs col 0) gives higher NOI -> higher IRR
    assert matrix.irr_matrix[1][2] > matrix.irr_matrix[1][0]


def test_breakeven_metrics_calculation(
    sample_deal: PropertyDeal, sample_debt_sizing: DebtSizingResult
):
    """Test occupancy and rent breakeven points for debt service."""
    engine = SensitivityEngine()
    be = engine.calculate_breakeven_metrics(deal=sample_deal, debt_sizing=sample_debt_sizing)

    assert 0.40 <= be.breakeven_occupancy_pct <= 0.90
    assert be.margin_of_safety_occupancy_pct > 0.0
    assert (
        be.breakeven_monthly_rent_per_unit
        < sample_deal.total_current_monthly_rent / sample_deal.total_units
    )
    assert be.margin_of_safety_rent_pct > 0.0
    assert be.breakeven_noi_for_debt_service == sample_debt_sizing.annual_debt_service


def test_scenario_comparison(sample_deal: PropertyDeal, sample_debt_sizing: DebtSizingResult):
    """Verify Base, Bull, and Bear case return ordering."""
    engine = SensitivityEngine()
    scenarios = engine.generate_scenario_comparison(
        deal=sample_deal, debt_sizing=sample_debt_sizing
    )

    assert "base_case" in scenarios
    assert "bull_case" in scenarios
    assert "bear_case" in scenarios

    bull_irr = scenarios["bull_case"].levered_irr
    base_irr = scenarios["base_case"].levered_irr
    bear_irr = scenarios["bear_case"].levered_irr

    assert bull_irr >= base_irr >= bear_irr


def test_tax_engine_straight_line_depreciation(
    sample_deal: PropertyDeal, sample_debt_sizing: DebtSizingResult
):
    """Test MACRS 27.5-year straight line depreciation for multifamily."""
    engine = TaxEngine(land_value_pct=0.20, enable_cost_segregation=False)
    dep_sched = engine.compute_depreciation_schedule(sample_deal, hold_years=5)

    assert len(dep_sched) == 5
    # Total depreciable basis = 4,280,000 * 0.80 = 3,424,000
    # Annual = 3,424,000 / 27.5 = 124,509.09
    expected_dep = round(sample_deal.total_acquisition_basis * 0.80 / 27.5, 2)
    assert pytest.approx(dep_sched[0], abs=2.0) == expected_dep
    assert dep_sched[0] == dep_sched[1] == dep_sched[4]


def test_tax_engine_cost_segregation(sample_deal: PropertyDeal):
    """Test cost segregation accelerated Year 1 bonus depreciation."""
    engine = TaxEngine(
        land_value_pct=0.20,
        enable_cost_segregation=True,
        cost_seg_5yr_pct=0.15,
        cost_seg_15yr_pct=0.10,
        year1_bonus_depreciation_pct=0.80,
    )
    dep_sched = engine.compute_depreciation_schedule(sample_deal, hold_years=5)

    # Year 1 should have massive bonus depreciation
    assert dep_sched[0] > dep_sched[1] * 2.5
    assert dep_sched[1] > 0.0


def test_tax_engine_full_analysis(sample_deal: PropertyDeal, sample_debt_sizing: DebtSizingResult):
    """Test full pre-tax vs after-tax analysis and terminal exit taxes."""
    engine = TaxEngine()
    nois = [300000.0, 310000.0, 320000.0, 330000.0, 340000.0]
    exit_gross = 5200000.0

    res = engine.analyze(
        deal=sample_deal,
        debt_sizing=sample_debt_sizing,
        annual_nois=nois,
        exit_gross_proceeds=exit_gross,
    )

    assert len(res.annual_schedule) == 5
    assert res.total_depreciation_claimed > 0.0
    assert res.depreciation_recapture_tax > 0.0
    assert res.total_exit_taxes > 0.0
    # After-tax IRR is typically lower than pre-tax IRR due to taxes
    assert res.after_tax_irr <= res.pre_tax_irr
    assert res.after_tax_equity_multiple <= res.pre_tax_equity_multiple


def test_deal_optimizer_price_solver(sample_deal: PropertyDeal):
    """Test reverse-solving maximum offer price for a 15% levered IRR hurdle."""
    optimizer = DealOptimizer()
    target_irr = 0.15
    res = optimizer.solve_max_offer_price(
        deal=sample_deal,
        target_levered_irr=target_irr,
        target_min_dscr=1.25,
        target_min_debt_yield=0.08,
    )

    assert res.target_hurdle_irr == target_irr
    assert res.max_supportable_purchase_price > 100000.0
    assert res.implied_loan_amount > 0.0
    assert res.implied_equity_required > 0.0

    # At the solved max price, check that the modeled IRR is within 50 bps of target
    irr_at_solved, _ = optimizer._evaluate_irr_at_price(
        sample_deal, res.max_supportable_purchase_price, 1.25, 0.08
    )
    assert abs(irr_at_solved - target_irr) < 0.015


def test_deal_optimizer_required_rent(sample_deal: PropertyDeal):
    """Test solver for minimum market rent required to meet hurdle IRR."""
    optimizer = DealOptimizer()
    req_rent = optimizer.solve_required_market_rent(
        deal=sample_deal,
        target_levered_irr=0.18,
    )
    assert req_rent > 0.0


def test_monte_carlo_var_cvar_and_variance_attribution(
    sample_deal: PropertyDeal, sample_debt_sizing: DebtSizingResult
):
    """Test enhanced Monte Carlo engine VaR/CVaR and variance attribution metrics."""
    from autonomous_multi_agent_real.engine.monte_carlo import MonteCarloEngine

    engine = MonteCarloEngine(seed=42, enable_correlated_shocks=True)
    res = engine.simulate(sample_deal, sample_debt_sizing, iterations=200)

    assert res.var_95_irr is not None
    assert res.cvar_95_irr is not None
    assert res.var_99_irr is not None
    assert res.cvar_99_irr is not None

    # Expected shortfall (CVaR) is worse than or equal to VaR
    assert res.cvar_95_irr <= res.var_95_irr
    assert res.cvar_99_irr <= res.var_99_irr

    # Variance attribution
    assert "rent_growth_impact" in res.variance_attribution
    assert "exit_cap_rate_impact" in res.variance_attribution
    # Exit cap rate has negative correlation with IRR (higher cap rate = lower exit price)
    assert res.variance_attribution["exit_cap_rate_impact"] < 0.0


def test_pipeline_integration_with_new_core_engines(sample_deal: PropertyDeal):
    """Verify that DealPipeline executes and populates all core engines in the output dossier."""
    pipeline = DealPipeline(monte_carlo_iterations=100, random_seed=42)
    result = pipeline.run(sample_deal)

    assert result.waterfall is not None
    assert result.waterfall.lp_equity_invested > 0.0
    assert result.waterfall.lp_equity_multiple > 0.0

    assert result.sensitivity is not None
    assert len(result.sensitivity.irr_matrix) > 0

    assert result.breakeven is not None
    assert result.breakeven.breakeven_occupancy_pct > 0.0

    assert result.tax_analysis is not None
    assert result.tax_analysis.total_depreciation_claimed > 0.0

    assert result.pricing_optimization is not None
    assert result.pricing_optimization.max_supportable_purchase_price > 0.0
