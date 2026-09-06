"""Rich terminal CLI for autonomous multi-agent real estate deal underwriting."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.storage.repository import DealRepository
from autonomous_multi_agent_real.types import (
    FinancingTerms,
    InvestmentDecision,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnitMixItem,
)

console = Console()


@click.group()
def cli():
    """Autonomous Multi-Agent Real Estate Underwriting & Simulation Engine."""
    pass


@cli.command(name="list")
def list_deals():
    """List benchmark property deals available for underwriting."""
    repo = DealRepository()
    deals = repo.list_deals()

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

    for d in deals:
        table.add_row(
            d.id,
            d.title,
            d.property_type.value,
            str(d.total_units),
            f"{d.gross_square_feet:,.0f}",
            f"${d.purchase_price:,.0f}",
            f"${d.total_current_monthly_rent:,.0f}",
        )

    console.print(table)


@cli.command(name="underwrite")
@click.option(
    "--deal-id", "-d", default="austin-multifamily", help="ID of benchmark deal to underwrite."
)
@click.option(
    "--iterations", "-i", default=1000, type=int, help="Monte Carlo simulation iterations."
)
def underwrite_deal(deal_id: str, iterations: int):
    """Run autonomous multi-agent underwriting workflow on a deal."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(
            f"[red]Error: Deal '{deal_id}' not found. Use 'list' to see available deals.[/red]"
        )
        raise click.Abort()

    console.print(
        Panel(
            f"Underwriting Deal: [bold green]{deal.title}[/bold green] ({deal.address})",
            title="Workflow Init",
        )
    )

    pipeline = DealPipeline(monte_carlo_iterations=iterations)
    result = pipeline.run(deal)

    # 1. Executive Summary Panel
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

    # 2. Key Metrics Table
    m = result.deal_metrics
    d = result.debt_sizing
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

    # 3. Cash Flow Pro-Forma Schedule
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

    for cf in result.cash_flows:
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

    # 4. Monte Carlo Percentiles
    mc = result.monte_carlo
    mc_table = Table(
        title=f"Monte Carlo Stochastic Stress Test ({mc.iterations:,} Iterations)",
        show_header=True,
        header_style="bold magenta",
    )
    mc_table.add_column("Statistic", style="white")
    mc_table.add_column("Value", justify="right", style="bold yellow")

    mc_table.add_row("Mean Levered IRR", f"{mc.mean_levered_irr:.1%}")
    mc_table.add_row("Median Levered IRR (P50)", f"{mc.p50_irr:.1%}")
    mc_table.add_row("Downside Case (P10 IRR)", f"{mc.p10_irr:.1%}")
    mc_table.add_row("Upside Case (P90 IRR)", f"{mc.p90_irr:.1%}")
    mc_table.add_row("Mean Equity Multiple", f"{mc.mean_equity_multiple:.2f}x")
    mc_table.add_row("Prob(Negative Return)", f"{mc.probability_negative_irr:.1%}")
    mc_table.add_row("Prob(DSCR Covenant Breach < 1.0x)", f"{mc.probability_dscr_breach:.1%}")

    console.print(mc_table)

    # 5. Swarm Agent Reports
    agent_table = Table(
        title="Autonomous Swarm Agent Deliberations", show_header=True, header_style="bold white"
    )
    agent_table.add_column("Agent", style="cyan")
    agent_table.add_column("Status", justify="center")
    agent_table.add_column("Summary")
    agent_table.add_column("Flags", justify="right")

    for _, rep in result.agent_reports.items():
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
            rep.summary,
            str(len(rep.risk_flags)),
        )

    console.print(agent_table)


@cli.command(name="simulate")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal to simulate.")
@click.option("--iterations", "-i", default=2000, type=int, help="Number of Monte Carlo paths.")
@click.option("--seed", "-s", default=42, type=int, help="Random number generator seed.")
def simulate_deal(deal_id: str, iterations: int, seed: int):
    """Run high-throughput Monte Carlo risk simulation."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    from autonomous_multi_agent_real.agents.debt import DebtAgent
    from autonomous_multi_agent_real.engine.monte_carlo import MonteCarloEngine
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext

    ctx = DealWorkflowContext(deal=deal)
    DebtAgent().analyze(ctx)
    if not ctx.debt_sizing:
        console.print("[red]Debt sizing failed.[/red]")
        raise click.Abort()

    engine = MonteCarloEngine(seed=seed)
    res = engine.simulate(deal=deal, debt_sizing=ctx.debt_sizing, iterations=iterations)

    console.print(
        Panel(
            f"Simulated [bold cyan]{iterations:,}[/bold cyan] iterations for deal [bold green]{deal.title}[/bold green]\n"
            f"Mean IRR: [bold]{res.mean_levered_irr:.2%}[/bold] (Std: {res.std_levered_irr:.2%})\n"
            f"P10: [yellow]{res.p10_irr:.2%}[/yellow] | Median (P50): [green]{res.p50_irr:.2%}[/green] | P90: [bold green]{res.p90_irr:.2%}[/bold green]\n"
            f"Probability of Negative Return: [bold red]{res.probability_negative_irr:.2%}[/bold red]\n"
            f"Probability of Covenant Default (DSCR < 1.0): [bold red]{res.probability_dscr_breach:.2%}[/bold red]",
            title="Monte Carlo Simulation Report",
        )
    )


@cli.command(name="quick")
@click.option("--price", "-p", required=True, type=float, help="Purchase price ($).")
@click.option("--units", "-u", required=True, type=int, help="Number of units.")
@click.option("--sqft", required=True, type=float, help="Gross square footage.")
@click.option(
    "--rent", "-r", required=True, type=float, help="Average monthly in-place rent per unit."
)
@click.option(
    "--market-rent", "-m", required=True, type=float, help="Average monthly market rent per unit."
)
def quick_underwrite(price: float, units: int, sqft: float, rent: float, market_rent: float):
    """Quickly underwrite custom property parameters."""
    deal = PropertyDeal(
        id="custom-quick-deal",
        title="Quick Underwrite Property",
        address="Custom Property Address",
        property_type=PropertyType.MULTI_FAMILY,
        gross_square_feet=sqft,
        unit_mix=[
            UnitMixItem(
                unit_type="Standard-Unit",
                count=units,
                square_feet=sqft / units if units > 0 else 800.0,
                current_rent=rent,
                market_rent=market_rent,
            )
        ],
        purchase_price=price,
        rehab_budget=0.0,
        current_occupancy_pct=0.95,
        market_occupancy_pct=0.95,
        annual_rent_growth_pct=0.03,
        annual_expense_growth_pct=0.025,
        hold_period_years=5,
        exit_cap_rate=0.065,
        expenses=OperatingExpenses(
            property_taxes=price * 0.015,
            insurance=units * 600.0,
            repairs_and_maintenance=units * 800.0,
            property_management_pct=0.07,
            utilities=units * 300.0,
            admin_and_legal=3000.0,
            replacement_reserves_per_unit=250.0,
        ),
        financing=FinancingTerms(
            purchase_price=price,
            down_payment_pct=0.25,
            interest_rate=0.065,
            amortization_years=30,
            loan_term_years=10,
            interest_only_months=0,
            closing_costs_pct=0.02,
        ),
    )

    pipeline = DealPipeline(monte_carlo_iterations=500)
    result = pipeline.run(deal)

    m = result.deal_metrics
    console.print(
        Panel(
            f"[bold]Verdict:[/bold] {result.decision.value.upper()} (Score: {result.committee_score}/100)\n"
            f"[bold]Levered IRR:[/bold] {m.levered_irr:.1%} | [bold]Equity Multiple:[/bold] {m.equity_multiple:.2f}x | [bold]Year 1 DSCR:[/bold] {result.debt_sizing.dscr_year1:.2f}x\n"
            f"[bold]Equity Required:[/bold] ${result.debt_sizing.equity_required:,.0f} | [bold]Loan Amount:[/bold] ${result.debt_sizing.loan_amount:,.0f}",
            title="Quick Underwriting Summary",
        )
    )
