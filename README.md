# Autonomous Multi-Agent Real Estate Deal Underwriting & Cash Flow Simulation Engine

[![CI](https://github.com/ZeroTrustZein/autonomous-multi-agent-real/actions/workflows/ci.yml/badge.svg)](https://github.com/ZeroTrustZein/autonomous-multi-agent-real/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)

An institutional-grade, multi-agent real estate underwriting and stochastic simulation platform. Built in pure Python with **Pydantic v2**, high-speed **NumPy** vectorized Monte Carlo simulations, an event-driven agent orchestration pipeline, cross-agent deliberation protocols, private equity distribution waterfalls, and automated credit policy compliance auditing.

---

## System Architecture

The engine coordinates specialized underwriting agents arranged in an orchestrated execution Directed Acyclic Graph (DAG):

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

## Key Features

### 1. Specialized Swarm Agents
* **Acquisition Agent**: Unit mix analysis, price per unit/sqft, initial yield screening, and upfront rehab basis capitalization.
* **Market Comps Agent**: In-place vs. market rent variance, loss-to-lease mark-to-market upside, and submarket cap rate spreads.
* **Debt Financing Agent**: Simultaneous debt sizing against maximum LTV, minimum DSCR, and minimum Debt Yield constraints; identifies binding constraint.
* **Cash Flow Simulation Agent**: Multi-year pro-forma cash flow projection, debt service deductions, terminal valuation, and baseline IRR/EM calculations.
* **Risk & Monte Carlo Agent**: Vectorized stochastic risk analysis, parametric VaR/CVaR, and downside probability assessments.
* **Investment Committee Agent**: Multi-factor scoring (0–100), automated covenant penalties, and authoritative investment verdict (`APPROVED`, `CONDITIONAL`, `REJECTED`).

### 2. High-Precision Financial Engineering Core
* **Hybrid Newton-Raphson & Bisection IRR Solver**: Guaranteed mathematical convergence for non-linear multi-year cash flow sequences.
* **Vectorized Monte Carlo (NumPy)**: Evaluates thousands of paths in seconds with an empirical **Cholesky correlation matrix** coupling rent growth, vacancy, expense inflation, and exit cap rate shifts.
* **Private Equity GP/LP Waterfall Engine**: Multi-tier distribution modeling with compounding preferred returns and customizable promote hurdles (80/20, 70/30, 50/50).
* **2D Sensitivity & Breakeven Analysis**: High-resolution parameter matrices (Cap Rate vs. Rent Growth) and operational breakeven metrics (occupancy & rent margins of safety).
* **Tax Depreciation & Cost Segregation Engine**: MACRS 27.5-year residential and 39-year commercial schedules, Section 1250 depreciation recapture (25%), capital gains (20%), and 60% bonus depreciation under cost segregation.
* **Reverse Pricing & Hurdle Optimizer**: Bisection goal-seek solver identifying the maximum acquisition price that satisfies a target levered IRR while respecting lender debt constraints.

### 3. Deliberation, Governance & Portfolio
* **Deliberation Protocol**: Cross-agent challenges, assumption contestation, and rebuttal rounds using an in-memory MessageBus and Blackboard.
* **Institutional Credit Policy Engine**: Automatic audit against institutional covenants (hard stops) and guidelines (warnings) with actionable remediation steps.
* **Multi-Asset Portfolio Consolidation**: Capital-weighted aggregation, portfolio-level IRR/EM solving, diversification analysis, and macro stress testing (Rate Spikes, Severe Recessions, Stagflation).
* **Versioned Deal Repository**: Snapshot auditing, parameter diffing across revision numbers, and rollback support.
* **Terminal CLI & Interactive REPL**: Rich terminal interface with interactive exploration mode, tables, panels, and Markdown/JSON/CSV exports.

---

## Installation

### Prerequisites
* Python 3.10, 3.11, 3.12, 3.13, or 3.14
* Recommended: Virtual environment (`venv` or `conda`)

```bash
# Clone the repository
git clone https://github.com/ZeroTrustZein/autonomous-multi-agent-real.git
cd autonomous-multi-agent-real

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in editable development mode
pip install -e .

# Install development & test dependencies
pip install -e ".[dev]"
```

---

## Quickstart

### 1. Command-Line Interface (CLI)

```bash
# List all deals in the repository
autonomous-multi-agent-real list

# Inspect deal parameters
autonomous-multi-agent-real show --deal-id austin-multifamily

# Run complete multi-agent underwriting workflow
autonomous-multi-agent-real underwrite --deal-id austin-multifamily

# Run 2,000-path Monte Carlo risk simulation
autonomous-multi-agent-real simulate --deal-id austin-multifamily --iterations 2000

# Compute GP/LP waterfall distributions
autonomous-multi-agent-real waterfall --deal-id austin-multifamily --pref 0.08

# Generate 2D sensitivity matrix & breakeven safety analysis
autonomous-multi-agent-real sensitivity --deal-id austin-multifamily

# Launch interactive terminal command center (REPL)
autonomous-multi-agent-real interactive
```

### 2. Programmatic Python API

```python
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.storage.repository import DealRepository
from autonomous_multi_agent_real.reporting.memo import InvestmentMemoGenerator

# 1. Retrieve deal from repository
repo = DealRepository()
deal = repo.get_deal("austin-multifamily")

# 2. Run the underwriting pipeline
pipeline = DealPipeline(monte_carlo_iterations=2000, random_seed=42)
result = pipeline.run(deal)

# 3. Access verified underwriting metrics
print(f"Deal Title:        {result.deal_title}")
print(f"Decision:          {result.decision.value.upper()}")
print(f"Committee Score:   {result.committee_score:.1f}/100")
print(f"Levered IRR:       {result.deal_metrics.levered_irr:.1%}")
print(f"Equity Multiple:   {result.deal_metrics.equity_multiple:.2f}x")
print(
    f"Senior Debt Sized: ${result.debt_sizing.loan_amount:,.0f} ({result.debt_sizing.binding_constraint})"
)
print(f"Monte Carlo P50:   {result.monte_carlo.p50_irr:.1%}")
print(f"Tail VaR (95%):    {result.monte_carlo.var_95_irr:.1%}")

# 4. Generate Markdown Investment Committee Memo
memo = InvestmentMemoGenerator().generate_memo(deal, result, result.compliance_report)
print(f"Generated Underwriting Memo ({len(memo)} characters)")
```

---

## CLI Command Reference

| Command | Description | Example Usage |
| :--- | :--- | :--- |
| `list` | Query and filter deals in repository | `autonomous-multi-agent-real list -t multi_family --min-units 50` |
| `show` | Display deal assumptions & unit mix | `autonomous-multi-agent-real show -d austin-multifamily` |
| `underwrite` | Run full 8-stage underwriting DAG | `autonomous-multi-agent-real underwrite -d austin-multifamily -i 2000 -m memo.md` |
| `simulate` | Run Monte Carlo risk simulation | `autonomous-multi-agent-real simulate -d austin-multifamily -i 5000` |
| `quick` | Underwrite with inline CLI parameters | `autonomous-multi-agent-real quick -p 15000000 -u 80 -r 1800 -t multi_family` |
| `waterfall` | Calculate GP/LP equity waterfall | `autonomous-multi-agent-real waterfall -d austin-multifamily --pref 0.08` |
| `sensitivity`| 2D stress matrix & breakeven analysis | `autonomous-multi-agent-real sensitivity -d austin-multifamily --steps 5` |
| `tax` | MACRS depreciation & tax shielding | `autonomous-multi-agent-real tax -d austin-multifamily --cost-seg` |
| `optimize` | Solve maximum offer price for hurdle | `autonomous-multi-agent-real optimize -d austin-multifamily --target-irr 0.16` |
| `audit` | Check institutional credit policies | `autonomous-multi-agent-real audit -d austin-multifamily` |
| `debate` | Run swarm deliberation & challenges | `autonomous-multi-agent-real debate -d austin-multifamily` |
| `portfolio` | Multi-asset consolidation & stress | `autonomous-multi-agent-real portfolio --stress` |
| `memo` | Export Markdown IC Underwriting Memo | `autonomous-multi-agent-real memo -d austin-multifamily -o memo.md` |
| `export` | Export dossier to CSV or JSON | `autonomous-multi-agent-real export -d austin-multifamily -f json -o out.json` |
| `deal` | Repository revisions, diffs & rollback | `autonomous-multi-agent-real deal diff -d austin-multifamily -r1 1 -r2 2` |
| `interactive` | Launch interactive terminal shell | `autonomous-multi-agent-real interactive` |

---

## Comprehensive Documentation

Deep-dive documentation guides are available in the [`docs/`](./docs) directory:

* 📐 **[System Architecture & Technical Deep-Dive](docs/ARCHITECTURE.md)**: Detailed specifications of the execution DAG, state machine lifecycle, pure financial formulas, Cholesky correlation matrix, deliberation blackboard protocols, and portfolio rollup mechanics.
* 📚 **[Complete API Reference](docs/API_REFERENCE.md)**: Exhaustive reference covering all classes, methods, data models, functions, exceptions, and CLI commands.
* 🛠️ **[Practical Usage Guide](docs/USAGE_GUIDE.md)**: Step-by-step recipes covering full CLI workflows, Monte Carlo risk modeling, private equity waterfall structuring, tax modeling, reverse pricing, and programmatic Python integration.

---

## Testing & Quality Assurance

The codebase is backed by a comprehensive automated test suite with **100% test pass rate** and **96% statement coverage**:

```bash
# Run test suite with coverage
python -m pytest --cov=src/autonomous_multi_agent_real --cov-report=term-missing

# Run Ruff linter and code style checks
python -m ruff check .

# Run Mypy static type checker
python -m mypy src/autonomous_multi_agent_real
```

**Quality Metrics:**
* **90 Passing Tests** covering edge cases, core engines, integration pipelines, CLI commands, and interactive shell.
* **96% Code Coverage** across 3,100+ statements.
* **Zero Ruff warnings / Zero Mypy type issues** in strict type mode.

---

## Contributing & License

Distributed under the **MIT License**. Contributions, bug reports, and enhancements are welcome via GitHub Pull Requests.
