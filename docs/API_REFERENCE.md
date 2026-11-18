# Complete API Reference

This document provides a comprehensive API reference for all packages, modules, classes, methods, data models, and functions within **`autonomous-multi-agent-real`**.

---

## Table of Contents

1. [Domain Models & Types (`autonomous_multi_agent_real.types`)](#1-domain-models--types-autonomous_multi_agent_realtypes)
2. [Workflow & Pipeline Orchestrator (`autonomous_multi_agent_real.engine.workflow`)](#2-workflow--pipeline-orchestrator-autonomous_multi_agent_realengineworkflow)
3. [Financial Math Engine (`autonomous_multi_agent_real.engine.financial`)](#3-financial-math-engine-autonomous_multi_agent_realenginefinancial)
4. [Monte Carlo Simulation Engine (`autonomous_multi_agent_real.engine.monte_carlo`)](#4-monte-carlo-simulation-engine-autonomous_multi_agent_realenginemonte_carlo)
5. [Private Equity Waterfall Engine (`autonomous_multi_agent_real.engine.waterfall`)](#5-private-equity-waterfall-engine-autonomous_multi_agent_realenginewaterfall)
6. [Sensitivity & Breakeven Engine (`autonomous_multi_agent_real.engine.sensitivity`)](#6-sensitivity--breakeven-engine-autonomous_multi_agent_realenginesensitivity)
7. [Tax Depreciation & After-Tax Engine (`autonomous_multi_agent_real.engine.tax`)](#7-tax-depreciation--after-tax-engine-autonomous_multi_agent_realenginetax)
8. [Deal Optimization Solver (`autonomous_multi_agent_real.engine.optimizer`)](#8-deal-optimization-solver-autonomous_multi_agent_realengineoptimizer)
9. [Underwriting Swarm Agents (`autonomous_multi_agent_real.agents`)](#9-underwriting-swarm-agents-autonomous_multi_agent_realagents)
10. [Agent Collaboration & Blackboard Protocol (`autonomous_multi_agent_real.collaboration`)](#10-agent-collaboration--blackboard-protocol-autonomous_multi_agent_realcollaboration)
11. [Institutional Credit Policy Rule Engine (`autonomous_multi_agent_real.rules`)](#11-institutional-credit-policy-rule-engine-autonomous_multi_agent_realrules)
12. [Portfolio Aggregation & Stress Testing (`autonomous_multi_agent_real.portfolio`)](#12-portfolio-aggregation--stress-testing-autonomous_multi_agent_realportfolio)
13. [Reporting & Data Export (`autonomous_multi_agent_real.reporting`)](#13-reporting--data-export-autonomous_multi_agent_realreporting)
14. [Deal Storage & Audit Repository (`autonomous_multi_agent_real.storage`)](#14-deal-storage--audit-repository-autonomous_multi_agent_realstorage)
15. [Command-Line Interface Commands (`autonomous_multi_agent_real.cli`)](#15-command-line-interface-commands-autonomous_multi_agent_realcli)
16. [Feature Store Subsystem (`autonomous_multi_agent_real.features`)](#16-feature-store-subsystem-autonomous_multi_agent_realfeatures)

---

## 1. Domain Models & Types (`autonomous_multi_agent_real.types`)

### Enums

#### `PropertyType(str, Enum)`
Real estate asset classifications:
* `SINGLE_FAMILY = "single_family"`
* `MULTI_FAMILY = "multi_family"`
* `COMMERCIAL = "commercial"`
* `INDUSTRIAL = "industrial"`
* `MIXED_USE = "mixed_use"`

#### `AgentRole(str, Enum)`
Identifiers for specialized swarm agents:
* `ACQUISITION = "acquisition"`
* `MARKET_COMPS = "market_comps"`
* `DEBT_FINANCING = "debt_financing"`
* `CASH_FLOW = "cash_flow"`
* `RISK_SIMULATION = "risk_simulation"`
* `INVESTMENT_COMMITTEE = "investment_committee"`

#### `AgentDecisionStatus(str, Enum)`
Agent-level evaluation verdict:
* `APPROVED = "approved"`
* `CONDITIONAL = "conditional"`
* `FLAGGED = "flagged"`
* `REJECTED = "rejected"`

#### `InvestmentDecision(str, Enum)`
Consolidated Investment Committee consensus outcome:
* `APPROVED = "approved"`
* `CONDITIONAL = "conditional"`
* `REJECTED = "rejected"`

#### `WorkflowStage(str, Enum)`
State machine stages of the underwriting lifecycle:
* `INTAKE = "intake"`
* `MARKET_ANALYSIS = "market_analysis"`
* `DEBT_SIZING = "debt_sizing"`
* `CASH_FLOW_SIMULATION = "cash_flow_simulation"`
* `RISK_MODELING = "risk_modeling"`
* `COMMITTEE_SYNTHESIS = "committee_synthesis"`
* `COMPLETED = "completed"`
* `FAILED = "failed"`

---

### Core Data Models

#### `UnitMixItem`
Represents an individual unit layout specification within a property:
```python
class UnitMixItem(BaseModel):
    unit_type: str  # e.g., "1BR/1BA", "2BR/2BA"
    count: int  # Unit count (ge=1)
    square_feet: float  # Average square footage per unit (gt=0)
    current_rent: float  # In-place monthly rent per unit (ge=0)
    market_rent: float  # Projected market monthly rent (ge=0)
```
**Methods:**
* `total_monthly_current_rent() -> float`: `count * current_rent`
* `total_monthly_market_rent() -> float`: `count * market_rent`
* `loss_to_lease() -> float`: `max(0.0, total_monthly_market_rent - total_monthly_current_rent)`

#### `OperatingExpenses`
Itemized annual operating expenses:
```python
class OperatingExpenses(BaseModel):
    property_taxes: float
    insurance: float
    repairs_and_maintenance: float
    property_management_pct: float = 0.08  # Percentage of EGI (0.0 to 0.30)
    utilities: float = 0.0
    admin_and_legal: float = 0.0
    replacement_reserves_per_unit: float = 250.0
    other_expenses: float = 0.0
```
**Methods:**
* `fixed_annual_expenses(unit_count: int) -> float`: Calculates total expenses excluding variable management fee.

#### `FinancingTerms`
Capital markets and debt parameters:
```python
class FinancingTerms(BaseModel):
    purchase_price: float
    down_payment_pct: float = 0.25  # Equity down payment fraction (0.05 to 1.0)
    interest_rate: float = 0.065  # Annual interest rate (0.01 to 0.25)
    amortization_years: int = 30  # Loan amortization (5 to 40 years)
    loan_term_years: int = 10  # Maturity term (1 to 30 years)
    interest_only_months: int = 0  # Initial IO period in months (0 to 120)
    closing_costs_pct: float = 0.02  # Financing & closing fee % (0.0 to 0.10)
```

#### `PropertyDeal`
Complete property deal specification:
```python
class PropertyDeal(BaseModel):
    id: str
    title: str
    address: str
    property_type: PropertyType = PropertyType.MULTI_FAMILY
    gross_square_feet: float
    unit_mix: List[UnitMixItem]
    purchase_price: float
    rehab_budget: float = 0.0
    current_occupancy_pct: float = 0.95
    market_occupancy_pct: float = 0.95
    annual_rent_growth_pct: float = 0.03
    annual_expense_growth_pct: float = 0.025
    hold_period_years: int = 5
    exit_cap_rate: float = 0.065
    selling_costs_pct: float = 0.02
    expenses: OperatingExpenses
    financing: FinancingTerms
```
**Properties:**
* `total_units -> int`
* `total_current_monthly_rent -> float`
* `total_market_monthly_rent -> float`
* `total_current_annual_rent -> float`
* `total_market_annual_rent -> float`
* `total_acquisition_basis -> float`: `purchase_price + rehab_budget + (purchase_price * closing_costs_pct)`

#### `DebtSizingResult`
Outputs of loan constraint analysis:
```python
class DebtSizingResult(BaseModel):
    loan_amount: float
    equity_required: float
    monthly_payment: float
    annual_debt_service: float
    ltv_ratio: float
    dscr_year1: float
    debt_yield_pct: float
    binding_constraint: str  # "LTV", "DSCR", or "Debt Yield"
```

#### `AnnualCashFlow`
Single-year pro-forma cash flow line items:
```python
class AnnualCashFlow(BaseModel):
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
```

#### `DealMetrics`
Consolidated deal return and leverage ratios:
```python
class DealMetrics(BaseModel):
    unlevered_irr: float
    levered_irr: float
    equity_multiple: float
    net_present_value: float
    average_cash_on_cash: float
    entry_cap_rate: float
    exit_cap_rate: float
    min_dscr: float
    average_dscr: float
```

#### `MonteCarloSimulationResult`
Stochastic risk assessment metrics:
```python
class MonteCarloSimulationResult(BaseModel):
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
    distribution_quantiles: Dict[str, float]
    var_95_irr: Optional[float] = None
    cvar_95_irr: Optional[float] = None
    var_99_irr: Optional[float] = None
    cvar_99_irr: Optional[float] = None
    variance_attribution: Dict[str, float]
```

#### `UnderwritingResult`
Final consolidated underwriting assessment dossier:
```python
class UnderwritingResult(BaseModel):
    deal_id: str
    deal_title: str
    decision: InvestmentDecision
    committee_score: float  # 0.0 to 100.0
    deal_metrics: DealMetrics
    debt_sizing: DebtSizingResult
    cash_flows: List[AnnualCashFlow]
    monte_carlo: MonteCarloSimulationResult
    agent_reports: Dict[str, AgentAnalysisReport]
    executive_summary: str
    investment_thesis: List[str]
    key_risks_and_mitigants: List[Dict[str, str]]
    execution_time_seconds: float
    timestamp: datetime
    waterfall: Optional[WaterfallResult] = None
    sensitivity: Optional[SensitivityMatrix] = None
    breakeven: Optional[BreakevenMetrics] = None
    tax_analysis: Optional[TaxAnalysisResult] = None
    pricing_optimization: Optional[PricingOptimizationResult] = None
    compliance_report: Optional[Any] = None
    debate_transcript: Optional[Any] = None
```

---

## 2. Workflow & Pipeline Orchestrator (`autonomous_multi_agent_real.engine.workflow`)

### `DealPipeline`

Coordinates agent execution and invokes core analytical engines.

```python
class DealPipeline:
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
    ): ...
```

#### Methods

* `run(deal: PropertyDeal) -> UnderwritingResult`:
  Synchronously executes the full 8-stage underwriting workflow. Raises `RuntimeError` if mandatory outputs cannot be generated.
* `run_async(deal: PropertyDeal) -> Awaitable[UnderwritingResult]`:
  Asynchronous execution wrapper.

---

## 3. Financial Math Engine (`autonomous_multi_agent_real.engine.financial`)

### Functions

#### `calculate_monthly_mortgage_payment(principal: float, annual_interest_rate: float, amortization_years: int) -> float`
Calculates fixed monthly principal and interest payment. Returns $0.0$ if principal $\le 0$.

#### `calculate_loan_amortization_schedule(principal: float, annual_interest_rate: float, amortization_years: int, hold_period_years: int, interest_only_months: int = 0) -> List[Tuple[float, float, float]]`
Generates annual schedule returning `(annual_principal_paid, annual_interest_paid, ending_loan_balance)` for each year.

#### `calculate_npv(discount_rate: float, cash_flows: List[float]) -> float`
Calculates Net Present Value for a cash flow series starting at $t=0$.

#### `calculate_irr(cash_flows: List[float], max_iter: int = 200, tol: float = 1e-6) -> float`
Solves for Internal Rate of Return using hybrid Newton-Raphson with bisection fallback. Requires at least one negative and one positive cash flow.

#### `calculate_equity_multiple(initial_equity: float, total_cash_returned: float) -> float`
Calculates `total_cash_returned / initial_equity`. Returns $0.0$ if initial equity $\le 0$.

#### `calculate_dscr(noi: float, annual_debt_service: float) -> float`
Calculates Debt Service Coverage Ratio (`noi / annual_debt_service`). Returns `99.99` if debt service is zero.

#### `calculate_debt_yield(noi: float, loan_amount: float) -> float`
Calculates Debt Yield (`noi / loan_amount`).

#### `calculate_cap_rate(noi: float, property_value: float) -> float`
Calculates Capitalization Rate (`noi / property_value`).

#### `calculate_exit_sale_proceeds(exit_year_noi: float, exit_cap_rate: float, selling_costs_pct: float = 0.02) -> float`
Calculates net terminal sale proceeds after transaction costs.

---

## 4. Monte Carlo Simulation Engine (`autonomous_multi_agent_real.engine.monte_carlo`)

### `MonteCarloEngine`

```python
class MonteCarloEngine:
    def __init__(self, seed: Optional[int] = 42, enable_correlated_shocks: bool = True): ...
```

#### Methods

* `simulate(deal: PropertyDeal, debt_sizing: DebtSizingResult, iterations: int = 1000) -> MonteCarloSimulationResult`:
  Executes high-speed stochastic simulation with Cholesky-correlated macro shocks. Computes mean, standard deviation, P10/P50/P90 quantiles, probability of loss, probability of DSCR breach, VaR (95/99), CVaR (95/99), and variance attribution.

---

## 5. Private Equity Waterfall Engine (`autonomous_multi_agent_real.engine.waterfall`)

### `get_default_waterfall_structure(preferred_return_rate: float = 0.08, lp_equity_pct: float = 0.90, gp_equity_pct: float = 0.10) -> WaterfallStructure`
Generates standard 4-tier institutional promote structure (8% pref, 80/20 to 14%, 70/30 to 18%, 50/50 residual).

### `WaterfallEngine`

```python
class WaterfallEngine:
    def __init__(self, structure: Optional[WaterfallStructure] = None): ...
```

#### Methods

* `calculate(total_equity: float, annual_cash_flows: List[float]) -> WaterfallResult`:
  Distributes annual cash flows across LP and GP tiers, accounting for capital return, compounding preferred return, promote participation, and returns separate LP/GP IRRs and Equity Multiples.

---

## 6. Sensitivity & Breakeven Engine (`autonomous_multi_agent_real.engine.sensitivity`)

### `SensitivityEngine`

```python
class SensitivityEngine:
    @staticmethod
    def generate_matrix(
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
        row_param: str,
        row_values: List[float],
        col_param: str,
        col_values: List[float],
    ) -> SensitivityMatrix: ...

    @staticmethod
    def generate_cap_vs_rent_growth_matrix(
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
        cap_steps: int = 5,
        rent_steps: int = 5,
    ) -> SensitivityMatrix: ...

    @staticmethod
    def calculate_breakeven_metrics(
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
    ) -> BreakevenMetrics: ...

    @staticmethod
    def run_scenario_comparison(
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
    ) -> Dict[str, DealMetrics]: ...
```

---

## 7. Tax Depreciation & After-Tax Engine (`autonomous_multi_agent_real.engine.tax`)

### `TaxEngine`

```python
class TaxEngine:
    def __init__(
        self,
        land_value_pct: float = 0.20,
        ordinary_income_tax_rate: float = 0.37,
        capital_gains_tax_rate: float = 0.20,
        depreciation_recapture_rate: float = 0.25,
        enable_cost_segregation: bool = False,
        cost_seg_5yr_pct: float = 0.12,
        cost_seg_15yr_pct: float = 0.08,
        year1_bonus_depreciation_pct: float = 0.60,
    ): ...
```

#### Methods

* `compute_depreciation_schedule(deal: PropertyDeal, hold_years: int) -> List[float]`:
  Generates annual MACRS depreciation allowances (27.5-year residential or 39-year commercial, with optional cost segregation).
* `analyze(deal: PropertyDeal, debt_sizing: DebtSizingResult, annual_nois: List[float], exit_gross_proceeds: float) -> TaxAnalysisResult`:
  Computes full annual tax shielding, depreciation recapture tax at exit, capital gains tax, and pre-tax vs. after-tax IRR and Equity Multiples.

---

## 8. Deal Optimization Solver (`autonomous_multi_agent_real.engine.optimizer`)

### `DealOptimizer`

```python
class DealOptimizer:
    @staticmethod
    def solve_max_offer_price(
        deal: PropertyDeal,
        target_levered_irr: float = 0.15,
        target_min_dscr: float = 1.25,
        target_min_debt_yield: float = 0.08,
        tol: float = 1000.0,
        max_iter: int = 50,
    ) -> PricingOptimizationResult: ...

    @staticmethod
    def solve_required_monthly_rent(
        deal: PropertyDeal,
        target_levered_irr: float = 0.15,
        tol: float = 1.0,
        max_iter: int = 50,
    ) -> float: ...
```

---

## 9. Underwriting Swarm Agents (`autonomous_multi_agent_real.agents`)

All agents inherit from `BaseAgent`:
```python
class BaseAgent(ABC):
    role: AgentRole
    name: str

    @abstractmethod
    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport: ...
```

### Agents:
* **`AcquisitionAgent`**: Analyzes unit mix, square footage, purchase price per unit/sqft, initial yield, and rehab capital requirements.
* **`MarketCompsAgent`**: Evaluates rent roll vs. market comps, in-place vs. market vacancy, loss-to-lease mark-to-market upside, and submarket cap rate spreads.
* **`DebtAgent`**: Sizes senior debt across maximum LTV, minimum DSCR, and minimum Debt Yield constraints; identifies binding constraint.
* **`CashFlowAgent`**: Models multi-year operating pro-forma, debt service, terminal reversion, unlevered/levered IRR, equity multiple, and NPV.
* **`RiskMonteCarloAgent`**: Executes vectorized Monte Carlo simulation, calculates VaR/CVaR, and flags downside probability breaches.
* **`InvestmentCommitteeAgent`**: Synthesizes all agent reports, computes composite score (0-100), applies risk penalties, and issues final verdict (`APPROVED`, `CONDITIONAL`, `REJECTED`).

---

## 10. Agent Collaboration & Blackboard Protocol (`autonomous_multi_agent_real.collaboration`)

### `MessageBus`
Publish-subscribe in-memory broker supporting wildcard pattern matching (`"*"`, `"debt.*"`):
* `subscribe(topic_pattern: str, handler: Callable[[AgentMessage], None]) -> None`
* `publish(message: AgentMessage) -> None`
* `get_history(topic_filter: Optional[str] = None) -> List[AgentMessage]`

### `Blackboard`
Thread-safe shared memory:
* `set_fact(key: str, value: Any, source_agent: str, confidence: float = 1.0) -> None`
* `get_fact(key: str) -> Optional[Any]`
* `acquire_lock(key: str, owner: str) -> bool`
* `release_lock(key: str, owner: str) -> bool`

### `DeliberationEngine`
Coordinates cross-agent challenge rounds and rebuttals:
* `conduct_deliberation(context: DealWorkflowContext) -> DebateTranscript`

---

## 11. Institutional Credit Policy Rule Engine (`autonomous_multi_agent_real.rules`)

### `RuleEngine`
```python
class RuleEngine:
    def __init__(self, rules: Optional[List[RuleDefinition]] = None): ...
    def register_rule(self, rule: RuleDefinition) -> None: ...
    def evaluate(self, context: DealWorkflowContext) -> ComplianceReport: ...
```

### Standard Policy Rules (`get_default_institutional_rules`):
* `POL-LEV-01`: Senior LTV $\le 80.0\%$ (`ERROR`)
* `POL-LEV-02`: Target Senior LTV $\le 75.0\%$ (`WARNING`)
* `POL-DSCR-01`: Min DSCR Floor $\ge 1.15\text{x}$ (`ERROR`)
* `POL-DSCR-02`: Target DSCR Guideline $\ge 1.25\text{x}$ (`WARNING`)
* `POL-DY-01`: Minimum Debt Yield $\ge 7.0\%$ (`ERROR`)
* `POL-RET-01`: Minimum Levered IRR $\ge 10.0\%$ (`ERROR`)
* `POL-RET-02`: Target Levered IRR $\ge 14.0\%$ (`WARNING`)
* `POL-RES-01`: Minimum Reserves $\ge \$250/\text{unit}/\text{year}$ (`WARNING`)
* `POL-BASIS-01`: Maximum Basis per Unit $\le \$350,000$ (`WARNING`)

---

## 12. Portfolio Aggregation & Stress Testing (`autonomous_multi_agent_real.portfolio`)

### `PortfolioManager`
```python
class PortfolioManager:
    def __init__(self, portfolio_id: str = "main", portfolio_name: str = "Core Portfolio"): ...
    def add_deal(self, deal: PropertyDeal, underwriting_result: UnderwritingResult) -> None: ...
    def remove_deal(self, deal_id: str) -> bool: ...
    def calculate_rollup(self) -> PortfolioRollup: ...
```

### `PortfolioStressEngine`
```python
class PortfolioStressEngine:
    @staticmethod
    def get_default_stress_scenarios() -> List[PortfolioStressScenario]: ...
    @staticmethod
    def run_stress_test(
        portfolio: PortfolioManager, scenario: PortfolioStressScenario
    ) -> Dict[str, Any]: ...
```

---

## 13. Reporting & Data Export (`autonomous_multi_agent_real.reporting`)

### `InvestmentMemoGenerator`
* `generate_memo(deal: PropertyDeal, result: UnderwritingResult, compliance_report: Optional[ComplianceReport] = None) -> str`:
  Produces complete Markdown-formatted Investment Committee Underwriting Memorandum.

### `DataExporter`
* `export_to_json(result: UnderwritingResult, file_path: Path | str) -> None`
* `export_to_csv(result: UnderwritingResult, file_path: Path | str) -> None`

---

## 14. Deal Storage & Audit Repository (`autonomous_multi_agent_real.storage`)

### `DealRepository`
```python
class DealRepository:
    def __init__(self, data_dir: Optional[Path | str] = None): ...
    def save_deal(self, deal: PropertyDeal) -> None: ...
    def get_deal(self, deal_id: str) -> Optional[PropertyDeal]: ...
    def list_deals(
        self,
        property_type: Optional[str] = None,
        min_units: Optional[int] = None,
        max_price: Optional[float] = None,
        min_cap_rate: Optional[float] = None,
    ) -> List[PropertyDeal]: ...
    def delete_deal(self, deal_id: str) -> bool: ...
    def create_revision(
        self,
        deal: PropertyDeal,
        author: str = "analyst",
        change_summary: str = "Assumptions update",
    ) -> DealRevision: ...
    def get_revisions(self, deal_id: str) -> List[DealRevision]: ...
    def diff_revisions(self, deal_id: str, rev1: int, rev2: int) -> List[DealRevisionDiff]: ...
    def revert_to_revision(self, deal_id: str, rev_number: int) -> Optional[PropertyDeal]: ...
    def save_portfolio(self, rollup: PortfolioRollup) -> None: ...
    def get_portfolio(self, portfolio_id: str) -> Optional[PortfolioRollup]: ...
```

---

## 15. Command-Line Interface Commands (`autonomous_multi_agent_real.cli`)

| Command | Synopsis | Key Options |
| :--- | :--- | :--- |
| `list` | List and filter deals in repository | `-t/--property-type`, `--min-units`, `--max-price`, `--min-cap` |
| `show` | Display full property specifications | `-d/--deal-id` |
| `underwrite` | Run full multi-agent workflow DAG | `-d/--deal-id`, `-i/--iterations`, `-s/--seed`, `-m/--memo-out`, `-e/--export` |
| `simulate` | Run Monte Carlo risk simulation | `-d/--deal-id`, `-i/--iterations`, `--seed`, `--no-correlated-shocks` |
| `quick` | Quick underwriting with CLI overrides | `-p/--price`, `-u/--units`, `-r/--rent`, `-t/--type`, `--rate`, `--ltv` |
| `waterfall` | Compute GP/LP promote distributions | `-d/--deal-id`, `--pref`, `--lp-share`, `--gp-share` |
| `sensitivity`| Run 2D stress matrix & breakeven | `-d/--deal-id`, `--steps` |
| `tax` | Compute MACRS depreciation & taxes | `-d/--deal-id`, `--cost-seg`, `--land-pct`, `--tax-rate` |
| `optimize` | Solve max purchase price for hurdle | `-d/--deal-id`, `--target-irr`, `--min-dscr`, `--min-debt-yield` |
| `audit` | Check institutional credit policies | `-d/--deal-id` |
| `debate` | Run swarm deliberation challenge rounds | `-d/--deal-id` |
| `portfolio` | Consolidate portfolio & stress test | `--portfolio-id`, `--stress` |
| `memo` | Generate Markdown IC Underwriting Memo | `-d/--deal-id`, `-o/--out` |
| `export` | Export underwriting output to CSV/JSON | `-d/--deal-id`, `-f/--format`, `-o/--out` |
| `deal` | Manage repository, diffs, & revisions | `import`, `export`, `delete`, `revisions`, `create-revision`, `diff`, `revert` |
| `interactive` | Launch interactive terminal shell | *(None)* |
| `features` | Real-time feature store inspection & ML dataset operations | `status`, `list`, `show`, `inspect`, `backfill`, `sync`, `audit`, `dataset` |

---

## 16. Feature Store Subsystem (`autonomous_multi_agent_real.features`)

The Feature Store subsystem provides an institutional-grade, dual-tier feature store architecture combining streaming ingestion, in-memory low-latency serving, partitioned offline Apache Parquet persistence, point-in-time historical joins, statistical drift monitoring, and automated pipeline interception.

### 16.1 Domain Models & Types (`autonomous_multi_agent_real.features.types`)

#### Enums

* **`FeatureDataType(str, Enum)`**: Supported primitive and composite data types:
  * `FLOAT = "float"`
  * `INT = "int"`
  * `STRING = "string"`
  * `BOOLEAN = "boolean"`
  * `TIMESTAMP = "timestamp"`
  * `VECTOR = "vector"`
  * `JSON = "json"`
  * Method: `to_arrow_type() -> pa.DataType` converts to native PyArrow representation.

* **`FeatureCategory(str, Enum)`**: Domain taxonomy for underwriting features:
  * `PROPERTY = "property"`
  * `FINANCIAL = "financial"`
  * `MARKET = "market"`
  * `DEBT = "debt"`
  * `RISK = "risk"`
  * `LOCATION = "location"`
  * `DERIVED = "derived"`
  * `TIME_SERIES = "time_series"`

* **`FeatureTimeWindow(str, Enum)`**: Window intervals for streaming aggregations:
  * `REALTIME = "realtime"`
  * `HOURLY = "1h"`
  * `DAILY = "24h"`
  * `WEEKLY = "7d"`
  * `MONTHLY = "30d"`
  * `QUARTERLY = "90d"`
  * `ALL_TIME = "all_time"`

* **`FeatureStreamStatus(str, Enum)`**: Lifecycle statuses for in-flight streaming records:
  * `BUFFERED = "buffered"`
  * `INGESTING = "ingesting"`
  * `COMMITTED = "committed"`
  * `FAILED = "failed"`
  * `DEAD_LETTER = "dead_letter"`

#### Pydantic Schemas

```python
class FeatureMetadata(BaseModel):
    name: str
    category: FeatureCategory
    data_type: FeatureDataType = FeatureDataType.FLOAT
    description: str = ""
    unit: Optional[str] = None
    is_nullable: bool = True
    tags: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    window: FeatureTimeWindow = FeatureTimeWindow.REALTIME
    created_at: datetime
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    # Properties & methods:
    # is_derived -> bool
    # to_arrow_field() -> pa.Field


class FeatureValue(BaseModel):
    feature_name: str
    value: Any
    data_type: Optional[FeatureDataType] = None
    confidence: float = 1.0  # [0.0, 1.0]
    timestamp: datetime


class FeatureRecord(BaseModel):
    entity_id: str
    entity_type: str = "deal"
    feature_name: str
    value: Any
    timestamp: datetime
    source: str = "pipeline"
    partition_key: Optional[str] = None


class FeatureVector(BaseModel):
    entity_id: str
    entity_type: str = "deal"
    features: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    schema_version: str = "1.0.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Methods: get(), has_feature(), to_dict(), to_numeric_array()


class FeatureStreamEvent(BaseModel):
    event_id: str
    event_type: str = "feature_update"
    stream_name: str = "real_estate_underwriting_stream"
    entity_id: str
    entity_type: str = "deal"
    payload: Dict[str, Any]
    event_time: datetime
    status: FeatureStreamStatus = FeatureStreamStatus.BUFFERED
    retry_count: int = 0
    error_message: Optional[str] = None


class StreamBufferConfig(BaseModel):
    buffer_size: int = 1000
    flush_interval_seconds: float = 5.0
    max_retries: int = 3
    dead_letter_queue_enabled: bool = True


class ParquetPartitionSpec(BaseModel):
    partition_columns: List[str] = ["year", "month"]
    row_group_size: int = 10000
    compression: str = "SNAPPY"


class OnlineStoreConfig(BaseModel):
    ttl_seconds: int = 86400
    max_entities: int = 10000
    eviction_policy: str = "LRU"


class FeatureStatistics(BaseModel):
    feature_name: str
    count: int
    null_count: int
    null_rate: float
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    p99: Optional[float] = None


class FeatureQualityReport(BaseModel):
    is_valid: bool = True
    dataset_name: str = "feature_dataset"
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    overall_quality_score: float = 1.0
    total_features_checked: int = 0
    missing_features: List[str] = Field(default_factory=list)
    null_rate_violations: Dict[str, float] = Field(default_factory=dict)
    range_violations: Dict[str, str] = Field(default_factory=dict)
    validation_timestamp: datetime


class MaterializationJob(BaseModel):
    job_id: str
    status: str  # "completed", "failed", "running"
    source: str
    destination: str
    records_processed: int = 0
    features_count: int = 0
    entities_count: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


class ObservationTarget(BaseModel):
    entity_id: str
    timestamp: datetime
    target_value: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

#### PyArrow Helper Functions

```python
def to_arrow_schema(definitions: Sequence[FeatureMetadata]) -> pa.Schema: ...
def feature_vectors_to_arrow_table(
    vectors: Sequence[FeatureVector], schema: Optional[pa.Schema] = None
) -> pa.Table: ...
def feature_records_to_arrow_table(records: Sequence[FeatureRecord]) -> pa.Table: ...
def table_to_safe_pydict(table: pa.Table) -> Dict[str, List[Any]]: ...
```

---

### 16.2 Feature Registry (`autonomous_multi_agent_real.features.registry`)

The central schema registry governing definition, registration, versioning, derivation rules, and constraints for all feature dimensions.

```python
class FeatureRegistry:
    def __init__(self) -> None: ...
    def register(self, metadata: FeatureMetadata) -> None: ...
    def register_derived(
        self, metadata: FeatureMetadata, compute_fn: Callable[[Dict[str, Any]], Any]
    ) -> None: ...
    def get(self, name: str) -> Optional[FeatureMetadata]: ...
    def list_features(
        self, category: Optional[FeatureCategory] = None, tags: Optional[List[str]] = None
    ) -> List[FeatureMetadata]: ...
    def compute_derived_features(self, raw_features: Dict[str, Any]) -> Dict[str, Any]: ...
    def validate_features(
        self, features: Dict[str, Any], allow_missing: bool = True
    ) -> Tuple[bool, List[str]]: ...
    def get_arrow_schema(self, feature_names: Optional[Sequence[str]] = None) -> pa.Schema: ...
    def to_dict(self) -> Dict[str, Any]: ...
    def from_dict(self, data: Dict[str, Any]) -> None: ...


def get_default_registry() -> FeatureRegistry:
    """Return singleton institutional registry populated with underwriting metrics:
    cap_rate, in_place_noi, stabilized_noi, dscr, ltv, debt_yield,
    gross_rent_multiplier, expense_ratio, break_even_occupancy,
    purchase_price_per_unit, purchase_price_per_sqft, and derived ratios.
    """
```

---

### 16.3 Feature Extraction & Streaming Aggregator (`autonomous_multi_agent_real.features.extractor`)

Extracts normalized feature vectors and atomic records from raw domain objects (`PropertyDeal`, `UnderwritingResult`), dictionaries, and streaming events.

```python
class FeatureExtractor:
    def __init__(self, registry: Optional[FeatureRegistry] = None) -> None: ...
    def extract_deal_features(
        self, deal: PropertyDeal, context: Optional[Any] = None
    ) -> FeatureVector: ...
    def extract_deal_records(
        self, deal: PropertyDeal, context: Optional[Any] = None
    ) -> List[FeatureRecord]: ...
    def extract_from_underwrite(
        self, deal: PropertyDeal, underwrite_result: Any
    ) -> FeatureVector: ...
    def extract_from_dict(
        self, data: Dict[str, Any], entity_id: str, entity_type: str = "deal"
    ) -> FeatureVector: ...
    def extract_from_stream_event(self, event: FeatureStreamEvent) -> FeatureVector: ...


class WindowedAggregator:
    def __init__(self, window_size_seconds: float = 3600.0) -> None: ...
    def add_observation(
        self, feature_name: str, value: float, timestamp: Optional[datetime] = None
    ) -> None: ...
    def get_window_statistics(
        self, feature_name: str, as_of: Optional[datetime] = None
    ) -> Dict[str, float]: ...
    def get_all_statistics(
        self, as_of: Optional[datetime] = None
    ) -> Dict[str, Dict[str, float]]: ...
    def clean_expired(self, current_time: Optional[datetime] = None) -> int: ...
```

---

### 16.4 Storage Engines: Columnar Parquet & Low-Latency Online Store (`storage.py`, `serving.py`)

#### `ParquetFeatureStore`
Provides partitioned, columnar disk storage for offline analytics, time-travel point-in-time queries, and batch training data compilation.

```python
class ParquetFeatureStore:
    def __init__(
        self,
        base_path: Union[str, Path],
        partition_spec: Optional[ParquetPartitionSpec] = None,
        registry: Optional[FeatureRegistry] = None,
    ) -> None: ...
    def write_vectors(self, vectors: Sequence[FeatureVector]) -> int: ...
    def write_records(self, records: Sequence[FeatureRecord]) -> int: ...
    def query(
        self,
        entity_ids: Optional[Sequence[str]] = None,
        feature_names: Optional[Sequence[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> pa.Table: ...
    def query_as_of(
        self, entity_id: str, as_of_time: datetime, feature_names: Optional[Sequence[str]] = None
    ) -> Optional[FeatureVector]: ...
    def get_latest_vector(self, entity_id: str) -> Optional[FeatureVector]: ...
    def compact_partitions(self) -> int: ...
```

#### `OnlineFeatureStore` & `FeatureServingService`
Provides high-throughput sub-millisecond feature vector retrieval backed by an in-memory thread-safe LRU cache with TTL expiration.

```python
class OnlineFeatureStore:
    def __init__(self, config: Optional[OnlineStoreConfig] = None) -> None: ...
    def put_vector(self, vector: FeatureVector) -> None: ...
    def put_record(self, record: FeatureRecord) -> None: ...
    def put_records(self, records: Sequence[FeatureRecord]) -> None: ...
    def get_feature(self, entity_id: str, feature_name: str) -> Optional[Any]: ...
    def get_vector(self, entity_id: str) -> Optional[FeatureVector]: ...
    def get_batch_vectors(self, entity_ids: Sequence[str]) -> Dict[str, FeatureVector]: ...
    def delete_entity(self, entity_id: str) -> bool: ...
    def clear(self) -> None: ...
    def size(self) -> int: ...


class FeatureServingService:
    def __init__(
        self, online_store: OnlineFeatureStore, offline_store: Optional[ParquetFeatureStore] = None
    ) -> None: ...
    def get_online_features(
        self,
        entity_id: str,
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
    ) -> Dict[str, Any]: ...
    def get_feature_vector(
        self, entity_id: str, entity_type: str = "deal", fallback_to_offline: bool = True
    ) -> Optional[FeatureVector]: ...
    def get_batch_features(
        self,
        entity_ids: Sequence[str],
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
    ) -> Dict[str, Dict[str, Any]]: ...
    def get_feature_matrix(
        self, entity_ids: Sequence[str], feature_names: Sequence[str], entity_type: str = "deal"
    ) -> Dict[str, List[Any]]: ...
```

---

### 16.5 Streaming Buffer & Materialization Engine (`buffer.py`, `materialization.py`)

#### `StreamFeatureBuffer`
Thread-safe ingestion buffer handling micro-batches, backpressure, watermarks, and dead-letter queues.

```python
class StreamFeatureBuffer:
    def __init__(
        self,
        config: Optional[StreamBufferConfig] = None,
        on_flush: Optional[Callable[[List[FeatureStreamEvent]], None]] = None,
    ) -> None: ...
    def push_event(self, event: FeatureStreamEvent) -> bool: ...
    def push_vector(self, vector: FeatureVector) -> bool: ...
    def push_record(self, record: FeatureRecord) -> bool: ...
    def flush(self) -> List[FeatureStreamEvent]: ...
    def drain_dead_letter_queue(self) -> List[FeatureStreamEvent]: ...
    def size(self) -> int: ...
```

#### `MaterializationEngine`
Coordinates asynchronous or on-demand synchronization between in-memory streaming buffers, offline Parquet storage, and online cache.

```python
class MaterializationEngine:
    def __init__(
        self,
        offline_store: ParquetFeatureStore,
        online_store: OnlineFeatureStore,
        buffer: Optional[StreamFeatureBuffer] = None,
        extractor: Optional[FeatureExtractor] = None,
    ) -> None: ...
    def materialize_to_online(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        entity_ids: Optional[Sequence[str]] = None,
    ) -> MaterializationJob: ...
    def flush_buffer_to_parquet(self) -> MaterializationJob: ...
    def backfill_deals(
        self, deals: Sequence[PropertyDeal], sync_online: bool = True
    ) -> MaterializationJob: ...
    def sync_audit(self) -> Dict[str, Any]: ...
```

---

### 16.6 Training Dataset Generator (`autonomous_multi_agent_real.features.training`)

Compiles point-in-time feature tables joined to observation targets while strictly preventing data leakage across historical underwriting milestones.

```python
class TrainingDataset(BaseModel):
    name: str
    feature_names: List[str]
    target_column: Optional[str] = None
    train_vectors: List[FeatureVector] = Field(default_factory=list)
    val_vectors: List[FeatureVector] = Field(default_factory=list)
    test_vectors: List[FeatureVector] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Methods: to_arrow_table(), to_dict(), export_parquet()


class TrainingDatasetGenerator:
    def __init__(
        self, offline_store: ParquetFeatureStore, registry: Optional[FeatureRegistry] = None
    ) -> None: ...
    def build_dataset(
        self,
        observations: Sequence[ObservationTarget],
        dataset_name: str,
        feature_names: Optional[Sequence[str]] = None,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> TrainingDataset: ...
    def compute_feature_correlations(
        self, dataset: TrainingDataset
    ) -> Dict[str, Dict[str, float]]: ...
```

---

### 16.7 Feature Quality & Statistical Drift Engine (`autonomous_multi_agent_real.features.quality`)

Performs statistical profiling, boundary constraint validation, and drift analysis.

```python
class FeatureQualityEngine:
    def __init__(self, registry: Optional[FeatureRegistry] = None) -> None: ...
    def compute_statistics(
        self, vectors: Sequence[FeatureVector]
    ) -> Dict[str, FeatureStatistics]: ...
    def audit_dataset(
        self, vectors: Sequence[FeatureVector], dataset_name: str = "dataset"
    ) -> FeatureQualityReport: ...
    def detect_drift(
        self,
        baseline_vectors: Sequence[FeatureVector],
        current_vectors: Sequence[FeatureVector],
        threshold_p_value: float = 0.05,
    ) -> Dict[str, Any]: ...
```

---

### 16.8 Context Enrichment & Pipeline Interception (`enricher.py`, `interceptor.py`)

#### `FeatureContextEnricher`
Augments raw deals with peer-cohort percentiles, z-scores, and benchmark spreads for institutional comparative underwriting.

```python
class FeatureContextEnricher:
    def __init__(
        self,
        extractor: FeatureExtractor,
        online_store: Optional[OnlineFeatureStore] = None,
        offline_store: Optional[ParquetFeatureStore] = None,
    ) -> None: ...
    def enrich_deal(
        self,
        deal: PropertyDeal,
        cohort_deals: Optional[Sequence[PropertyDeal]] = None,
        cohort_name: str = "default_cohort",
    ) -> EnrichedFeatureContext: ...
```

#### `PipelineFeatureInterceptor`
Provides non-invasive hooks attaching to `DealPipeline` stage events to automatically extract, validate, and persist features into the feature store during live underwriting execution.

```python
class PipelineFeatureInterceptor:
    def __init__(
        self,
        extractor: FeatureExtractor,
        buffer: Optional[StreamFeatureBuffer] = None,
        online_store: Optional[OnlineFeatureStore] = None,
        offline_store: Optional[ParquetFeatureStore] = None,
    ) -> None: ...
    def attach_to_pipeline(self, pipeline: Any) -> None: ...
    def on_deal_started(self, deal: PropertyDeal) -> None: ...
    def on_stage_completed(self, stage_name: str, deal: PropertyDeal, context: Any) -> None: ...
    def on_deal_completed(self, deal: PropertyDeal, underwrite_result: Any) -> FeatureVector: ...
```

---

### 16.9 Master Subsystem Coordinator Facade (`autonomous_multi_agent_real.features.coordinator`)

Unified singleton/facade exposing all capabilities across the streaming, storage, serving, and quality subsystems through a clean API.

```python
class FeatureStoreCoordinator:
    def __init__(
        self,
        base_path: Union[str, Path],
        registry: Optional[FeatureRegistry] = None,
        partition_spec: Optional[ParquetPartitionSpec] = None,
        online_config: Optional[OnlineStoreConfig] = None,
        buffer_config: Optional[StreamBufferConfig] = None,
    ) -> None: ...

    def extract_and_persist(
        self, deal: PropertyDeal, context: Optional[Any] = None, sync_online: bool = True
    ) -> FeatureVector: ...
    def get_features(
        self,
        entity_id: str,
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
    ) -> Dict[str, Any]: ...
    def get_feature_vector(
        self, entity_id: str, entity_type: str = "deal", fallback_to_offline: bool = True
    ) -> Optional[FeatureVector]: ...
    def get_batch_features(
        self,
        entity_ids: Sequence[str],
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
    ) -> Dict[str, Dict[str, Any]]: ...
    def get_feature_matrix(
        self, entity_ids: Sequence[str], feature_names: Sequence[str], entity_type: str = "deal"
    ) -> Dict[str, List[Any]]: ...
    def enrich_deal(
        self,
        deal: PropertyDeal,
        cohort_deals: Optional[Sequence[PropertyDeal]] = None,
        cohort_name: str = "default_cohort",
    ) -> EnrichedFeatureContext: ...
    def materialize_to_online(
        self,
        start_time: Optional[Any] = None,
        end_time: Optional[Any] = None,
        entity_ids: Optional[Sequence[str]] = None,
    ) -> MaterializationJob: ...
    def flush_buffer(self) -> MaterializationJob: ...
    def backfill_deals(
        self, deals: Sequence[PropertyDeal], sync_online: bool = True
    ) -> MaterializationJob: ...
    def build_training_dataset(
        self,
        observations: Sequence[ObservationTarget],
        dataset_name: str,
        feature_names: Optional[Sequence[str]] = None,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> TrainingDataset: ...
    def audit_quality(self, entity_ids: Optional[Sequence[str]] = None) -> FeatureQualityReport: ...
    def audit_sync(self) -> Dict[str, Any]: ...
    def get_status(self) -> Dict[str, Any]: ...


def create_feature_store(base_path: Optional[Union[str, Path]] = None) -> FeatureStoreCoordinator:
    """Instantiate and initialize default coordinator rooted at base_path or .feature_store."""
```
