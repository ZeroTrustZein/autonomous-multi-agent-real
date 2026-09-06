"""Interactive terminal workflow wizard for autonomous real estate deal underwriting."""

from __future__ import annotations

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
    render_executive_panel,
    render_metrics_table,
    render_monte_carlo_table,
    render_optimizer_panel,
    render_portfolio_summary,
    render_scenario_table,
    render_sensitivity_table,
    render_tax_table,
    render_waterfall_table,
)
from autonomous_multi_agent_real.engine.optimizer import DealOptimizer
from autonomous_multi_agent_real.engine.sensitivity import SensitivityEngine
from autonomous_multi_agent_real.engine.tax import TaxEngine
from autonomous_multi_agent_real.engine.waterfall import WaterfallEngine
from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.portfolio.engine import PortfolioManager
from autonomous_multi_agent_real.storage.repository import DealRepository


def run_interactive_session(console: Optional[Console] = None) -> None:
    """Launch the interactive terminal session for underwriting exploration."""
    con = console or Console()
    repo = DealRepository()

    con.print(
        Panel(
            "[bold cyan]Autonomous Multi-Agent Real Estate Underwriting & Cash Flow Simulation[/bold cyan]\n"
            "[dim]Interactive Terminal Command Center | Version 0.1.0[/dim]",
            title="ODYSSEUS Swarm Console",
            border_style="cyan",
        )
    )

    while True:
        con.print("\n[bold magenta]--- Swarm Command Menu ---[/bold magenta]")
        con.print(" [1] List & Inspect Deals")
        con.print(" [2] Run Full Multi-Agent Underwriting Pipeline")
        con.print(" [3] Run Monte Carlo Risk Simulation")
        con.print(" [4] Private Equity Waterfall Distribution (GP/LP)")
        con.print(" [5] Sensitivity Matrix & Breakeven Analysis")
        con.print(" [6] Tax Shield & Cost Segregation Analysis")
        con.print(" [7] Target Hurdle Price / Rent Optimization")
        con.print(" [8] Institutional Credit Policy Compliance Audit")
        con.print(" [9] Swarm Deliberation & Debate Transcript")
        con.print(" [10] Consolidated Portfolio Rollup")
        con.print(" [0] Exit")

        try:
            choice = click.prompt("Select command", default="1").strip().lower()
        except (KeyboardInterrupt, EOFError):
            con.print("\n[yellow]Exiting interactive session.[/yellow]")
            break

        if choice in ("0", "exit", "quit", "q"):
            con.print("[yellow]Exiting interactive session.[/yellow]")
            break

        deals = repo.list_deals()
        deal_ids = [d.id for d in deals]
        default_id = (
            "austin-multifamily"
            if "austin-multifamily" in deal_ids
            else (deal_ids[0] if deal_ids else "")
        )

        if choice == "1":
            render_deals_table(deals, con)
            inspect_id = click.prompt(
                "Enter deal ID to inspect (or press Enter to skip)", default=""
            ).strip()
            if inspect_id:
                target = repo.get_deal(inspect_id)
                if target:
                    render_deal_detail(target, con)
                else:
                    con.print(f"[red]Deal '{inspect_id}' not found.[/red]")

        elif choice == "2":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            iterations = click.prompt("Monte Carlo Iterations", default=500, type=int)
            con.print(f"[cyan]Executing multi-agent workflow on {deal.title}...[/cyan]")
            pipeline = DealPipeline(monte_carlo_iterations=iterations)
            result = pipeline.run(deal)
            render_executive_panel(result, con)
            render_metrics_table(result.deal_metrics, result.debt_sizing, con)
            render_cashflow_table(result.cash_flows, con)
            render_monte_carlo_table(result.monte_carlo, con)
            render_agent_reports_table(result.agent_reports, con)

        elif choice == "3":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            iterations = click.prompt("Simulation Iterations", default=1000, type=int)
            from autonomous_multi_agent_real.agents.debt import DebtAgent
            from autonomous_multi_agent_real.engine.monte_carlo import MonteCarloEngine
            from autonomous_multi_agent_real.engine.state import DealWorkflowContext

            ctx = DealWorkflowContext(deal=deal)
            DebtAgent().analyze(ctx)
            if not ctx.debt_sizing:
                con.print("[red]Debt sizing failed.[/red]")
                continue
            engine = MonteCarloEngine(seed=42)
            mc = engine.simulate(deal=deal, debt_sizing=ctx.debt_sizing, iterations=iterations)
            render_monte_carlo_table(mc, con)

        elif choice == "4":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            pref = click.prompt("Preferred Return Hurdle (e.g. 0.08)", default=0.08, type=float)
            pipeline = DealPipeline(monte_carlo_iterations=100)
            res = pipeline.run(deal)
            cfs = [cf.net_cash_flow for cf in res.cash_flows]
            wf_engine = WaterfallEngine()
            wf_engine.structure.preferred_return_rate = pref
            wf_res = wf_engine.calculate(
                total_equity=res.debt_sizing.equity_required, annual_cash_flows=cfs
            )
            render_waterfall_table(wf_res, con)

        elif choice == "5":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            pipeline = DealPipeline(monte_carlo_iterations=100)
            res = pipeline.run(deal)
            sens_engine = SensitivityEngine()
            sens_matrix = sens_engine.generate_cap_vs_rent_growth_matrix(deal, res.debt_sizing)
            breakeven = sens_engine.calculate_breakeven_metrics(deal, res.debt_sizing)
            scenarios = sens_engine.generate_scenario_comparison(deal, res.debt_sizing)
            render_sensitivity_table(sens_matrix, con)
            render_breakeven_panel(breakeven, con)
            render_scenario_table(scenarios, con)

        elif choice == "6":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            cost_seg = click.confirm("Apply Cost Segregation (Bonus Depreciation)?", default=True)
            pipeline = DealPipeline(monte_carlo_iterations=100)
            res = pipeline.run(deal)
            tax_engine = TaxEngine(enable_cost_segregation=cost_seg)
            annual_nois = [cf.net_operating_income for cf in res.cash_flows]
            exit_gross = res.cash_flows[-1].exit_sale_proceeds
            tax_res = tax_engine.analyze(deal, res.debt_sizing, annual_nois, exit_gross)
            render_tax_table(tax_res, con, cost_seg_applied=cost_seg)

        elif choice == "7":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            target_irr = click.prompt(
                "Target Levered IRR Hurdle (e.g. 0.15)", default=0.15, type=float
            )
            mode = click.prompt("Solver Mode [price / rent]", default="price").strip().lower()
            optimizer = DealOptimizer()
            if mode == "rent":
                req_rent = optimizer.solve_required_market_rent(deal, target_levered_irr=target_irr)
                avg_curr = (
                    deal.total_market_monthly_rent / deal.total_units
                    if deal.total_units > 0
                    else 0.0
                )
                con.print(
                    Panel(
                        f"Current Market Rent: [bold]${avg_curr:,.2f}/unit/mo[/bold]\n"
                        f"Required Market Rent for {target_irr:.1%} IRR: [bold green]${req_rent:,.2f}/unit/mo[/bold green] "
                        f"({(req_rent - avg_curr) / avg_curr:+.1%})",
                        title="Required Market Rent Solution",
                        border_style="green",
                    )
                )
            else:
                opt_res = optimizer.solve_max_offer_price(deal, target_levered_irr=target_irr)
                render_optimizer_panel(opt_res, con)

        elif choice == "8":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            pipeline = DealPipeline(monte_carlo_iterations=100)
            res = pipeline.run(deal)
            if res.compliance_report:
                render_compliance_panel(res.compliance_report, con)

        elif choice == "9":
            deal_id = click.prompt("Target Deal ID", default=default_id).strip()
            deal = repo.get_deal(deal_id)
            if not deal:
                con.print(f"[red]Deal '{deal_id}' not found.[/red]")
                continue
            pipeline = DealPipeline(monte_carlo_iterations=100)
            res = pipeline.run(deal)
            if res.debate_transcript:
                render_debate_transcript(res.debate_transcript, con)

        elif choice == "10":
            con.print("[cyan]Aggregating portfolio deals...[/cyan]")
            mgr = PortfolioManager()
            for d in repo.list_deals():
                mgr.add_deal(d)
            rollup = mgr.generate_rollup()
            risk = mgr.calculate_risk_profile()
            render_portfolio_summary(rollup, risk, con)

        else:
            con.print("[red]Unknown option. Please choose a valid number from the menu.[/red]")
