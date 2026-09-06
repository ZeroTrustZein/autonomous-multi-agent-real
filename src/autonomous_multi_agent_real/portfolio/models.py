"""Domain models for real estate investment portfolio aggregation and stress testing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


class PortfolioDealAllocation(BaseModel):
    """Allocation parameters and summary metrics for an asset in the portfolio."""

    model_config = ConfigDict(extra="ignore")

    deal_id: str
    deal_title: str
    property_type: str
    purchase_price: float
    equity_allocated: float
    loan_amount: float
    levered_irr: float
    equity_multiple: float
    weight_by_equity: float


class PortfolioRollup(BaseModel):
    """Aggregated financial and operational performance dossier across all portfolio assets."""

    model_config = ConfigDict(extra="ignore")

    portfolio_id: str
    portfolio_name: str
    deal_count: int
    total_units: int
    total_gross_square_feet: float
    total_purchase_price: float
    total_equity_invested: float
    total_debt_funded: float
    weighted_ltv: float
    weighted_dscr: float
    weighted_exit_cap: float
    portfolio_levered_irr: float
    portfolio_unlevered_irr: float
    portfolio_equity_multiple: float
    portfolio_npv: float
    aggregate_annual_cash_flows: List[float] = Field(default_factory=list)
    asset_type_breakdown: Dict[str, float] = Field(default_factory=dict)
    allocations: List[PortfolioDealAllocation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioStressScenario(BaseModel):
    """Macro-economic stress shocks applied jointly across all portfolio assets."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="e.g. Rate Spike, Recession, Stagflation")
    description: str = ""
    rent_growth_delta: float = 0.0  # e.g. -0.015 for -150 bps rent growth
    occupancy_delta: float = 0.0  # e.g. -0.05 for -500 bps occupancy
    interest_rate_delta: float = 0.0  # e.g. +0.015 for +150 bps interest rate
    exit_cap_rate_delta: float = 0.0  # e.g. +0.0075 for +75 bps exit cap expansion


class PortfolioStressResult(BaseModel):
    """Stress testing performance impact across portfolio."""

    model_config = ConfigDict(extra="ignore")

    scenario_name: str
    base_portfolio_irr: float
    stressed_portfolio_irr: float
    irr_drop_basis_points: float
    stressed_min_dscr: float
    dscr_breach_deals: List[str] = Field(default_factory=list)
    capital_loss_deals: List[str] = Field(default_factory=list)


class PortfolioRiskProfile(BaseModel):
    """Cross-asset concentration, diversification, and downside risk metrics."""

    model_config = ConfigDict(extra="ignore")

    portfolio_id: str
    hhi_concentration_index: float = Field(
        ..., description="Herfindahl-Hirschman Index across asset types (0 to 10,000)"
    )
    diversification_rating: str = Field(..., description="'High', 'Moderate', or 'Concentrated'")
    top_asset_type_concentration_pct: float
    stress_test_results: List[PortfolioStressResult] = Field(default_factory=list)
