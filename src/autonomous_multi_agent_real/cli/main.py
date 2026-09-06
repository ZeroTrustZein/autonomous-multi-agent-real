"""Rich terminal CLI for autonomous multi-agent real estate deal underwriting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from autonomous_multi_agent_real.cli.formatters import (
    render_agent_reports_table,
    render_breakeven_panel,
    render_cashflow_table,
    render_compliance_panel,
    render_deal_detail,
    render_deals_table,
    render_debate_transcript,
    render_diff_table,
    render_executive_panel,
    render_metrics_table,
    render_monte_carlo_table,
    render_optimizer_panel,
    render_portfolio_summary,
    render_revisions_table,
    render_scenario_table,
    render_sensitivity_table,
    render_tax_table,
    render_waterfall_table,
)
from autonomous_multi_agent_real.cli.interactive import run_interactive_session
from autonomous_multi_agent_real.engine.optimizer import DealOptimizer
from autonomous_multi_agent_real.engine.sensitivity import SensitivityEngine
from autonomous_multi_agent_real.engine.tax import TaxEngine
from autonomous_multi_agent_real.engine.waterfall import (
    WaterfallEngine,
    get_default_waterfall_structure,
)
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.portfolio.engine import PortfolioManager
from autonomous_multi_agent_real.reporting.exporter import DataExporter
from autonomous_multi_agent_real.reporting.memo import InvestmentMemoGenerator
from autonomous_multi_agent_real.rules.engine import RuleEngine
from autonomous_multi_agent_real.storage.repository import DealRepository
from autonomous_multi_agent_real.types import (
    FinancingTerms,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnitMixItem,
    WaterfallTier,
)

console = Console()

PROPERTY_TYPE_CHOICES = [
    "multi_family",
    "multifamily",
    "single_family",
    "singlefamily",
    "commercial",
    "industrial",
    "mixed_use",
    "mixeduse",
]


def normalize_property_type(val: Optional[str]) -> Optional[PropertyType]:
    """Normalize input string to PropertyType enum."""
    if not val:
        return None
    cleaned = val.lower().replace("-", "").replace("_", "")
    mapping = {
        "multifamily": PropertyType.MULTI_FAMILY,
        "singlefamily": PropertyType.SINGLE_FAMILY,
        "commercial": PropertyType.COMMERCIAL,
        "industrial": PropertyType.INDUSTRIAL,
        "mixeduse": PropertyType.MIXED_USE,
    }
    return mapping.get(cleaned)


@click.group()
@click.version_option(version="0.1.0", prog_name="autonomous-multi-agent-real")
def cli():
    """Autonomous Multi-Agent Real Estate Underwriting & Simulation Engine."""
    pass


@cli.command(name="list")
@click.option(
    "--property-type",
    "-t",
    type=click.Choice(PROPERTY_TYPE_CHOICES, case_sensitive=False),
    default=None,
    help="Filter deals by property asset class.",
)
@click.option("--min-units", type=int, default=None, help="Filter deals by minimum unit count.")
@click.option("--max-price", type=float, default=None, help="Filter deals by maximum purchase price.")
@click.option("--search", "-q", default=None, help="Search text in title, address, or ID.")
@click.option("--json-output", "--json", is_flag=True, help="Output results in JSON format.")
def list_deals(
    property_type: Optional[str],
    min_units: Optional[int],
    max_price: Optional[float],
    search: Optional[str],
    json_output: bool,
):
    """List benchmark property deals available for underwriting with optional filtering."""
    repo = DealRepository()
    pt = normalize_property_type(property_type)
    deals = repo.query_deals(
        property_type=pt,
        min_units=min_units,
        max_price=max_price,
        search_text=search,
    )

    if json_output:
        click.echo(json.dumps([d.model_dump(mode="json") for d in deals], indent=2))
        return

    render_deals_table(deals, console)


@cli.command(name="show")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal to inspect.")
@click.option("--json-output", "--json", is_flag=True, help="Output deal assumptions in JSON.")
def show_deal(deal_id: str, json_output: bool):
    """Display complete financial assumptions, unit mix, expenses, and debt terms for a deal."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    if json_output:
        click.echo(deal.model_dump_json(indent=2))
        return

    render_deal_detail(deal, console)


@cli.command(name="underwrite")
@click.option(
    "--deal-id", "-d", default="austin-multifamily", help="ID of benchmark deal to underwrite."
)
@click.option(
    "--iterations", "-i", default=1000, type=int, help="Monte Carlo simulation iterations."
)
@click.option("--json-out", "-j", default=None, help="File path to save JSON result.")
@click.option("--save", is_flag=True, help="Persist underwriting result to repository.")
@click.option("--json-output", "--json", is_flag=True, help="Print raw JSON result to stdout.")
def underwrite_deal(
    deal_id: str,
    iterations: int,
    json_out: Optional[str],
    save: bool,
    json_output: bool,
):
    """Run autonomous multi-agent underwriting workflow on a deal."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(
            f"[red]Error: Deal '{deal_id}' not found. Use 'list' to see available deals.[/red]"
        )
        raise click.Abort()

    pipeline = DealPipeline(monte_carlo_iterations=iterations)
    result = pipeline.run(deal)

    if save:
        repo.save_result(result)

    if json_out:
        out_p = Path(json_out)
        out_p.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[green]Underwriting result saved to: {out_p.resolve()}[/green]")

    if json_output:
        click.echo(result.model_dump_json(indent=2))
        return

    console.print(
        Panel(
            f"Underwriting Deal: [bold green]{deal.title}[/bold green] ({deal.address})",
            title="Workflow Init",
        )
    )

    # 1. Executive Summary Panel
    render_executive_panel(result, console)

    # 2. Key Metrics Table
    render_metrics_table(result.deal_metrics, result.debt_sizing, console)

    # 3. Cash Flow Pro-Forma Schedule
    render_cashflow_table(result.cash_flows, console)

    # 4. Monte Carlo Percentiles
    render_monte_carlo_table(result.monte_carlo, console)

    # 5. Swarm Agent Reports
    render_agent_reports_table(result.agent_reports, console)


@cli.command(name="simulate")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal to simulate.")
@click.option("--iterations", "-i", default=2000, type=int, help="Number of Monte Carlo paths.")
@click.option("--seed", "-s", default=42, type=int, help="Random number generator seed.")
@click.option("--json-output", "--json", is_flag=True, help="Output simulation metrics in JSON.")
def simulate_deal(deal_id: str, iterations: int, seed: int, json_output: bool):
    """Run high-throughput Monte Carlo risk simulation with quantile distributions."""
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

    if json_output:
        click.echo(res.model_dump_json(indent=2))
        return

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
    render_monte_carlo_table(res, console)


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
@click.option("--down-payment", default=0.25, type=float, help="Equity down payment ratio (default 0.25).")
@click.option("--interest-rate", default=0.065, type=float, help="Senior loan interest rate (default 0.065).")
@click.option("--exit-cap", default=0.065, type=float, help="Exit capitalization rate (default 0.065).")
@click.option("--hold", default=5, type=int, help="Investment hold period in years (default 5).")
@click.option("--json-output", "--json", is_flag=True, help="Output summary result in JSON.")
def quick_underwrite(
    price: float,
    units: int,
    sqft: float,
    rent: float,
    market_rent: float,
    down_payment: float,
    interest_rate: float,
    exit_cap: float,
    hold: int,
    json_output: bool,
):
    """Quickly underwrite custom property parameters without preset configurations."""
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
        hold_period_years=hold,
        exit_cap_rate=exit_cap,
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
            down_payment_pct=down_payment,
            interest_rate=interest_rate,
            amortization_years=30,
            loan_term_years=10,
            interest_only_months=0,
            closing_costs_pct=0.02,
        ),
    )

    pipeline = DealPipeline(monte_carlo_iterations=500)
    result = pipeline.run(deal)

    if json_output:
        click.echo(result.model_dump_json(indent=2))
        return

    m = result.deal_metrics
    console.print(
        Panel(
            f"[bold]Verdict:[/bold] {result.decision.value.upper()} (Score: {result.committee_score}/100)\n"
            f"[bold]Levered IRR:[/bold] {m.levered_irr:.1%} | [bold]Equity Multiple:[/bold] {m.equity_multiple:.2f}x | [bold]Year 1 DSCR:[/bold] {result.debt_sizing.dscr_year1:.2f}x\n"
            f"[bold]Equity Required:[/bold] ${result.debt_sizing.equity_required:,.0f} | [bold]Loan Amount:[/bold] ${result.debt_sizing.loan_amount:,.0f}",
            title="Quick Underwriting Summary",
        )
    )


@cli.command(name="waterfall")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal.")
@click.option("--pref", default=0.08, type=float, help="LP preferred return hurdle rate (e.g. 0.08 for 8%).")
@click.option("--lp-share", default=0.90, type=float, help="Limited Partner equity ownership share (default 0.90).")
@click.option("--gp-share", default=0.10, type=float, help="General Partner equity ownership share (default 0.10).")
@click.option("--json-output", "--json", is_flag=True, help="Output waterfall results in JSON.")
def waterfall_cmd(
    deal_id: str,
    pref: float,
    lp_share: float,
    gp_share: float,
    json_output: bool,
):
    """Compute and display private equity GP/LP promote waterfall distribution tiers."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    pipeline = DealPipeline(monte_carlo_iterations=200)
    result = pipeline.run(deal)

    structure = get_default_waterfall_structure(
        preferred_return_rate=pref,
        lp_equity_pct=lp_share,
        gp_equity_pct=gp_share,
    )
    # Update tier 1 hurdle
    structure.tiers[0] = WaterfallTier(
        name="Return of Capital & Preferred Return",
        hurdle_irr=pref,
        lp_share=lp_share,
        gp_share=gp_share,
    )

    engine = WaterfallEngine(structure=structure)
    cash_flows = [cf.net_cash_flow for cf in result.cash_flows]
    wf_res = engine.calculate(
        total_equity=result.debt_sizing.equity_required,
        annual_cash_flows=cash_flows,
    )

    if json_output:
        click.echo(wf_res.model_dump_json(indent=2))
        return

    render_waterfall_table(wf_res, console)


@cli.command(name="sensitivity")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal to evaluate.")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["matrix", "scenarios", "breakeven", "all"]),
    default="all",
    help="Sensitivity analysis component to display.",
)
@click.option("--json-output", "--json", is_flag=True, help="Output sensitivity metrics in JSON.")
def sensitivity_cmd(deal_id: str, mode: str, json_output: bool):
    """Run multi-variable sensitivity matrix, scenario comparison, and breakeven metrics."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    from autonomous_multi_agent_real.agents.debt import DebtAgent
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext

    ctx = DealWorkflowContext(deal=deal)
    DebtAgent().analyze(ctx)
    if not ctx.debt_sizing:
        console.print("[red]Debt sizing failed.[/red]")
        raise click.Abort()

    engine = SensitivityEngine()
    matrix = engine.generate_cap_vs_rent_growth_matrix(deal, ctx.debt_sizing)
    breakeven = engine.calculate_breakeven_metrics(deal, ctx.debt_sizing)
    scenarios = engine.generate_scenario_comparison(deal, ctx.debt_sizing)

    if json_output:
        payload = {
            "sensitivity_matrix": matrix.model_dump(mode="json"),
            "breakeven_metrics": breakeven.model_dump(mode="json"),
            "scenarios": {k: v.model_dump(mode="json") for k, v in scenarios.items()},
        }
        click.echo(json.dumps(payload, indent=2))
        return

    if mode in ("matrix", "all"):
        render_sensitivity_table(matrix, console)
    if mode in ("breakeven", "all"):
        render_breakeven_panel(breakeven, console)
    if mode in ("scenarios", "all"):
        render_scenario_table(scenarios, console)


@cli.command(name="tax")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal.")
@click.option("--cost-seg/--no-cost-seg", default=True, help="Toggle cost segregation study modeling.")
@click.option("--ordinary-rate", default=0.37, type=float, help="Ordinary income tax rate (default 0.37).")
@click.option("--cap-gains-rate", default=0.20, type=float, help="Capital gains tax rate (default 0.20).")
@click.option("--json-output", "--json", is_flag=True, help="Output tax schedule in JSON.")
def tax_cmd(
    deal_id: str,
    cost_seg: bool,
    ordinary_rate: float,
    cap_gains_rate: float,
    json_output: bool,
):
    """Calculate commercial real estate tax depreciation shield, cost segregation, and after-tax IRR."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    pipeline = DealPipeline(monte_carlo_iterations=200)
    res = pipeline.run(deal)

    engine = TaxEngine(
        ordinary_income_tax_rate=ordinary_rate,
        capital_gains_tax_rate=cap_gains_rate,
        enable_cost_segregation=cost_seg,
    )
    annual_nois = [cf.net_operating_income for cf in res.cash_flows]
    exit_gross = res.cash_flows[-1].exit_sale_proceeds
    tax_res = engine.analyze(
        deal=deal,
        debt_sizing=res.debt_sizing,
        annual_nois=annual_nois,
        exit_gross_proceeds=exit_gross,
    )

    if json_output:
        click.echo(tax_res.model_dump_json(indent=2))
        return

    render_tax_table(tax_res, console, cost_seg_applied=cost_seg)


@cli.command(name="optimize")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal.")
@click.option("--target-irr", "-t", default=0.15, type=float, help="Target levered IRR hurdle (e.g. 0.15).")
@click.option("--target-dscr", default=1.25, type=float, help="Minimum target Year 1 DSCR.")
@click.option("--target-dy", default=0.08, type=float, help="Minimum target Year 1 Debt Yield.")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["price", "rent"]),
    default="price",
    help="Optimization target: maximum purchase price or required market rent.",
)
@click.option("--json-output", "--json", is_flag=True, help="Output optimization result in JSON.")
def optimize_cmd(
    deal_id: str,
    target_irr: float,
    target_dscr: float,
    target_dy: float,
    mode: str,
    json_output: bool,
):
    """Solve for maximum supportable purchase price or required rents to achieve hurdle returns."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    solver = DealOptimizer()
    if mode == "price":
        opt_res = solver.solve_max_offer_price(
            deal=deal,
            target_levered_irr=target_irr,
            target_min_dscr=target_dscr,
            target_min_debt_yield=target_dy,
        )
        if json_output:
            click.echo(opt_res.model_dump_json(indent=2))
            return
        render_optimizer_panel(opt_res, console)
    else:
        req_rent = solver.solve_required_market_rent(
            deal=deal,
            target_levered_irr=target_irr,
            target_min_dscr=target_dscr,
            target_min_debt_yield=target_dy,
        )
        avg_curr = deal.total_market_monthly_rent / deal.total_units if deal.total_units > 0 else 0.0
        delta_pct = (req_rent - avg_curr) / avg_curr if avg_curr > 0 else 0.0

        if json_output:
            click.echo(
                json.dumps(
                    {
                        "deal_id": deal.id,
                        "target_hurdle_irr": target_irr,
                        "current_avg_market_rent": avg_curr,
                        "required_avg_market_rent": req_rent,
                        "rent_adjustment_pct": delta_pct,
                    },
                    indent=2,
                )
            )
            return

        console.print(
            Panel(
                f"Target Levered IRR: [bold yellow]{target_irr:.1%}[/bold yellow]\n"
                f"Current Average Market Rent: [bold]${avg_curr:,.2f}/unit/month[/bold]\n"
                f"Required Average Market Rent: [bold green]${req_rent:,.2f}/unit/month[/bold green] ({delta_pct:+.1%})",
                title="Required Market Rent Solver Solution",
                border_style="green",
            )
        )


@cli.command(name="audit")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal to audit.")
@click.option("--json-output", "--json", is_flag=True, help="Output audit report in JSON format.")
def audit_deal(deal_id: str, json_output: bool):
    """Run institutional credit policy compliance audit on a deal."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    pipeline = DealPipeline(monte_carlo_iterations=200)
    result = pipeline.run(deal)

    report = result.compliance_report
    if not report:
        engine = RuleEngine()
        from autonomous_multi_agent_real.engine.state import DealWorkflowContext

        ctx = DealWorkflowContext(
            deal=deal,
            debt_sizing=result.debt_sizing,
            deal_metrics=result.deal_metrics,
            monte_carlo=result.monte_carlo,
        )
        report = engine.evaluate(ctx)

    if json_output:
        click.echo(report.model_dump_json(indent=2))
        return

    render_compliance_panel(report, console)


@cli.command(name="debate")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal.")
@click.option("--json-output", "--json", is_flag=True, help="Output deliberation transcript in JSON.")
def debate_cmd(deal_id: str, json_output: bool):
    """Display autonomous swarm deliberation, cross-agent challenges, and committee consensus."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    pipeline = DealPipeline(monte_carlo_iterations=200)
    result = pipeline.run(deal)

    transcript = result.debate_transcript
    if not transcript:
        from autonomous_multi_agent_real.collaboration.debate import DeliberationEngine
        from autonomous_multi_agent_real.engine.state import DealWorkflowContext

        ctx = DealWorkflowContext(
            deal=deal,
            debt_sizing=result.debt_sizing,
            deal_metrics=result.deal_metrics,
            agent_reports=result.agent_reports,
        )
        delib = DeliberationEngine()
        transcript = delib.conduct_deliberation(ctx)

    if json_output:
        click.echo(transcript.model_dump_json(indent=2))
        return

    render_debate_transcript(transcript, console)


@cli.command(name="portfolio")
@click.option(
    "--deals",
    default=None,
    help="Comma-separated deal IDs to include in portfolio (default: all benchmark deals).",
)
@click.option("--stress/--no-stress", default=True, help="Include macro stress testing scenarios.")
@click.option("--json-output", "--json", is_flag=True, help="Output portfolio rollup in JSON.")
def portfolio_summary(deals: Optional[str], stress: bool, json_output: bool):
    """Underwrite and roll up real estate deals into a consolidated portfolio with stress tests."""
    mgr = PortfolioManager()
    repo = DealRepository()

    if deals:
        ids = [d_id.strip() for d_id in deals.split(",") if d_id.strip()]
        for deal_id in ids:
            d = repo.get_deal(deal_id)
            if d:
                mgr.add_deal(d)
    else:
        for deal in repo.list_deals():
            mgr.add_deal(deal)

    if not json_output:
        console.print("[cyan]Underwriting portfolio deals...[/cyan]")

    rollup = mgr.generate_rollup()
    risk = mgr.calculate_risk_profile()

    if json_output:
        payload = {
            "rollup": rollup.model_dump(mode="json"),
            "risk_profile": risk.model_dump(mode="json"),
        }
        click.echo(json.dumps(payload, indent=2))
        return

    render_portfolio_summary(rollup, risk, console)


@cli.command(name="memo")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal.")
@click.option("--out", "-o", default=None, help="Output markdown file path.")
@click.option("--iterations", "-i", default=500, type=int, help="Simulation iterations for memo.")
def generate_memo_cmd(deal_id: str, out: Optional[str], iterations: int):
    """Generate executive investment committee memorandum in Markdown."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    pipeline = DealPipeline(monte_carlo_iterations=iterations)
    result = pipeline.run(deal)

    memo_gen = InvestmentMemoGenerator()
    memo = memo_gen.generate_memo(
        deal=deal, result=result, compliance_report=result.compliance_report
    )

    if out:
        out_path = Path(out)
        out_path.write_text(memo, encoding="utf-8")
        console.print(f"[green]Investment memo saved to: {out_path.resolve()}[/green]")
    else:
        console.print(memo)


@cli.command(name="export")
@click.option("--deal-id", "-d", default="austin-multifamily", help="ID of deal.")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["cashflow", "waterfall", "sensitivity", "json"]),
    default="cashflow",
    help="Export format.",
)
@click.option("--out", "-o", default=None, help="Output file path.")
def export_data_cmd(deal_id: str, format: str, out: Optional[str]):
    """Export deal underwriting data to CSV or JSON."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Error: Deal '{deal_id}' not found.[/red]")
        raise click.Abort()

    pipeline = DealPipeline(monte_carlo_iterations=200)
    result = pipeline.run(deal)

    exporter = DataExporter()
    if format == "cashflow":
        content = exporter.export_cashflows_csv(result)
    elif format == "waterfall":
        content = exporter.export_waterfall_csv(result)
    elif format == "sensitivity":
        content = exporter.export_sensitivity_csv(result)
    else:
        content = exporter.export_underwriting_json(result)

    if out:
        out_path = Path(out)
        out_path.write_text(content, encoding="utf-8")
        console.print(f"[green]Data successfully exported to: {out_path.resolve()}[/green]")
    else:
        console.print(content)


# --------------------------------------------------------------------------
# Deal Management Subgroup
# --------------------------------------------------------------------------


@cli.group(name="deal")
def deal_group():
    """Deal repository management, revisions, import, and diffing."""
    pass


@deal_group.command(name="import")
@click.option("--file", "-f", "file_path", required=True, type=click.Path(exists=True), help="Path to deal JSON file.")
def deal_import(file_path: str):
    """Import a property deal from JSON file into the repository."""
    raw = Path(file_path).read_text(encoding="utf-8")
    data = json.loads(raw)
    deal = PropertyDeal.model_validate(data)
    repo = DealRepository()
    repo.save_deal(deal)
    console.print(f"[green]Successfully imported deal '{deal.id}' ({deal.title}) into repository.[/green]")


@deal_group.command(name="export")
@click.option("--deal-id", "-d", required=True, help="ID of deal to export.")
@click.option("--out", "-o", required=True, help="Destination JSON path.")
def deal_export(deal_id: str, out: str):
    """Export property deal specification to JSON."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Deal '{deal_id}' not found.[/red]")
        raise click.Abort()
    out_p = Path(out)
    out_p.write_text(deal.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"[green]Exported deal '{deal_id}' to: {out_p.resolve()}[/green]")


@deal_group.command(name="delete")
@click.option("--deal-id", "-d", required=True, help="ID of deal to delete.")
def deal_delete(deal_id: str):
    """Delete a property deal from the repository."""
    repo = DealRepository()
    if repo.delete_deal(deal_id):
        console.print(f"[green]Deal '{deal_id}' deleted successfully.[/green]")
    else:
        console.print(f"[red]Deal '{deal_id}' not found.[/red]")


@deal_group.command(name="revisions")
@click.option("--deal-id", "-d", required=True, help="ID of deal to inspect revisions.")
def deal_revisions(deal_id: str):
    """List audit revision history for a property deal."""
    repo = DealRepository()
    revs = repo.get_revisions(deal_id)
    if not revs:
        console.print(f"[yellow]No revisions found for deal '{deal_id}'.[/yellow]")
        return
    render_revisions_table(revs, console)


@deal_group.command(name="create-revision")
@click.option("--deal-id", "-d", required=True, help="ID of deal.")
@click.option("--author", "-a", default="analyst", help="Author of revision.")
@click.option("--summary", "-s", default="Assumptions update", help="Summary of changes.")
def deal_create_revision(deal_id: str, author: str, summary: str):
    """Create a new versioned snapshot revision for a deal."""
    repo = DealRepository()
    deal = repo.get_deal(deal_id)
    if not deal:
        console.print(f"[red]Deal '{deal_id}' not found.[/red]")
        raise click.Abort()
    rev = repo.create_revision(deal, author=author, change_summary=summary)
    console.print(
        f"[green]Created revision #{rev.revision_number} (ID: {rev.revision_id}) for deal '{deal_id}'.[/green]"
    )


@deal_group.command(name="diff")
@click.option("--deal-id", "-d", required=True, help="ID of deal.")
@click.option("--rev1", "-r1", required=True, type=int, help="First revision number.")
@click.option("--rev2", "-r2", required=True, type=int, help="Second revision number.")
def deal_diff(deal_id: str, rev1: int, rev2: int):
    """Diff financial parameters between two revisions of a deal."""
    repo = DealRepository()
    diffs = repo.diff_revisions(deal_id, rev1, rev2)
    render_diff_table(deal_id, rev1, rev2, diffs, console)


@deal_group.command(name="revert")
@click.option("--deal-id", "-d", required=True, help="ID of deal.")
@click.option("--rev", "-r", required=True, type=int, help="Revision number to restore.")
def deal_revert(deal_id: str, rev: int):
    """Revert deal assumptions to a previous revision state."""
    repo = DealRepository()
    restored = repo.revert_to_revision(deal_id, rev)
    if restored:
        console.print(f"[green]Successfully reverted deal '{deal_id}' to revision {rev}.[/green]")
    else:
        console.print(f"[red]Revision {rev} not found for deal '{deal_id}'.[/red]")


@cli.command(name="interactive")
def interactive_cmd():
    """Launch the interactive terminal command center for exploratory deal underwriting."""
    run_interactive_session(console)
