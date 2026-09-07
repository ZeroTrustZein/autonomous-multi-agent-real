# System Architecture & Technical Deep-Dive

This document provides an exhaustive technical specification of the architecture, algorithmic formulations, multi-agent coordination protocols, and data models powering **`autonomous-multi-agent-real`**.

---

## 1. High-Level Architectural Vision

`autonomous-multi-agent-real` is an institutional-grade, multi-agent real estate underwriting and stochastic simulation platform. The system coordinates specialized AI underwriting agents arranged in an event-driven Directed Acyclic Graph (DAG), backed by pure Python/NumPy quantitative financial engines, an in-memory blackboard deliberation protocol, an institutional credit policy compliance engine, and a versioned audit repository.

```
                         [ Deal Ingestion / JSON Submission ]
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │       Acquisition & Screening Agent           │
                 │   - Intake validation & Unit mix aggregation  │
                 │   - Basis capitalization & Initial screening  │
                 └───────────────────────┬───────────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
         ┌─────────────────────────────┐   ┌─────────────────────────────┐
         │   Market Comps Agent        │   │   Debt Financing Agent      │
         │ - Rent comps & Mark-to-mkt  │   │ - Sizing across LTV/DSCR/DY │
         │ - Loss-to-lease computation │   │ - Multi-year amortization   │
         │ - Submarket cap rate delta  │   │ - Refinance & balloon risk  │
         └──────────────┬──────────────┘   └──────────────┬──────────────┘
                        └────────────────┬────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │          Cash Flow Simulation Agent           │
                 │   - Multi-year operating pro-forma (GPR->NOI) │
                 │   - Debt service subtraction -> BTCF          │
                 │   - Terminal reversion & net exit proceeds    │
                 │   - Levered / Unlevered IRR & Equity Multiple │
                 └───────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                       ▼                       ▼
   ┌───────────────────────────┐ ┌───────────────┐ ┌───────────────────────────┐
   │    Waterfall Engine       │ │  Tax Engine   │ │   Sensitivity Engine      │
   │ - Multi-tier GP/LP promote│ │ - MACRS 27.5/ │ │ - 2D matrix (Cap vs Rent) │
   │ - Preferred return hurdle │ │   39.0yr      │ │ - Breakeven occupancy/rent│
   │ - European/American style │ │ - Cost seg    │ │ - Base / Bull / Bear test │
   └─────────────┬─────────────┘ └───────┬───────┘ └─────────────┬─────────────┘
                 └───────────────────────┼───────────────────────┘
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │         Stochastic Risk & Monte Carlo         │
                 │   - Vectorized NumPy Cholesky shock matrix    │
                 │   - Correlated variables: rent/vac/opex/exit  │
                 │   - Parametric VaR (95/99) & CVaR (Expected)  │
                 │   - Variance attribution & downside quantile  │
                 └───────────────────────┬───────────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
         ┌─────────────────────────────┐   ┌─────────────────────────────┐
         │ Multi-Agent Deliberation    │   │ Institutional Policy Audit  │
         │ - Cross-agent challenges    │   │ - Hard limits (Covenants)   │
         │ - Assumption contestation   │   │ - Soft guidelines (Warning) │
         │ - Concession / Rebuttal     │   │ - Remediation action paths  │
         └──────────────┬──────────────┘   └──────────────┬──────────────┘
                        └────────────────┬────────────────┘
                                         │
                                         ▼
                 ┌───────────────────────────────────────────────┐
                 │       Investment Committee Synthesis          │
                 │   - Multi-dimensional weighted scoring (0-100)│
                 │   - Verdict: APPROVED / CONDITIONAL / REJECTED│
                 │   - Core thesis & risk mitigation synthesis   │
                 │   - Publication-ready IC Underwriting Memo    │
                 └───────────────────────────────────────────────┘
```

---

## 2. Core Subsystems & Components

### 2.1 Domain Models & Type System (`types.py`)

The type system is strictly structured via **Pydantic v2**, ensuring runtime schema validation, serialization, and immutability guarantees:

* **`PropertyType`**: Enum classifying real estate assets (`single_family`, `multi_family`, `commercial`, `industrial`, `mixed_use`).
* **`UnitMixItem`**: Unit inventory definition including unit count, average square footage, in-place contract rent, and market rent. Exposes methods for `loss_to_lease()` and aggregate rent.
* **`OperatingExpenses`**: Granular expense itemization covering property taxes, insurance, repairs & maintenance, utilities, administrative & legal, replacement reserves per unit, and variable management fee (percentage of Effective Gross Income).
* **`FinancingTerms`**: Capital markets assumptions including loan-to-cost/down payment fraction, nominal interest rate, amortization schedule length, loan term/balloon, interest-only period, and acquisition closing cost percentages.
* **`PropertyDeal`**: Master model encapsulating physical property specifications, unit mix, purchase basis, capital expenditure / rehab budget, current & market occupancy rates, rent/expense growth escalators, hold period, terminal exit cap rate, expense schedule, and financing assumptions.
* **`UnderwritingResult`**: Consolidated dossier combining deal metrics, debt sizing, pro-forma cash flows, Monte Carlo simulation statistics, individual agent analytical reports, GP/LP waterfall ledgers, sensitivity matrices, tax depreciation schedules, pricing optimization, compliance audit report, and committee debate transcript.

---

### 2.2 Orchestration Engine & Execution DAG (`engine/workflow.py`, `engine/state.py`)

The underwriting pipeline is managed by `DealPipeline`, which executes a sequential, event-driven DAG through `DealWorkflowContext`:

```
 Stage 1: INTAKE ──► Stage 2: MARKET_ANALYSIS ──► Stage 3: DEBT_SIZING
                                                        │
                                                        ▼
 Stage 5: RISK_MODELING ◄── [Core Engines] ◄── Stage 4: CASH_FLOW_SIMULATION
           │             (Waterfall, Tax,
           │              Sensitivity, Opt)
           ▼
 Deliberation & Policy Audit ──► Stage 6: COMMITTEE_SYNTHESIS ──► COMPLETED
```

#### Workflow State Machine (`DealWorkflowContext`):
1. **Facts Store**: Global dictionary of validated deal metrics populated progressively by agents.
2. **Agent Reports Store**: Map of `AgentRole -> AgentAnalysisReport`.
3. **Artifact Registry**: Storage for `DebtSizingResult`, `AnnualCashFlow` list, `WaterfallResult`, `SensitivityMatrix`, `TaxAnalysisResult`, and `PricingOptimizationResult`.
4. **Audit Trail**: Append-only log of timestamped workflow events and execution durations.

Both synchronous execution (`run()`) and asynchronous execution (`run_async()`) are supported natively.

---

### 2.3 Pure Financial Mathematics Engine (`engine/financial.py`)

The financial engine implements deterministic, closed-form financial equations with robust numerical fallback routines.

#### Mortgage Payment Calculation:
For principal $P$, monthly interest rate $r = \frac{i}{12}$, and total payment months $n = 12 \times \text{years}$:

$$M = P \cdot \frac{r(1 + r)^n}{(1 + r)^n - 1}$$

If $r = 0$, $M = \frac{P}{n}$.

#### Loan Amortization Schedule:
Simulates monthly compounding over the holding period $H$ years:
* Months $m \le \text{interest\_only\_months}$:
  $$\text{Interest}_m = \text{Balance}_{m-1} \cdot r, \quad \text{Principal}_m = 0$$
* Months $m > \text{interest\_only\_months}$:
  $$\text{Interest}_m = \text{Balance}_{m-1} \cdot r, \quad \text{Principal}_m = M - \text{Interest}_m$$
  $$\text{Balance}_m = \max(0, \text{Balance}_{m-1} - \text{Principal}_m)$$

#### Net Present Value (NPV):
$$\text{NPV}(k, \mathbf{C}) = \sum_{t=0}^T \frac{C_t}{(1 + k)^t}$$

#### Internal Rate of Return (IRR) Solver:
IRR satisfies $\text{NPV}(\text{IRR}, \mathbf{C}) = 0$. The solver implements a hybrid **Newton-Raphson** algorithm with numerical first-derivative calculations:

$$r_{k+1} = r_k - \frac{\text{NPV}(r_k)}{\text{NPV}'(r_k)}, \quad \text{where } \text{NPV}'(r) = -\sum_{t=1}^T \frac{t \cdot C_t}{(1 + r)^{t+1}}$$

If Newton-Raphson diverges outside valid economic bounds ($r < -99\%$ or $r > 1000\%$) or encounters a near-zero derivative, the engine automatically falls back to **Bisection Root Finding** over $[-0.95, 5.00]$, guaranteeing convergence.

#### Key Real Estate Performance Ratios:
* **Debt Service Coverage Ratio (DSCR)**:
  $$\text{DSCR}_t = \frac{\text{NOI}_t}{\text{Annual Debt Service}_t}$$
* **Debt Yield**:
  $$\text{Debt Yield} = \frac{\text{NOI}_1}{\text{Loan Amount}}$$
* **Loan-to-Value (LTV)**:
  $$\text{LTV} = \frac{\text{Loan Amount}}{\text{Purchase Price}}$$
* **Capitalization Rate (Cap Rate)**:
  $$\text{Cap Rate} = \frac{\text{NOI}}{\text{Property Value}}$$
* **Equity Multiple (EM)**:
  $$\text{EM} = \frac{\sum_{t=1}^T \text{Distributions}_t}{\text{Initial Equity Invested}}$$

---

### 2.4 Vectorized Monte Carlo Simulation Engine (`engine/monte_carlo.py`)

Risk modeling uses high-speed vectorized operations in NumPy to simulate multi-thousand path iterations across macroeconomic and asset-level uncertainties.

#### Correlated Shock Matrix via Cholesky Decomposition:
Real estate risks are co-dependent (e.g., higher vacancy frequently coincides with depressed rent growth and expanding cap rates). The engine establishes an empirical correlation matrix $\mathbf{\Sigma}$:

$$\mathbf{\Sigma} = \begin{pmatrix} 1.00 & -0.45 & 0.30 & -0.35 \\ -0.45 & 1.00 & -0.10 & 0.25 \\ 0.30 & -0.10 & 1.00 & 0.10 \\ -0.35 & 0.25 & 0.10 & 1.00 \end{pmatrix}$$

Variables: $[g_{\text{rent}}, v_{\text{vacancy}}, g_{\text{opex}}, c_{\text{exit}}]$.

The lower triangular Cholesky factor $\mathbf{L}$ where $\mathbf{\Sigma} = \mathbf{L}\mathbf{L}^T$ transforms uncorrelated standard normal vectors $\mathbf{Z} \sim \mathcal{N}(0, \mathbf{I})$ into correlated random vectors:

$$\mathbf{X} = \mathbf{\mu} + \mathbf{L} \mathbf{Z} \cdot \mathbf{\sigma}$$

```
 Uncorrelated Variates Z ~ N(0, I) ──► [Cholesky Transformation L] ──► Correlated Macro Shocks
                                                                              │
 ┌────────────────────────────────────────────────────────────────────────────┘
 ▼
 Iteration Paths (e.g. N=2,000)
 ├── Dynamic GPR & Vacancy Paths ──► Effective Gross Income (EGI)
 ├── Dynamic Expense Inflation   ──► Net Operating Income (NOI)
 ├── Debt Service Subtraction    ──► Before-Tax Cash Flow (BTCF)
 └── Correlated Exit Cap Rate    ──► Terminal Sale Proceeds & Payoff
                                              │
                                              ▼
 Vectorized IRR Solver / Quantiles ──► P10 / P50 / P90 Returns & VaR / CVaR
```

#### Tail-Risk Metrics:
* **Value at Risk (VaR)**:
  $$\text{VaR}_\alpha(\text{IRR}) = \text{Quantile}_{1-\alpha}(\mathbf{r})$$
  Evaluates 95% and 99% downside thresholds.
* **Conditional Value at Risk (CVaR / Expected Shortfall)**:
  $$\text{CVaR}_\alpha(\text{IRR}) = \mathbb{E}\left[ r \mid r \le \text{VaR}_\alpha(r) \right]$$
  Computes the expected return conditional on breaching the VaR threshold.
* **Variance Attribution**: Decomposes total IRR variance into percentage contributions from rent growth, vacancy, operating expenses, and exit cap rate via partial variance regression.

---

### 2.5 GP/LP Private Equity Distribution Waterfall Engine (`engine/waterfall.py`)

The waterfall engine computes equity cash distributions, compounding preferred return hurdles, and sponsor promote splits between Limited Partners (LP) and General Partners (GP).

#### Distribution Mechanics:
1. **Tier 1 — Return of Capital & Preferred Return**:
   - Cash flows first pay down unreturned equity capital pro-rata to LP ($90\%$) and GP ($10\%$).
   - Concurrently accrues compounding preferred return (default $8.0\%$ per annum) on unreturned capital.
2. **Tier 2 — First Promote Tier**:
   - Above 8.0% IRR up to 14.0% IRR: Distributions split 80% LP / 20% GP promote.
3. **Tier 3 — Second Promote Tier**:
   - Above 14.0% IRR up to 18.0% IRR: Distributions split 70% LP / 30% GP promote.
4. **Tier 4 — Residual Promote**:
   - Above 18.0% IRR: Distributions split 50% LP / 50% GP promote.

Computes separate LP IRR, LP Equity Multiple, GP IRR (boosted by promote), GP Equity Multiple, and total dollar sponsor promote generated.

---

### 2.6 Multi-Variable Sensitivity & Breakeven Engine (`engine/sensitivity.py`)

#### 2D Stress Matrix:
Constructs an $N \times M$ grid evaluating levered IRR, equity multiple, and minimum DSCR across independent parameter axes:
* Default matrix: **Exit Cap Rate** ($[\text{exit}-1.0\%, \dots, \text{exit}+1.0\%]$ in 5 steps) versus **Rent Growth** ($[\text{rent}-2.0\%, \dots, \text{rent}+2.0\%]$ in 5 steps).
* Fully configurable to custom parameters (e.g. interest rate vs. initial purchase price).

#### Downside Breakeven Metrics:
* **Breakeven Occupancy**: The minimum occupancy level where Net Operating Income exactly covers annual debt service:
  $$\text{Occ}_{\text{be}} = \frac{\text{Operating Expenses} + \text{Annual Debt Service}}{\text{Gross Potential Rent}}$$
* **Breakeven Rent**: Minimum monthly rent per unit required to maintain a DSCR of 1.0x:
  $$\text{Rent}_{\text{be}} = \frac{\text{Fixed Expenses} + \text{Debt Service}}{12 \times \text{Units} \times \text{Occupancy} \times (1 - \text{Management Fee Pct})}$$
* **Margin of Safety**: Percentage buffer between base underwritten assumptions and breakeven thresholds.

---

### 2.7 Tax Depreciation & Cost Segregation Engine (`engine/tax.py`)

Simulates U.S. Federal Income Tax treatment for commercial and residential real estate assets:
* **Depreciable Basis**: Total acquisition basis minus allocated land value (default 20% non-depreciable land).
* **Recovery Periods (MACRS Straight-Line)**:
  - Multifamily residential: $27.5$ years ($3.636\%$ annual depreciation).
  - Commercial / Industrial: $39.0$ years ($2.564\%$ annual depreciation).
* **Cost Segregation Option**:
  - Reallocates basis into 5-year personal property (e.g. 12%) and 15-year land improvements (e.g. 8%).
  - Applies 60% bonus depreciation under Section 168(k) in Year 1.
* **Exit Tax Liabilities**:
  - **Section 1250 Depreciation Recapture**: Taxed at $25.0\%$ on accumulated depreciation claimed.
  - **Capital Gains Tax**: Taxed at $20.0\%$ on net price appreciation above original basis.
* **After-Tax Returns**: Generates after-tax cash flows and recalculates After-Tax IRR and After-Tax Equity Multiple.

---

### 2.8 Reverse Pricing & Hurdle Optimization Solver (`engine/optimizer.py`)

Provides inverse financial engineering capabilities:
* **`solve_max_offer_price`**: Uses bisection search to determine the maximum purchase price a sponsor can pay while still satisfying:
  1. Minimum Levered IRR hurdle (e.g. $\ge 15.0\%$).
  2. Senior lender minimum DSCR covenant (e.g. $\ge 1.25\text{x}$).
  3. Minimum Debt Yield threshold (e.g. $\ge 8.0\%$).
  Dynamically resizes senior debt at each candidate price point.
* **`solve_required_monthly_rent`**: Computes the minimum average unit rent needed to achieve a target return on a fixed acquisition basis.

---

### 2.9 Multi-Agent Swarm Collaboration & Deliberation Protocol (`collaboration/`)

Agents communicate through a decoupled **Message Bus** and shared **Blackboard Architecture**:

```
 ┌────────────────────────────────────────────────────────┐
 │                     MessageBus                         │
 │  Publish / Subscribe Pattern with Wildcard Routing     │
 └───────────▲────────────────────────────────▲───────────┘
             │                                │
 ┌───────────▼───────────┐        ┌───────────▼───────────┐
 │   Acquisition Agent   │        │   Debt Sizing Agent   │
 └───────────┬───────────┘        └───────────┬───────────┘
             │                                │
             ▼                                ▼
 ┌────────────────────────────────────────────────────────┐
 │                  Shared Blackboard                     │
 │  Facts (Thread-safe dict) | Flags | Assumption Locks   │
 └────────────────────────────────────────────────────────┘
```

#### Deliberation & Cross-Agent Challenge Protocol (`DeliberationEngine`):
When agents generate conflicting underwriting assumptions, the system executes structured deliberation:
1. **Challenge Generation**: Agents audit peer metrics against their domain heuristics. For example:
   - *Risk Agent* challenges *Acquisition Agent* if exit cap rate compression is modeled during high interest rate regimes.
   - *Debt Agent* challenges *Cash Flow Agent* if Year 1 DSCR is within 5 bps of the lender covenant floor.
   - *Market Agent* challenges *Cash Flow Agent* if projected rent growth exceeds submarket historical averages by >100 bps.
2. **Debate Rounds & Rebuttal**: The targeted agent must either issue a reasoned rebuttal with supporting evidence or concede the point and adjust the metric.
3. **Consensus Outcome**: Produces a structured transcript and composite alignment score passed directly to the Investment Committee.

---

### 2.10 Institutional Rule Engine & Credit Policy Audit (`rules/`)

Validates opportunities against strict institutional credit covenants and guidelines:
* **Hard Limits (`RuleSeverity.ERROR`)**: Non-negotiable covenants (e.g., Senior LTV $\le 80\%$, Year 1 DSCR $\ge 1.15\text{x}$, Debt Yield $\ge 7.0\%$, Minimum Levered IRR $\ge 10.0\%$). Breaches trigger automatic deal rejection or mandatory structuring remediation.
* **Soft Guidelines (`RuleSeverity.WARNING`)**: Operational targets (e.g., Target LTV $\le 75\%$, Target DSCR $\ge 1.25\text{x}$, Replacement Reserves $\ge \$250/\text{unit}/\text{year}$, Maximum Basis per Unit $\le \$350,000$). Breaches require formal IC commentary and risk mitigants.
* **Remediation Directives**: Each rule specifies concrete corrective actions (e.g., "Increase LP equity injection by $\$450,000$ to restore DSCR to $1.25\text{x}$").

---

### 2.11 Multi-Asset Portfolio Consolidation & Macro Stress Engine (`portfolio/`)

Aggregates multiple individual property underwritings into a cohesive portfolio:
* **Rollup Metrics**: Total capitalization, aggregate unit count, weighted average LTV, weighted average DSCR, and aggregate multi-year cash flow stream.
* **Consolidated Portfolio IRR & Equity Multiple**: Solves portfolio-level cash flow returns across all assets simultaneously.
* **Diversification Breakdown**: Computes asset-class concentration percentages and geographic exposure.
* **Macroeconomic Stress Testing (`PortfolioStressEngine`)**: Evaluates portfolio vulnerability against systemic macro shocks:
  - *Rate Spike Scenario*: +150 bps debt financing rate, +50 bps exit cap expansion.
  - *Severe Recession Scenario*: -200 bps rent growth, +500 bps vacancy spike, +75 bps exit cap expansion.
  - *Stagflation Scenario*: +200 bps expense inflation, 0% rent growth, +50 bps exit cap expansion.

---

### 2.12 Audit Trail, Revision Control & Persistence (`storage/repository.py`)

* **Repository Architecture**: High-speed filesystem-backed JSON repository storing deals, underwriting runs, and portfolio models.
* **Versioned Revisions**:
  - Every assumption update creates a discrete, immutable snapshot with author metadata, timestamp, and change description.
  - Parameter diffing computes exact numerical variances between revision numbers.
  - Rollback engine enables instantaneous reversion to any prior assumption baseline.

---

## 3. Data Flow & Execution Sequence

The end-to-end execution of a deal follows this deterministic sequence:

```
[User Deal Submission]
         │
         ▼
 1. DealRepository.save_deal()
         │
         ▼
 2. DealPipeline.run(deal)
         │
         ├── Stage 1: AcquisitionAgent.analyze() ──► Unit Mix Aggregation & Basis Sizing
         │
         ├── Stage 2: MarketCompsAgent.analyze() ──► Loss-to-Lease & Rent Comps Benchmarking
         │
         ├── Stage 3: DebtAgent.analyze() ────────► Multi-Constraint Debt Sizing (LTV/DSCR/DY)
         │
         ├── Stage 4: CashFlowAgent.analyze() ────► Pro-Forma Projection (GPR -> EGI -> NOI -> BTCF)
         │       │
         │       ├── WaterfallEngine.calculate() ──► GP/LP Promote & Hurdle Distributions
         │       ├── SensitivityEngine.matrix() ──► 2D Cap vs. Rent Grid & Breakeven Analysis
         │       ├── TaxEngine.analyze() ─────────► MACRS Depreciation & After-Tax Returns
         │       └── DealOptimizer.solve() ───────► Max Supportable Acquisition Price
         │
         ├── Stage 5: RiskMonteCarloAgent.run() ──► 2,000+ Correlated NumPy Stochastic Paths
         │
         ├── Stage 6: DeliberationEngine.debate() ─► Cross-Agent Challenge Rounds & Transcript
         │
         ├── Stage 7: RuleEngine.evaluate() ──────► Institutional Credit Policy Covenant Audit
         │
         └── Stage 8: InvestmentCommitteeAgent ──► Final Synthesis, 0-100 Score & Verdict
                         │
                         ▼
             [ UnderwritingResult Dossier ]
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
[ Rich CLI View ] [ Markdown Memo ] [ CSV/JSON Exporter ]
```

---

## 4. Design Principles & Extensibility

1. **Pure Separation of Concerns**: Quantitative math (`engine/financial.py`) is decoupled from agent decision logic (`agents/`), which is decoupled from reporting (`reporting/`) and presentation (`cli/`).
2. **Zero Hallucination in Math**: All financial returns, debt schedules, taxes, and Monte Carlo paths are calculated deterministically via tested numerical code, never generated via probabilistic LLM token completion.
3. **Immutability & Auditability**: Every underwriting run records complete provenance, agent confidence scores, risk flags, and parameter revisions.
4. **Strict Typing**: All models enforce Pydantic v2 schemas with bounds checking and type safety.
