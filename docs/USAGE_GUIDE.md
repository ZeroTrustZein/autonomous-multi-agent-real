# Practical Usage Guide: Autonomous Real Estate Underwriting

This guide provides practical recipes, CLI commands, configuration templates, and Python integration walkthroughs for operating **`autonomous-multi-agent-real`** in production, deal analysis, and quantitative investment workflows.

---

## Table of Contents

1. [Recipe 1: Full Multi-Agent Underwriting via CLI](#recipe 1-full-multi-agent-underwriting-via-cli)
2. [Recipe 2: Vectorized Stochastic Risk Simulation (Monte Carlo & VaR)](#recipe-2-vectorized-stochastic-risk-simulation-monte-carlo--var)
3. [Recipe 3: Private Equity GP/LP Waterfall Structuring](#recipe-3-private-equity-gplp-waterfall-structuring)
4. [Recipe 4: Two-Dimensional Sensitivity & Breakeven Analysis](#recipe-4-two-dimensional-sensitivity--breakeven-analysis)
5. [Recipe 5: Tax Depreciation & Cost Segregation Modeling](#recipe-5-tax-depreciation--cost-segregation-modeling)
6. [Recipe 6: Reverse Pricing & Hurdle Goal-Seeking](#recipe-6-reverse-pricing--hurdle-goal-seeking)
7. [Recipe 7: Multi-Agent Deliberation & Institutional Policy Auditing](#recipe-7-multi-agent-deliberation--institutional-policy-auditing)
8. [Recipe 8: Multi-Asset Portfolio Consolidation & Macro Stress Testing](#recipe-8-multi-asset-portfolio-consolidation--macro-stress-testing)
9. [Recipe 9: Deal Repository Versioning, Revisions & Diffing](#recipe-9-deal-repository-versioning-revisions--diffing)
10. [Recipe 10: Interactive Terminal Command Center (REPL)](#recipe-10-interactive-terminal-command-center-repl)
11. [Recipe 11: Programmatic Python Pipeline Integration](#recipe-11-programmatic-python-pipeline-integration)
12. [Recipe 12: Real-Time Feature Ingestion & Online Feature Serving](#recipe-12-real-time-feature-ingestion--online-feature-serving)
13. [Recipe 13: Time-Travel Point-in-Time Joins & ML Training Datasets](#recipe-13-time-travel-point-in-time-joins--ml-training-datasets)
14. [Recipe 14: Feature Quality Auditing & Statistical Drift Detection](#recipe-14-feature-quality-auditing--statistical-drift-detection)
15. [Recipe 15: Feature Store CLI Management & Interactive Operations](#recipe-15-feature-store-cli-management--interactive-operations)

---

## Recipe 1: Full Multi-Agent Underwriting via CLI

To underwrite a benchmark or imported property deal, invoke the `underwrite` command:

```bash
# Underwrite the default benchmark Austin multifamily asset
autonomous-multi-agent-real underwrite --deal-id austin-multifamily
```

### Options & Flags:
* `--iterations`, `-i`: Number of Monte Carlo iterations (default: 1,000).
* `--seed`, `-s`: Random number generator seed for deterministic reproducibility (default: 42).
* `--memo-out`, `-m`: File path to automatically export the complete Markdown Investment Committee Underwriting Memorandum.
* `--export`, `-e`: File path to export full JSON results.

```bash
# Run with 5,000 Monte Carlo paths and export both memo and JSON dossier
autonomous-multi-agent-real underwrite \
  --deal-id austin-multifamily \
  --iterations 5000 \
  --memo-out ./reports/austin_memo.md \
  --export ./reports/austin_underwriting.json
```

---

## Recipe 2: Vectorized Stochastic Risk Simulation (Monte Carlo & VaR)

Stress-test returns and evaluate tail risks using correlated macro shocks:

```bash
# Run 2,500 stochastic iterations
autonomous-multi-agent-real simulate --deal-id austin-multifamily --iterations 2500
```

### Advanced Simulation Flags:
* `--seed`: Set random seed for audits.
* `--no-correlated-shocks`: Disable empirical cross-correlation (Cholesky matrix) to evaluate uncorrelated Gaussian distributions.

```bash
autonomous-multi-agent-real simulate \
  --deal-id austin-multifamily \
  --iterations 10000 \
  --seed 1337
```

**Key CLI Outputs Displayed:**
* Mean Levered IRR, Median (P50), P10 Downside, and P90 Upside
* Value at Risk (VaR 95% and VaR 99%)
* Conditional Value at Risk (CVaR 95% / Expected Shortfall)
* Probability of Negative Return ($\mathbb{P}(\text{IRR} < 0)$)
* Probability of Senior Debt DSCR Breach ($\mathbb{P}(\text{DSCR} < 1.0\text{x})$)
* Variance Attribution breakdown (Rent Growth vs. Vacancy vs. OpEx vs. Exit Cap)

---

## Recipe 3: Private Equity GP/LP Waterfall Structuring

Compute distributions, return of capital, preferred return accrual, and sponsor promote splits:

```bash
# Calculate default 4-tier waterfall (8% pref, 80/20 to 14%, 70/30 to 18%, 50/50 residual)
autonomous-multi-agent-real waterfall --deal-id austin-multifamily
```

### Custom Equity Structuring Options:
* `--pref`: Annual compounding preferred return hurdle (e.g., `0.09` for 9.0%).
* `--lp-share`: LP equity capitalization fraction (default: `0.90`).
* `--gp-share`: Sponsor co-investment equity fraction (default: `0.10`).

```bash
# Structure a 95/5 joint venture with 7.0% preferred return
autonomous-multi-agent-real waterfall \
  --deal-id austin-multifamily \
  --pref 0.07 \
  --lp-share 0.95 \
  --gp-share 0.05
```

---

## Recipe 4: Two-Dimensional Sensitivity & Breakeven Analysis

Evaluate portfolio vulnerability to terminal valuation and rent compression:

```bash
# Generate 5x5 sensitivity matrix & operational breakevens
autonomous-multi-agent-real sensitivity --deal-id austin-multifamily
```

### Custom Matrix Steps:
```bash
# High-resolution 7x7 parameter matrix
autonomous-multi-agent-real sensitivity --deal-id austin-multifamily --steps 7
```

**Metrics Provided:**
* 2D Return Grid: Exit Cap Rate vs. Annual Rent Growth
* Breakeven Physical Occupancy (e.g., $68.4\%$ vs. $95.0\%$ current)
* Breakeven Monthly In-Place Rent per Unit
* Downside Margin of Safety (Buffer in % before debt service deficit)
* Scenario Trio: Base Case vs. Bull Case (+100 bps rent, -50 bps cap) vs. Bear Case (-150 bps rent, +75 bps cap)

---

## Recipe 5: Tax Depreciation & Cost Segregation Modeling

Model tax depreciation shielding, capital gains liabilities, and after-tax return boosts:

```bash
# Standard straight-line MACRS depreciation (27.5-year residential)
autonomous-multi-agent-real tax --deal-id austin-multifamily
```

### Cost Segregation & Bonus Depreciation:
Enable accelerated 5-year personal property and 15-year land improvement carve-outs with 60% first-year bonus depreciation:

```bash
autonomous-multi-agent-real tax \
  --deal-id austin-multifamily \
  --cost-seg \
  --land-pct 0.15 \
  --tax-rate 0.37
```

---

## Recipe 6: Reverse Pricing & Hurdle Goal-Seeking

Determine the maximum purchase price supportable by investment hurdles:

```bash
# Solve for max acquisition price to achieve a 16.0% Levered IRR hurdle
autonomous-multi-agent-real optimize \
  --deal-id austin-multifamily \
  --target-irr 0.16 \
  --min-dscr 1.25 \
  --min-debt-yield 0.08
```

The optimizer performs bisection search across candidate purchase prices, dynamically resizing senior debt under LTV, DSCR, and Debt Yield constraints at each candidate price.

---

## Recipe 7: Multi-Agent Deliberation & Institutional Policy Auditing

### Audit Credit Policy Compliance:
```bash
autonomous-multi-agent-real audit --deal-id austin-multifamily
```

Audits the deal against:
* Maximum Senior LTV Covenant ($\le 80.0\%$)
* Target Senior LTV Guideline ($\le 75.0\%$)
* Minimum DSCR Covenant Floor ($\ge 1.15\text{x}$)
* Minimum Debt Yield ($\ge 7.0\%$)
* Minimum Sponsor Hurdle IRR ($\ge 10.0\%$)
* Minimum Capital Replacement Reserves ($\ge \$250/\text{unit}/\text{year}$)

### Inspect Swarm Deliberation & Challenges:
```bash
autonomous-multi-agent-real debate --deal-id austin-multifamily
```

Displays cross-agent challenges (e.g., Debt Agent questioning DSCR cushion, Market Agent contesting rent escalators) and resulting consensus resolutions.

---

## Recipe 8: Multi-Asset Portfolio Consolidation & Macro Stress Testing

Consolidate all deals in the repository into an integrated portfolio:

```bash
# Aggregate repository deals into consolidated portfolio rollup
autonomous-multi-agent-real portfolio
```

### Apply Macroeconomic Stress Scenarios:
```bash
autonomous-multi-agent-real portfolio --stress
```

Simulates the joint impact of three systemic macro shocks:
1. **Rate Spike Shock**: +150 bps debt refinancing rate, +50 bps exit cap expansion.
2. **Severe Recession**: -200 bps rent contraction, +500 bps vacancy spike, +75 bps exit cap decompression.
3. **Stagflation**: +200 bps operating expense inflation, 0% rent growth, +50 bps exit cap expansion.

---

## Recipe 9: Deal Repository Versioning, Revisions & Diffing

The repository tracks complete revision histories for underwriting assumptions:

### 1. Create a New Versioned Revision:
```bash
autonomous-multi-agent-real deal create-revision \
  --deal-id austin-multifamily \
  --author "senior_analyst" \
  --summary "Updated tax assessment and revised interest rate to 6.75%"
```

### 2. View Revision History:
```bash
autonomous-multi-agent-real deal revisions --deal-id austin-multifamily
```

### 3. Diff Parameters Across Revisions:
```bash
autonomous-multi-agent-real deal diff \
  --deal-id austin-multifamily \
  --rev1 1 \
  --rev2 2
```

### 4. Revert to a Previous Revision State:
```bash
autonomous-multi-agent-real deal revert \
  --deal-id austin-multifamily \
  --rev 1
```

---

## Recipe 10: Interactive Terminal Command Center (REPL)

Launch the interactive prompt environment for continuous exploration without repeated shell launches:

```bash
autonomous-multi-agent-real interactive
```

Inside the interactive shell:
```text
(deal-underwriter) help
(deal-underwriter) list
(deal-underwriter) show austin-multifamily
(deal-underwriter) underwrite austin-multifamily
(deal-underwriter) simulate austin-multifamily 2000
(deal-underwriter) waterfall austin-multifamily 0.08
(deal-underwriter) sensitivity austin-multifamily
(deal-underwriter) tax austin-multifamily
(deal-underwriter) optimize austin-multifamily 0.16
(deal-underwriter) debate austin-multifamily
(deal-underwriter) portfolio
(deal-underwriter) exit
```

---

## Recipe 11: Programmatic Python Pipeline Integration

Integrate `autonomous-multi-agent-real` directly into your proprietary data ingestion or investment pipelines:

```python
from autonomous_multi_agent_real.types import (
    PropertyDeal,
    PropertyType,
    UnitMixItem,
    OperatingExpenses,
    FinancingTerms,
)
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.reporting.memo import InvestmentMemoGenerator

# 1. Define Property Deal
deal = PropertyDeal(
    id="denver-flats-120",
    title="Denver Flats 120-Unit Multifamily",
    address="1850 Logan St, Denver, CO 80203",
    property_type=PropertyType.MULTI_FAMILY,
    gross_square_feet=96000.0,
    purchase_price=24000000.0,
    rehab_budget=500000.0,
    current_occupancy_pct=0.94,
    market_occupancy_pct=0.96,
    annual_rent_growth_pct=0.035,
    annual_expense_growth_pct=0.025,
    hold_period_years=5,
    exit_cap_rate=0.060,
    unit_mix=[
        UnitMixItem(
            unit_type="1BR/1BA",
            count=60,
            square_feet=650.0,
            current_rent=1650.0,
            market_rent=1850.0,
        ),
        UnitMixItem(
            unit_type="2BR/2BA",
            count=60,
            square_feet=950.0,
            current_rent=2100.0,
            market_rent=2350.0,
        ),
    ],
    expenses=OperatingExpenses(
        property_taxes=240000.0,
        insurance=95000.0,
        repairs_and_maintenance=110000.0,
        property_management_pct=0.07,
        utilities=45000.0,
        admin_and_legal=30000.0,
        replacement_reserves_per_unit=300.0,
    ),
    financing=FinancingTerms(
        purchase_price=24000000.0,
        down_payment_pct=0.25,
        interest_rate=0.0625,
        amortization_years=30,
        loan_term_years=10,
        interest_only_months=24,
    ),
)

# 2. Instantiate Pipeline & Execute
pipeline = DealPipeline(monte_carlo_iterations=2000, random_seed=42)
result = pipeline.run(deal)

# 3. Inspect Results
print(f"Verdict: {result.decision.value.upper()}")
print(f"Committee Score: {result.committee_score:.1f}/100")
print(f"Levered IRR: {result.deal_metrics.levered_irr:.1%}")
print(f"Equity Multiple: {result.deal_metrics.equity_multiple:.2f}x")
print(f"Senior Loan Amount: ${result.debt_sizing.loan_amount:,.0f}")
print(f"Monte Carlo VaR 95%: {result.monte_carlo.var_95_irr:.1%}")

# 4. Generate Investment Committee Memo
memo_gen = InvestmentMemoGenerator()
memo_text = memo_gen.generate_memo(deal, result, result.compliance_report)

with open("denver_flats_memo.md", "w", encoding="utf-8") as f:
    f.write(memo_text)
```
