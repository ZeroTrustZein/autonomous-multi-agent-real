"""Pytest test fixtures and sample data for autonomous-multi-agent-real."""

from __future__ import annotations

import pytest

from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.storage.repository import DealRepository
from autonomous_multi_agent_real.types import (
    FinancingTerms,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnitMixItem,
)


@pytest.fixture
def sample_deal() -> PropertyDeal:
    """Standard 20-unit multifamily value-add acquisition fixture."""
    return PropertyDeal(
        id="test-multifamily-20",
        title="Oakwood Court 20-Unit Apartments",
        address="1200 Oakwood Lane, Austin, TX 78701",
        property_type=PropertyType.MULTI_FAMILY,
        gross_square_feet=18000.0,
        unit_mix=[
            UnitMixItem(
                unit_type="1BR/1BA",
                count=12,
                square_feet=800.0,
                current_rent=1400.0,
                market_rent=1650.0,
            ),
            UnitMixItem(
                unit_type="2BR/2BA",
                count=8,
                square_feet=1050.0,
                current_rent=1850.0,
                market_rent=2150.0,
            ),
        ],
        purchase_price=4000000.0,
        rehab_budget=200000.0,
        current_occupancy_pct=0.95,
        market_occupancy_pct=0.95,
        annual_rent_growth_pct=0.03,
        annual_expense_growth_pct=0.025,
        hold_period_years=5,
        exit_cap_rate=0.065,
        selling_costs_pct=0.02,
        expenses=OperatingExpenses(
            property_taxes=50000.0,
            insurance=15000.0,
            repairs_and_maintenance=18000.0,
            property_management_pct=0.07,
            utilities=10000.0,
            admin_and_legal=6000.0,
            replacement_reserves_per_unit=250.0,
            other_expenses=2000.0,
        ),
        financing=FinancingTerms(
            purchase_price=4000000.0,
            down_payment_pct=0.25,
            interest_rate=0.065,
            amortization_years=30,
            loan_term_years=10,
            interest_only_months=12,
            closing_costs_pct=0.02,
        ),
    )


@pytest.fixture
def pipeline() -> DealPipeline:
    """Instantiated DealPipeline with 200 Monte Carlo iterations for fast tests."""
    return DealPipeline(monte_carlo_iterations=200, random_seed=123)


@pytest.fixture
def deal_repo() -> DealRepository:
    """Deal repository instance populated with benchmarks."""
    return DealRepository()
