"""Domain models and type definitions for autonomous multi-agent real estate underwriting."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class PropertyType(str, Enum):
    """Real estate asset classification."""

    SINGLE_FAMILY = "single_family"
    MULTI_FAMILY = "multi_family"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    MIXED_USE = "mixed_use"


class AgentRole(str, Enum):
    """Role assigned to specialized underwriting agents."""

    ACQUISITION = "acquisition"
    MARKET_COMPS = "market_comps"
    DEBT_FINANCING = "debt_financing"
    CASH_FLOW = "cash_flow"
    RISK_SIMULATION = "risk_simulation"
    INVESTMENT_COMMITTEE = "investment_committee"


class AgentDecisionStatus(str, Enum):
    """Individual agent assessment verdict."""

    APPROVED = "approved"
    CONDITIONAL = "conditional"
    FLAGGED = "flagged"
    REJECTED = "rejected"


class InvestmentDecision(str, Enum):
    """Final investment committee consensus."""

    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"


class WorkflowStage(str, Enum):
    """Execution stages of deal underwriting pipeline."""

    INTAKE = "intake"
    MARKET_ANALYSIS = "market_analysis"
    DEBT_SIZING = "debt_sizing"
    CASH_FLOW_SIMULATION = "cash_flow_simulation"
    RISK_MODELING = "risk_modeling"
    COMMITTEE_SYNTHESIS = "committee_synthesis"
    COMPLETED = "completed"
    FAILED = "failed"


class UnitMixItem(BaseModel):
    """Unit specification in a multifamily or commercial property."""

    model_config = ConfigDict(extra="ignore")

    unit_type: str = Field(..., description="e.g. 1BR/1BA, 2BR/2BA, Retail-A")
    count: int = Field(..., ge=1, description="Number of units of this layout")
    square_feet: float = Field(..., gt=0.0, description="Average square footage per unit")
    current_rent: float = Field(..., ge=0.0, description="In-place monthly rent per unit")
    market_rent: float = Field(..., ge=0.0, description="Projected market monthly rent")

    def total_monthly_current_rent(self) -> float:
        return self.count * self.current_rent

    def total_monthly_market_rent(self) -> float:
        return self.count * self.market_rent

    def loss_to_lease(self) -> float:
        """Difference between market rent and in-place rent."""
        return max(0.0, self.total_monthly_market_rent() - self.total_monthly_current_rent())


class OperatingExpenses(BaseModel):
    """Operating expense itemization for property underwriting."""

    model_config = ConfigDict(extra="ignore")

    property_taxes: float = Field(..., ge=0.0, description="Annual municipal property taxes")
    insurance: float = Field(..., ge=0.0, description="Annual property & liability insurance")
    repairs_and_maintenance: float = Field(
        ..., ge=0.0, description="Annual repairs & maintenance budget"
    )
    property_management_pct: float = Field(
        0.08, ge=0.0, le=0.30, description="Management fee as % of EGI"
    )
    utilities: float = Field(0.0, ge=0.0, description="Annual landlord-paid utilities")
    admin_and_legal: float = Field(
        0.0, ge=0.0, description="Annual administrative, legal & accounting"
    )
    replacement_reserves_per_unit: float = Field(
        250.0, ge=0.0, description="Annual replacement reserve per unit"
    )
    other_expenses: float = Field(0.0, ge=0.0, description="Miscellaneous annual operating costs")

    def fixed_annual_expenses(self, unit_count: int) -> float:
        """Operating expenses excluding variable property management fee."""
        reserves = self.replacement_reserves_per_unit * unit_count
        return (
            self.property_taxes
            + self.insurance
            + self.repairs_and_maintenance
            + self.utilities
            + self.admin_and_legal
            + reserves
            + self.other_expenses
        )


class FinancingTerms(BaseModel):
    """Capital markets financing assumptions for property acquisition."""

    model_config = ConfigDict(extra="ignore")

    purchase_price: float = Field(..., gt=0.0, description="Agreed purchase price")
    down_payment_pct: float = Field(
        0.25, ge=0.05, le=1.0, description="Equity down payment fraction"
    )
    interest_rate: float = Field(
        0.065, ge=0.01, le=0.25, description="Annual mortgage interest rate"
    )
    amortization_years: int = Field(30, ge=5, le=40, description="Amortization period in years")
    loan_term_years: int = Field(10, ge=1, le=30, description="Loan maturity / balloon period")
    interest_only_months: int = Field(
        0, ge=0, le=120, description="Months of initial interest-only payments"
    )
    closing_costs_pct: float = Field(
        0.02, ge=0.0, le=0.10, description="Acquisition closing & financing fee %"
    )


class PropertyDeal(BaseModel):
    """Complete representation of a real estate underwriting opportunity."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique identifier for the deal")
    title: str = Field(..., description="Property deal marketing name")
    address: str = Field(..., description="Street address, city, state, zip")
    property_type: PropertyType = Field(PropertyType.MULTI_FAMILY)
    gross_square_feet: float = Field(..., gt=0.0)
    unit_mix: List[UnitMixItem] = Field(..., min_length=1)
    purchase_price: float = Field(..., gt=0.0)
    rehab_budget: float = Field(0.0, ge=0.0, description="Immediate upfront capital improvements")
    current_occupancy_pct: float = Field(0.95, ge=0.10, le=1.0)
    market_occupancy_pct: float = Field(0.95, ge=0.10, le=1.0)
    annual_rent_growth_pct: float = Field(0.03, ge=-0.10, le=0.20)
    annual_expense_growth_pct: float = Field(0.025, ge=-0.05, le=0.15)
    hold_period_years: int = Field(5, ge=1, le=20)
    exit_cap_rate: float = Field(0.065, ge=0.02, le=0.20)
    selling_costs_pct: float = Field(0.02, ge=0.0, le=0.10)
    expenses: OperatingExpenses
    financing: FinancingTerms

    @property
    def total_units(self) -> int:
        return sum(u.count for u in self.unit_mix)

    @property
    def total_current_monthly_rent(self) -> float:
        return sum(u.total_monthly_current_rent() for u in self.unit_mix)

    @property
    def total_market_monthly_rent(self) -> float:
        return sum(u.total_monthly_market_rent() for u in self.unit_mix)

    @property
    def total_current_annual_rent(self) -> float:
        return self.total_current_monthly_rent * 12.0

    @property
    def total_market_annual_rent(self) -> float:
        return self.total_market_monthly_rent * 12.0

    @property
    def total_acquisition_basis(self) -> float:
        """Purchase price + upfront rehab budget + transaction closing costs."""
        closing_costs = self.purchase_price * self.financing.closing_costs_pct
        return self.purchase_price + self.rehab_budget + closing_costs


class DebtSizingResult(BaseModel):
    """Detailed sizing and underwriting results for senior debt."""

    model_config = ConfigDict(extra="ignore")

    loan_amount: float
    equity_required: float
    monthly_payment: float
    annual_debt_service: float
    ltv_ratio: float
    dscr_year1: float
    debt_yield_pct: float
    binding_constraint: str


class AnnualCashFlow(BaseModel):
    """Pro-forma financial schedule for a single operating year."""

    model_config = ConfigDict(extra="ignore")

    year: int
    gross_potential_rent: float
    vacancy_loss: float
    effective_gross_income: float
    operating_expenses: float
    net_operating_income: float
    capital_expenditures: float
    debt_service: float
    before_tax_cash_flow: float
    exit_sale_proceeds: float = 0.0
    net_cash_flow: float
    ending_loan_balance: float
    dscr: float


class DealMetrics(BaseModel):
    """Key return and leverage risk performance indicators."""

    model_config = ConfigDict(extra="ignore")

    unlevered_irr: float
    levered_irr: float
    equity_multiple: float
    net_present_value: float
    average_cash_on_cash: float
    entry_cap_rate: float
    exit_cap_rate: float
    min_dscr: float
    average_dscr: float


class AgentAnalysisReport(BaseModel):
    """Specialized report produced by an individual swarm agent."""

    model_config = ConfigDict(extra="ignore")

    agent_role: AgentRole
    agent_name: str
    status: AgentDecisionStatus
    summary: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    key_metrics: Dict[str, Any] = Field(default_factory=dict)
    risk_flags: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MonteCarloSimulationResult(BaseModel):
    """Outputs from multi-parameter stochastic cash flow simulation."""

    model_config = ConfigDict(extra="ignore")

    iterations: int
    mean_levered_irr: float
    std_levered_irr: float
    p10_irr: float
    p50_irr: float
    p90_irr: float
    probability_negative_irr: float
    probability_dscr_breach: float
    mean_equity_multiple: float
    p10_equity_multiple: float
    p90_equity_multiple: float
    distribution_quantiles: Dict[str, float] = Field(default_factory=dict)


class UnderwritingResult(BaseModel):
    """Complete consolidated deal underwriting assessment dossier."""

    model_config = ConfigDict(extra="ignore")

    deal_id: str
    deal_title: str
    decision: InvestmentDecision
    committee_score: float = Field(..., ge=0.0, le=100.0)
    deal_metrics: DealMetrics
    debt_sizing: DebtSizingResult
    cash_flows: List[AnnualCashFlow]
    monte_carlo: MonteCarloSimulationResult
    agent_reports: Dict[str, AgentAnalysisReport]
    executive_summary: str
    investment_thesis: List[str]
    key_risks_and_mitigants: List[Dict[str, str]]
    execution_time_seconds: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
