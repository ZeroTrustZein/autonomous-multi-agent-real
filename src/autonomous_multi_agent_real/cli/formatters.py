"""Rich visual console rendering formatters for autonomous multi-agent underwriting CLI."""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autonomous_multi_agent_real.collaboration.debate import DebateTranscript
from autonomous_multi_agent_real.portfolio.models import (
    PortfolioRiskProfile,
    PortfolioRollup,
)
from autonomous_multi_agent_real.rules.models import ComplianceReport
from autonomous_multi_agent_real.storage.repository import DealRevision
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AnnualCashFlow,
    BreakevenMetrics,
    DealMetrics,
    DebtSizingResult,
    InvestmentDecision,
    MonteCarloSimulationResult,
    PricingOptimizationResult,
    PropertyDeal,
    SensitivityMatrix,
    TaxAnalysisResult,
    UnderwritingResult,
    WaterfallResult,
)


def render_deals_table(deals: List[PropertyDeal], console: Console) -> None:
    """Render a formatted table listing available property deals."""
    table = Table(
        title="Available Real Estate Underwriting Deals",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Type", style="green")
    table.add_column("Units", justify="right")
    table.add_column("SqFt", justify="right")
    table.add_column("Purchase Price", justify="right", style="bold yellow")
    table.add_column("Monthly Rent", justify="right")
    table.add_column("Occ %", justify="right")

    for d in deals:
        table.add_row(
            d.id,
            d.title,
            d.property_type.value,
            str(d.total_units),
            f"{d.gross_square_feet:,.0f}",
            f"${d.purchase_price:,.0f}",
            f"${d.total_current_monthly_rent:,.0f}",
            f"{d.current_occupancy_pct:.1%}",
        )

    console.print(table)


def render_deal_detail(deal: PropertyDeal, console: Console) -> None:
    """Render detailed profile and assumptions for a specific property deal."""
    info_text = (
        f"[bold]ID:[/bold] {deal.id}  |  [bold]Type:[/bold] {deal.property_type.value.upper()}  |  "
        f"[bold]Units:[/bold] {deal.total_units}  |  [bold]Gross SqFt:[/bold] {deal.gross_square_feet:,.0f}\n"
        f"[bold]Purchase Price:[/bold] ${deal.purchase_price:,.0f}  |  "
        f"[bold]Rehab Budget:[/bold] ${deal.rehab_budget:,.0f}  |  "
        f"[bold]Total Acquisition Basis:[/bold] ${deal.total_acquisition_basis:,.0f}\n"
        f"[bold]Occupancy:[/bold] Current {deal.current_occupancy_pct:.1%} / Market {deal.market_occupancy_pct:.1%}  |  "
        f"[bold]Annual Growth:[/bold] Rent {deal.annual_rent_growth_pct:.1%} / OpEx {deal.annual_expense_growth_pct:.1%}\n"
        f"[bold]Hold Period:[/bold] {deal.hold_period_years} Years  |  "
        f"[bold]Exit Cap Rate:[/bold] {deal.exit_cap_rate:.2%}  |  "
        f"[bold]Selling Costs:[/bold] {deal.selling_costs_pct:.1%}"
    )
    console.print(Panel(info_text, title=f"Property Deal: {deal.title} ({deal.address})", border_style="cyan"))

    # Unit Mix Table
    if deal.unit_mix:
        um_table = Table(title="Unit Mix Breakdown", show_header=True, header_style="bold blue")
        um_table.add_column("Unit Type", style="cyan")
        um_table.add_column("Count", justify="right")
        um_table.add_column("Avg SqFt", justify="right")
        um_table.add_column("In-Place Rent", justify="right")
        um_table.add_column("Market Rent", justify="right")
        um_table.add_column("Total Monthly Rent", justify="right", style="bold yellow")
        um_table.add_column("Loss-to-Lease", justify="right", style="magenta")

        for item in deal.unit_mix:
            ltl = item.loss_to_lease()
            cur_rent = item.total_monthly_current_rent()
            um_table.add_row(
                item.unit_type,
                str(item.count),
                f"{item.square_feet:,.0f}",
                f"${item.current_rent:,.0f}",
                f"${item.market_rent:,.0f}",
                f"${cur_rent:,.0f}",
                f"${ltl:,.0f}",
            )
        console.print(um_table)

    # Operating Expenses Table
    exp = deal.expenses
    exp_table = Table(title="Pro-Forma Operating Expenses (Year 1)", show_header=True, header_style="bold red")
    exp_table.add_column("Line Item", style="white")
    exp_table.add_column("Annual Cost ($)", justify="right")
    exp_table.add_column("Per Unit / Year ($)", justify="right")

    u = deal.total_units if deal.total_units > 0 else 1
    exp_table.add_row("Property Taxes", f"${exp.property_taxes:,.0f}", f"${exp.property_taxes / u:,.0f}")
    exp_table.add_row("Insurance", f"${exp.insurance:,.0f}", f"${exp.insurance / u:,.0f}")
    exp_table.add_row("Repairs & Maintenance", f"${exp.repairs_and_maintenance:,.0f}", f"${exp.repairs_and_maintenance / u:,.0f}")
    exp_table.add_row("Utilities", f"${exp.utilities:,.0f}", f"${exp.utilities / u:,.0f}")
    exp_table.add_row("Admin & Legal", f"${exp.admin_and_legal:,.0f}", f"${exp.admin_and_legal / u:,.0f}")
    exp_table.add_row("Management Fee %", f"{exp.property_management_pct:.1%}", "-")
    exp_table.add_row("Replacement Reserves", f"${exp.replacement_reserves_per_unit * u:,.0f}", f"${exp.replacement_reserves_per_unit:,.0f}")
    fixed_tot = exp.fixed_annual_expenses(u)
    exp_table.add_row("[bold]Total Fixed Expenses[/bold]", f"[bold]${fixed_tot:,.0f}[/bold]", f"[bold]${fixed_tot / u:,.0f}[/bold]")
    console.print(exp_table)

    # Financing Terms Table
    fin = deal.financing
    fin_table = Table(title="Financing Assumptions", show_header=True, header_style="bold green")
    fin_table.add_column("Parameter", style="white")
    fin_table.add_column("Assumption Value", justify="right", style="bold")
    fin_table.add_row("Down Payment %", f"{fin.down_payment_pct:.1%}")
    fin_table.add_row("Mortgage Interest Rate", f"{fin.interest_rate:.2%}")
    fin_table.add_row("Amortization Period", f"{fin.amortization_years} Years")
    fin_table.add_row("Loan Term", f"{fin.loan_term_years} Years")
    fin_table.add_row("Interest-Only Period", f"{fin.interest_only_months} Months")
    fin_table.add_row("Closing Costs %", f"{fin.closing_costs_pct:.1%}")
    console.print(fin_table)


def render_executive_panel(result: UnderwritingResult, console: Console) -> None:
    """Render the top-level Investment Committee decision panel."""
    color = (
        "green"
        if result.decision == InvestmentDecision.APPROVED
        else "yellow"
        if result.decision == InvestmentDecision.CONDITIONAL
        else "red"
    )
    console.print(
        Panel(
            f"[bold {color}]Decision: {result.decision.value.upper()}[/bold {color}] | Committee Score: [bold]{result.committee_score}/100[/bold]\n"
            f"{result.executive_summary}",
            title="Investment Committee Memorandum",
            border_style=color,
        )
    )


def render_metrics_table(m: DealMetrics, d: DebtSizingResult, console: Console) -> None:
    """Render financial return metrics and debt sizing constraints."""
    metrics_table = Table(
        title="Key Underwriting Metrics", show_header=True, header_style="bold blue"
    )
    metrics_table.add_column("Metric", style="white")
    metrics_table.add_column("Value", style="bold green", justify="right")

    metrics_table.add_row("Levered IRR", f"{m.levered_irr:.1%}")
    metrics_table.add_row("Unlevered IRR", f"{m.unlevered_irr:.1%}")
    metrics_table.add_row("Equity Multiple", f"{m.equity_multiple:.2f}x")
    metrics_table.add_row("NPV (@ 8.0% discount)", f"${m.net_present_value:,.2f}")
    metrics_table.add_row("Average Cash-on-Cash", f"{m.average_cash_on_cash:.1%}")
    metrics_table.add_row("Entry Cap Rate", f"{m.entry_cap_rate:.2%}")
    metrics_table.add_row("Exit Cap Rate", f"{m.exit_cap_rate:.2%}")
    metrics_table.add_row("Sized Senior Loan", f"${d.loan_amount:,.0f} ({d.ltv_ratio:.1%} LTV)")
    metrics_table.add_row("Required Equity", f"${d.equity_required:,.0f}")
    metrics_table.add_row(
        "Year 1 DSCR", f"{d.dscr_year1:.2f}x (Constraint: {d.binding_constraint})"
    )
    metrics_table.add_row("Year 1 Debt Yield", f"{d.debt_yield_pct:.1%}")

    console.print(metrics_table)


def render_cashflow_table(cash_flows: List[AnnualCashFlow], console: Console) -> None:
    """Render multi-year cash flow pro-forma table."""
    cf_table = Table(
        title="Multi-Year Pro-Forma Schedule ($)", show_header=True, header_style="bold cyan"
    )
    cf_table.add_column("Year", justify="center")
    cf_table.add_column("EGI", justify="right")
    cf_table.add_column("OpEx", justify="right")
    cf_table.add_column("NOI", justify="right")
    cf_table.add_column("Debt Svc", justify="right")
    cf_table.add_column("BTCF", justify="right")
    cf_table.add_column("Exit Proceeds", justify="right")
    cf_table.add_column("Net Cash Flow", justify="right", style="bold")
    cf_table.add_column("DSCR", justify="right")

    for cf in cash_flows:
        cf_table.add_row(
            str(cf.year),
            f"${cf.effective_gross_income:,.0f}",
            f"${cf.operating_expenses:,.0f}",
            f"${cf.net_operating_income:,.0f}",
            f"${cf.debt_service:,.0f}",
            f"${cf.before_tax_cash_flow:,.0f}",
            f"${cf.exit_sale_proceeds:,.0f}" if cf.exit_sale_proceeds > 0 else "-",
            f"${cf.net_cash_flow:,.0f}",
            f"{cf.dscr:.2f}x",
        )

    console.print(cf_table)


def render_monte_carlo_table(mc: MonteCarloSimulationResult, console: Console) -> None:
    """Render Monte Carlo risk statistics and quantile tables."""
    mc_table = Table(
        title=f"Monte Carlo Stochastic Stress Test ({mc.iterations:,} Iterations)",
        show_header=True,
        header_style="bold magenta",
    )
    mc_table.add_column("Statistic / Quantile", style="white")
    mc_table.add_column("Value", justify="right", style="bold yellow")
    mc_table.add_column("Risk Interpretation", style="dim")

    mc_table.add_row("Mean Levered IRR", f"{mc.mean_levered_irr:.1%}", "Central stochastic projection")
    mc_table.add_row("Standard Deviation", f"{mc.std_levered_irr:.1%}", "Volatility of returns")
    mc_table.add_row("Median Levered IRR (P50)", f"{mc.p50_irr:.1%}", "50th percentile baseline")
    mc_table.add_row("Downside Case (P10 IRR)", f"{mc.p10_irr:.1%}", "90% confidence downside floor")
    mc_table.add_row("Upside Case (P90 IRR)", f"{mc.p90_irr:.1%}", "Top-decile outperformance")
    mc_table.add_row("Mean Equity Multiple", f"{mc.mean_equity_multiple:.2f}x", "Average capital multiple")
    mc_table.add_row("Prob(Negative Return)", f"{mc.probability_negative_irr:.1%}", "Risk of principal loss")
    mc_table.add_row("Prob(DSCR Covenant Breach < 1.0x)", f"{mc.probability_dscr_breach:.1%}", "Risk of debt service shortfall")

    if mc.var_95_irr is not None:
        mc_table.add_row("Value-at-Risk (VaR 95%)", f"{mc.var_95_irr:.2%}", "95% worst-case loss threshold")
    if mc.cvar_95_irr is not None:
        mc_table.add_row("Conditional VaR (CVaR 95%)", f"{mc.cvar_95_irr:.2%}", "Expected return in worst 5% tail")

    console.print(mc_table)

    # Variance Attribution breakdown if available
    if mc.variance_attribution:
        va_table = Table(
            title="Variance Attribution (Risk Driver Sensitivity)",
            show_header=True,
            header_style="bold magenta",
        )
        va_table.add_column("Risk Parameter", style="white")
        va_table.add_column("Variance Share", justify="right", style="bold yellow")
        for param, share in mc.variance_attribution.items():
            clean_name = param.replace("_", " ").title()
            va_table.add_row(clean_name, f"{share:.1%}")
        console.print(va_table)


def render_agent_reports_table(agent_reports: Dict[str, AgentAnalysisReport], console: Console) -> None:
    """Render autonomous swarm agent reports and verdicts."""
    agent_table = Table(
        title="Autonomous Swarm Agent Deliberations", show_header=True, header_style="bold white"
    )
    agent_table.add_column("Agent", style="cyan")
    agent_table.add_column("Status", justify="center")
    agent_table.add_column("Confidence", justify="right")
    agent_table.add_column("Summary")
    agent_table.add_column("Flags", justify="right")

    for _, rep in agent_reports.items():
        st_color = (
            "green"
            if rep.status.value == "approved"
            else "yellow"
            if rep.status.value == "conditional"
            else "red"
        )
        agent_table.add_row(
            rep.agent_name,
            f"[{st_color}]{rep.status.value.upper()}[/{st_color}]",
            f"{rep.confidence_score:.0%}",
            rep.summary,
            str(len(rep.risk_flags)),
        )

    console.print(agent_table)


def render_waterfall_table(wf: WaterfallResult, console: Console) -> None:
    """Render private equity LP/GP promote waterfall distribution results."""
    total_dist = sum(d.total_distributable_cash for d in wf.annual_distributions)
    panel_text = (
        f"[bold]Total Distributable Cash:[/bold] ${total_dist:,.0f}\n"
        f"[bold cyan]Limited Partner (LP):[/bold cyan] Invested ${wf.lp_equity_invested:,.0f} | "
        f"Distributions ${wf.lp_total_distributions:,.0f} | "
        f"IRR: [bold green]{wf.lp_irr:.2%}[/bold green] | Multiple: [bold green]{wf.lp_equity_multiple:.2f}x[/bold green]\n"
        f"[bold magenta]General Partner (GP):[/bold magenta] Invested ${wf.gp_equity_invested:,.0f} | "
        f"Distributions ${wf.gp_total_distributions:,.0f} (Promote: ${wf.gp_total_promote:,.0f}) | "
        f"IRR: [bold green]{wf.gp_irr:.2%}[/bold green] | Multiple: [bold green]{wf.gp_equity_multiple:.2f}x[/bold green]"
    )
    console.print(Panel(panel_text, title="Private Equity Waterfall Distribution Summary", border_style="cyan"))

    # Distribution Schedule Table
    table = Table(title="Annual Distribution Schedule ($)", show_header=True, header_style="bold cyan")
    table.add_column("Year", justify="center")
    table.add_column("Distributable", justify="right")
    table.add_column("LP Distribution", justify="right", style="cyan")
    table.add_column("GP Distribution", justify="right", style="magenta")
    table.add_column("GP Promote", justify="right", style="bold yellow")
    table.add_column("LP Unreturned Cap", justify="right")

    for yd in wf.annual_distributions:
        table.add_row(
            str(yd.year),
            f"${yd.total_distributable_cash:,.0f}",
            f"${yd.lp_distribution:,.0f}",
            f"${yd.gp_distribution:,.0f}",
            f"${yd.gp_promote:,.0f}",
            f"${yd.lp_unreturned_capital:,.0f}",
        )
    console.print(table)


def render_sensitivity_table(sens: SensitivityMatrix, console: Console) -> None:
    """Render 2D sensitivity matrix of Exit Cap Rate vs Rent Growth."""
    table = Table(
        title="Levered IRR Sensitivity (Exit Cap Rate vs Annual Rent Growth)",
        show_header=True,
        header_style="bold blue",
    )
    table.add_column("Exit Cap Rate \\ Rent Growth", style="cyan", no_wrap=True)
    for c_val in sens.col_values:
        table.add_column(f"{c_val:.2%}", justify="right")

    for i, r_val in enumerate(sens.row_values):
        cells = [f"[bold]{r_val:.2%}[/bold]"]
        for irr in sens.irr_matrix[i]:
            if irr >= 0.15:
                color = "green"
            elif irr >= 0.10:
                color = "yellow"
            else:
                color = "red"
            cells.append(f"[{color}]{irr:.1%}[/{color}]")
        table.add_row(*cells)

    console.print(table)


def render_breakeven_panel(be: BreakevenMetrics, console: Console) -> None:
    """Render operational breakeven metrics and safety margins."""
    panel_text = (
        f"[bold]Breakeven Occupancy:[/bold] [bold cyan]{be.breakeven_occupancy_pct:.1%}[/bold cyan] "
        f"(Margin of Safety: [bold green]{be.margin_of_safety_occupancy_pct:+.1%}[/bold green])\n"
        f"[bold]Breakeven Monthly Rent:[/bold] [bold cyan]${be.breakeven_monthly_rent_per_unit:,.2f}/unit[/bold cyan] "
        f"(Margin of Safety: [bold green]{be.margin_of_safety_rent_pct:+.1%}[/bold green])\n"
        f"[bold]Required NOI for Senior Debt Service:[/bold] ${be.breakeven_noi_for_debt_service:,.0f}/year"
    )
    console.print(Panel(panel_text, title="Operational Breakeven & Downside Safety Margins", border_style="blue"))


def render_scenario_table(scenarios: Dict[str, DealMetrics], console: Console) -> None:
    """Render scenario comparison (Base vs Bull vs Bear)."""
    table = Table(title="Macro Scenario Return Comparison", show_header=True, header_style="bold magenta")
    table.add_column("Scenario", style="cyan")
    table.add_column("Levered IRR", justify="right", style="bold green")
    table.add_column("Unlevered IRR", justify="right")
    table.add_column("Equity Multiple", justify="right", style="bold yellow")
    table.add_column("NPV (@ 8%)", justify="right")
    table.add_column("Avg Cash-on-Cash", justify="right")
    table.add_column("Min DSCR", justify="right")
    table.add_column("Exit Cap", justify="right")

    for name, m in scenarios.items():
        clean_name = name.replace("_", " ").title()
        table.add_row(
            clean_name,
            f"{m.levered_irr:.1%}",
            f"{m.unlevered_irr:.1%}",
            f"{m.equity_multiple:.2f}x",
            f"${m.net_present_value:,.0f}",
            f"{m.average_cash_on_cash:.1%}",
            f"{m.min_dscr:.2f}x",
            f"{m.exit_cap_rate:.2%}",
        )

    console.print(table)


def render_tax_table(tax: TaxAnalysisResult, console: Console, cost_seg_applied: bool = False) -> None:
    """Render tax analysis, cost segregation benefits, and after-tax returns."""
    irr_delta = tax.after_tax_irr - tax.pre_tax_irr
    tax_savings = sum(-s.tax_liability for s in tax.annual_schedule if s.tax_liability < 0)
    panel_text = (
        f"[bold]Pre-Tax Levered IRR:[/bold] {tax.pre_tax_irr:.2%}  |  "
        f"[bold green]After-Tax Levered IRR:[/bold green] [bold green]{tax.after_tax_irr:.2%}[/bold green] "
        f"({irr_delta:+.2%})\n"
        f"[bold]Cumulative Tax Shield Benefit:[/bold] [bold green]${tax_savings:,.0f}[/bold green]  |  "
        f"[bold]Total Depreciation Claimed:[/bold] ${tax.total_depreciation_claimed:,.0f}\n"
        f"[bold]Cost Segregation Utilized:[/bold] {'[green]YES[/green]' if cost_seg_applied else '[yellow]NO (Straight-Line MACRS)[/yellow]'}\n"
        f"[bold]Estimated Exit Recapture & Capital Gains Tax:[/bold] ${tax.total_exit_taxes:,.0f}"
    )
    console.print(Panel(panel_text, title="Real Estate Tax Analysis & Depreciation Shield", border_style="green"))

    # Yearly tax schedule table
    table = Table(title="Annual Tax Depreciation Schedule ($)", show_header=True, header_style="bold green")
    table.add_column("Yr", justify="center")
    table.add_column("NOI", justify="right")
    table.add_column("Interest", justify="right")
    table.add_column("Depreciation", justify="right", style="cyan")
    table.add_column("Taxable Inc", justify="right")
    table.add_column("Tax (Saved) / Paid", justify="right", style="bold")
    table.add_column("After-Tax Cash Flow", justify="right", style="bold green")

    for s in tax.annual_schedule:
        tax_str = f"-${abs(s.tax_liability):,.0f}" if s.tax_liability < 0 else f"${s.tax_liability:,.0f}"
        table.add_row(
            str(s.year),
            f"${s.noi:,.0f}",
            f"${s.interest_deduction:,.0f}",
            f"${s.depreciation_deduction:,.0f}",
            f"${s.taxable_income:,.0f}",
            tax_str,
            f"${s.after_tax_cash_flow:,.0f}",
        )
    console.print(table)


def render_optimizer_panel(opt: PricingOptimizationResult, console: Console) -> None:
    """Render pricing optimization and target return hurdle solution."""
    status_str = (
        f"[bold red]OVERPRICED by ${opt.pricing_variance:,.0f} ({opt.pricing_variance_pct:+.1%})[/bold red]"
        if opt.is_overpriced
        else f"[bold green]UNDERPRICED / DISCOUNT by ${abs(opt.pricing_variance):,.0f} ({opt.pricing_variance_pct:+.1%})[/bold green]"
    )
    panel_text = (
        f"[bold]Target Return Hurdle:[/bold] [bold yellow]{opt.target_hurdle_irr:.1%} Levered IRR[/bold yellow]  |  "
        f"Min DSCR: {opt.target_min_dscr:.2f}x  |  Min Debt Yield: {opt.target_min_debt_yield:.1%}\n"
        f"[bold]Current Asking Price:[/bold] ${opt.current_purchase_price:,.0f}\n"
        f"[bold green]Max Supportable Purchase Price:[/bold green] [bold green]${opt.max_supportable_purchase_price:,.0f}[/bold green]\n"
        f"[bold]Implied Entry Cap Rate:[/bold] {opt.implied_entry_cap_rate:.2%}\n"
        f"[bold]Required Sized Capitalization:[/bold] Senior Debt ${opt.implied_loan_amount:,.0f}  |  Equity ${opt.implied_equity_required:,.0f}\n"
        f"[bold]Valuation Verdict:[/bold] {status_str}"
    )
    border_color = "red" if opt.is_overpriced else "green"
    console.print(Panel(panel_text, title="Deal Pricing & Hurdle Return Optimizer", border_style=border_color))


def render_compliance_panel(report: ComplianceReport, console: Console) -> None:
    """Render credit policy compliance audit results."""
    status_color = "green" if report.is_compliant else "red"
    console.print(
        Panel(
            f"Deal: [bold cyan]{report.deal_id}[/bold cyan]\n"
            f"Compliance Score: [bold]{report.compliance_score:.1f}%[/bold] ({report.passed_count}/{report.rules_checked} Rules Satisfied)\n"
            f"Errors: [{status_color}]{report.error_count}[/{status_color}] | Warnings: [yellow]{report.warning_count}[/yellow]\n"
            f"Overall Status: [bold {status_color}]{'COMPLIANT' if report.is_compliant else 'NON-COMPLIANT'}[/bold {status_color}]",
            title="Credit Policy Compliance Audit",
            border_style=status_color,
        )
    )

    table = Table(title="Policy Rule Breakdown", show_header=True, header_style="bold blue")
    table.add_column("Rule", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Actual", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Remediation", style="yellow")

    for r in report.results:
        color = "green" if r.passed else "red" if r.severity.value == "error" else "yellow"
        badge = f"[{color}]{'PASS' if r.passed else r.severity.value.upper()}[/{color}]"
        table.add_row(
            r.rule_name,
            badge,
            f"{r.actual_value:.3f}",
            f"{r.operator} {r.threshold_value:.3f}",
            r.remediation or "-",
        )

    console.print(table)


def render_debate_transcript(transcript: DebateTranscript, console: Console) -> None:
    """Render cross-agent deliberation and debate transcript."""
    verdict_color = (
        "green"
        if transcript.final_verdict == InvestmentDecision.APPROVED
        else "yellow"
        if transcript.final_verdict == InvestmentDecision.CONDITIONAL
        else "red"
    )
    panel_text = (
        f"Deal: [bold cyan]{transcript.deal_id}[/bold cyan]\n"
        f"Final Deliberation Verdict: [bold {verdict_color}]{transcript.final_verdict.value.upper()}[/bold {verdict_color}]\n"
        f"Consensus Score: [bold]{transcript.consensus_score:.0%}[/bold]  |  "
        f"Total Debate Rounds: {transcript.total_rounds}  |  "
        f"Challenges Raised: {transcript.challenges_count}  |  "
        f"Concessions: {transcript.concessions_count}"
    )
    console.print(Panel(panel_text, title="Autonomous Multi-Agent Deliberation & Debate", border_style=verdict_color))

    for rnd in transcript.rounds:
        round_table = Table(
            title=f"Debate Round {rnd.round_number} (Consensus: {rnd.round_score:.0%})",
            show_header=True,
            header_style="bold magenta",
        )
        round_table.add_column("Challenger", style="cyan")
        round_table.add_column("Target Agent", style="white")
        round_table.add_column("Topic", style="yellow")
        round_table.add_column("Contested Assumption")
        round_table.add_column("Suggested Adjustment")
        round_table.add_column("Rebuttal / Concession", style="dim")
        round_table.add_column("Status", justify="center")

        for ch in rnd.challenges:
            status_badge = "[green]RESOLVED[/green]" if ch.resolved else "[red]UNRESOLVED[/red]"
            round_table.add_row(
                ch.challenger,
                ch.target_agent,
                ch.topic.value.replace("_", " ").title(),
                ch.contested_assumption,
                ch.suggested_adjustment,
                ch.rebuttal_or_concession or "-",
                status_badge,
            )
        console.print(round_table)


def render_portfolio_summary(
    rollup: PortfolioRollup,
    risk: PortfolioRiskProfile,
    console: Console,
) -> None:
    """Render consolidated portfolio rollup, asset allocations, and stress tests."""
    console.print(
        Panel(
            f"Portfolio: [bold cyan]{rollup.portfolio_name}[/bold cyan]\n"
            f"Total Assets: [bold]{rollup.deal_count}[/bold] ({rollup.total_units} Units, {rollup.total_gross_square_feet:,.0f} SqFt)\n"
            f"Total Capitalization: [bold]${rollup.total_purchase_price:,.0f}[/bold] | Equity: [bold]${rollup.total_equity_invested:,.0f}[/bold] | Debt: [bold]${rollup.total_debt_funded:,.0f}[/bold]\n"
            f"Portfolio Levered IRR: [bold green]{rollup.portfolio_levered_irr:.2%}[/bold green] | Equity Multiple: [bold green]{rollup.portfolio_equity_multiple:.2f}x[/bold green]\n"
            f"Weighted LTV: [bold]{rollup.weighted_ltv:.1%}[/bold] | Weighted DSCR: [bold]{rollup.weighted_dscr:.2f}x[/bold]\n"
            f"Diversification: [bold]{risk.diversification_rating}[/bold] (HHI Concentration Index: {risk.hhi_concentration_index:.0f})",
            title="Portfolio Investment Summary",
        )
    )

    # Asset Table
    asset_table = Table(
        title="Portfolio Asset Allocations", show_header=True, header_style="bold magenta"
    )
    asset_table.add_column("Deal ID", style="cyan")
    asset_table.add_column("Property Type")
    asset_table.add_column("Purchase Price", justify="right")
    asset_table.add_column("Equity Allocated", justify="right")
    asset_table.add_column("Levered IRR", justify="right", style="bold green")
    asset_table.add_column("Multiple", justify="right")
    asset_table.add_column("Weight", justify="right")

    for a in rollup.allocations:
        asset_table.add_row(
            a.deal_id,
            a.property_type,
            f"${a.purchase_price:,.0f}",
            f"${a.equity_allocated:,.0f}",
            f"{a.levered_irr:.1%}",
            f"{a.equity_multiple:.2f}x",
            f"{a.weight_by_equity:.1%}",
        )

    console.print(asset_table)

    # Stress testing results if available
    if risk.stress_test_results:
        stress_table = Table(
            title="Portfolio Macroeconomic Stress Test Scenarios",
            show_header=True,
            header_style="bold red",
        )
        stress_table.add_column("Stress Scenario", style="white")
        stress_table.add_column("Base IRR", justify="right")
        stress_table.add_column("Stressed IRR", justify="right", style="bold yellow")
        stress_table.add_column("IRR Drop", justify="right", style="bold red")
        stress_table.add_column("Min DSCR", justify="right")
        stress_table.add_column("Covenant Breaches", justify="right", style="magenta")

        for st in risk.stress_test_results:
            breaches_str = ", ".join(st.dscr_breach_deals) if st.dscr_breach_deals else "None"
            stress_table.add_row(
                st.scenario_name,
                f"{st.base_portfolio_irr:.2%}",
                f"{st.stressed_portfolio_irr:.2%}",
                f"-{st.irr_drop_basis_points:,.0f} bps",
                f"{st.stressed_min_dscr:.2f}x",
                breaches_str,
            )
        console.print(stress_table)


def render_revisions_table(revisions: List[DealRevision], console: Console) -> None:
    """Render audit history of deal revisions."""
    table = Table(title="Deal Revision Audit Trail", show_header=True, header_style="bold cyan")
    table.add_column("Rev #", justify="center")
    table.add_column("Revision ID", style="cyan")
    table.add_column("Author", style="white", no_wrap=True)
    table.add_column("Date", style="dim", no_wrap=True)
    table.add_column("Summary of Changes", style="yellow")
    table.add_column("Purchase Price", justify="right")

    for r in revisions:
        table.add_row(
            str(r.revision_number),
            r.revision_id,
            r.author,
            r.created_at.strftime("%Y-%m-%d %H:%M"),
            r.change_summary,
            f"${r.deal_snapshot.purchase_price:,.0f}",
        )
    console.print(table)


def render_diff_table(
    deal_id: str,
    rev_a: int,
    rev_b: int,
    diffs: Dict[str, Dict[str, Any]],
    console: Console,
) -> None:
    """Render differences between two revisions of a deal."""
    if not diffs:
        console.print(f"[yellow]No parameter differences found between Revision {rev_a} and Revision {rev_b} for deal '{deal_id}'.[/yellow]")
        return

    table = Table(
        title=f"Revision Diff: Rev {rev_a} vs Rev {rev_b} ({deal_id})",
        show_header=True,
        header_style="bold yellow",
    )
    table.add_column("Parameter Field", style="white")
    table.add_column(f"Revision {rev_a} Value", justify="right", style="cyan")
    table.add_column(f"Revision {rev_b} Value", justify="right", style="green")

    for field, vals in diffs.items():
        v_a = vals["rev_a"]
        v_b = vals["rev_b"]
        table.add_row(
            field.replace("_", " ").title(),
            f"{v_a:,}" if isinstance(v_a, (int, float)) else str(v_a),
            f"{v_b:,}" if isinstance(v_b, (int, float)) else str(v_b),
        )
    console.print(table)
