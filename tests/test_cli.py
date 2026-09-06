"""Comprehensive test suite for Stage 5 CLI and terminal interfaces."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from autonomous_multi_agent_real.cli.main import cli
from autonomous_multi_agent_real.storage.repository import DealRepository


def test_cli_version():
    """Verify version option works."""
    runner = CliRunner()
    res = runner.invoke(cli, ["--version"])
    assert res.exit_code == 0
    assert "0.1.0" in res.output


def test_cli_list_with_filters():
    """Verify list command with property type, unit, price, and search query filters."""
    runner = CliRunner()

    # 1. Standard list
    res = runner.invoke(cli, ["list"])
    assert res.exit_code == 0
    assert "Available Real Estate Underwriting Deals" in res.output
    assert "austin-multifamily" in res.output

    # 2. Filter by property type
    res_mf = runner.invoke(cli, ["list", "--property-type", "multifamily"])
    assert res_mf.exit_code == 0
    assert "austin-multifamily" in res_mf.output
    assert "dallas-industrial" not in res_mf.output

    # 3. Filter by min units
    res_units = runner.invoke(cli, ["list", "--min-units", "20"])
    assert res_units.exit_code == 0
    assert "austin-multifamily" in res_units.output  # 24 units

    # 4. Filter by max price
    res_price = runner.invoke(cli, ["list", "--max-price", "5000000"])
    assert res_price.exit_code == 0
    assert "austin-multifamily" in res_price.output  # $4M
    assert "dallas-industrial" not in res_price.output  # $6.5M

    # 5. Search query
    res_search = runner.invoke(cli, ["list", "--search", "dallas"])
    assert res_search.exit_code == 0
    assert "dallas-industrial" in res_search.output
    assert "austin-multifamily" not in res_search.output

    # 6. JSON output
    res_json = runner.invoke(cli, ["list", "--json"])
    assert res_json.exit_code == 0
    parsed = json.loads(res_json.output)
    assert isinstance(parsed, list)
    assert len(parsed) >= 3


def test_cli_show_deal():
    """Verify detailed deal inspection command."""
    runner = CliRunner()

    # Rich table output
    res = runner.invoke(cli, ["show", "--deal-id", "austin-multifamily"])
    assert res.exit_code == 0
    assert "Travis Heights 24-Unit Value-Add" in res.output
    assert "Unit Mix Breakdown" in res.output
    assert "Pro-Forma Operating Expenses" in res.output
    assert "Financing Assumptions" in res.output

    # JSON output
    res_json = runner.invoke(cli, ["show", "--deal-id", "austin-multifamily", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["id"] == "austin-multifamily"
    assert data["purchase_price"] == 4800000.0

    # Non-existent deal
    res_missing = runner.invoke(cli, ["show", "--deal-id", "non-existent"])
    assert res_missing.exit_code != 0


def test_cli_underwrite_advanced(tmp_path: Path):
    """Verify underwrite command with JSON export and repository persistence."""
    runner = CliRunner()
    json_path = tmp_path / "underwrite_res.json"

    res = runner.invoke(
        cli,
        [
            "underwrite",
            "--deal-id",
            "austin-multifamily",
            "--iterations",
            "100",
            "--json-out",
            str(json_path),
            "--save",
        ],
    )
    assert res.exit_code == 0
    assert "Investment Committee Memorandum" in res.output
    assert json_path.exists()

    # Verify JSON structure
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["deal_id"] == "austin-multifamily"
    assert "deal_metrics" in saved

    # Verify stdout JSON mode
    res_raw = runner.invoke(
        cli,
        ["underwrite", "--deal-id", "austin-multifamily", "--iterations", "50", "--json"],
    )
    assert res_raw.exit_code == 0
    parsed = json.loads(res_raw.output)
    assert parsed["deal_id"] == "austin-multifamily"


def test_cli_simulate_advanced():
    """Verify simulate command with seed and JSON output."""
    runner = CliRunner()

    # Visual mode
    res = runner.invoke(
        cli,
        ["simulate", "--deal-id", "austin-multifamily", "--iterations", "200", "--seed", "123"],
    )
    assert res.exit_code == 0
    assert "Monte Carlo Simulation Report" in res.output
    assert "Mean Levered IRR" in res.output

    # JSON mode
    res_json = runner.invoke(
        cli,
        ["simulate", "--deal-id", "austin-multifamily", "--iterations", "100", "--json"],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["iterations"] == 100
    assert "mean_levered_irr" in data
    assert "p50_irr" in data


def test_cli_quick_advanced():
    """Verify quick underwrite with extended financing options."""
    runner = CliRunner()

    res = runner.invoke(
        cli,
        [
            "quick",
            "--price",
            "3000000",
            "--units",
            "16",
            "--sqft",
            "12000",
            "--rent",
            "1450",
            "--market-rent",
            "1700",
            "--down-payment",
            "0.30",
            "--interest-rate",
            "0.06",
            "--exit-cap",
            "0.06",
            "--hold",
            "7",
        ],
    )
    assert res.exit_code == 0
    assert "Quick Underwriting Summary" in res.output
    assert "Levered IRR:" in res.output

    # JSON mode
    res_json = runner.invoke(
        cli,
        [
            "quick",
            "--price",
            "3000000",
            "--units",
            "16",
            "--sqft",
            "12000",
            "--rent",
            "1450",
            "--market-rent",
            "1700",
            "--json",
        ],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["deal_id"] == "custom-quick-deal"


def test_cli_waterfall_command():
    """Verify private equity waterfall distribution CLI command."""
    runner = CliRunner()

    # Visual mode
    res = runner.invoke(
        cli,
        [
            "waterfall",
            "--deal-id",
            "austin-multifamily",
            "--pref",
            "0.08",
            "--lp-share",
            "0.85",
            "--gp-share",
            "0.15",
        ],
    )
    assert res.exit_code == 0
    assert "Private Equity Waterfall Distribution Summary" in res.output
    assert "Annual Distribution Schedule" in res.output
    assert "Limited Partner (LP)" in res.output
    assert "General Partner (GP)" in res.output

    # JSON mode
    res_json = runner.invoke(cli, ["waterfall", "--deal-id", "austin-multifamily", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "lp_irr" in data
    assert "gp_irr" in data
    assert "annual_distributions" in data


def test_cli_sensitivity_command():
    """Verify sensitivity command modes (matrix, breakeven, scenarios, all)."""
    runner = CliRunner()

    # 1. Matrix mode
    res_mat = runner.invoke(cli, ["sensitivity", "--deal-id", "austin-multifamily", "-m", "matrix"])
    assert res_mat.exit_code == 0
    assert "Levered IRR Sensitivity" in res_mat.output

    # 2. Breakeven mode
    res_be = runner.invoke(cli, ["sensitivity", "--deal-id", "austin-multifamily", "-m", "breakeven"])
    assert res_be.exit_code == 0
    assert "Operational Breakeven & Downside Safety Margins" in res_be.output

    # 3. Scenarios mode
    res_scen = runner.invoke(cli, ["sensitivity", "--deal-id", "austin-multifamily", "-m", "scenarios"])
    assert res_scen.exit_code == 0
    assert "Macro Scenario Return Comparison" in res_scen.output

    # 4. All mode (default)
    res_all = runner.invoke(cli, ["sensitivity", "--deal-id", "austin-multifamily"])
    assert res_all.exit_code == 0
    assert "Levered IRR Sensitivity" in res_all.output
    assert "Operational Breakeven" in res_all.output
    assert "Macro Scenario Return Comparison" in res_all.output

    # 5. JSON mode
    res_json = runner.invoke(cli, ["sensitivity", "--deal-id", "austin-multifamily", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "sensitivity_matrix" in data
    assert "breakeven_metrics" in data
    assert "scenarios" in data


def test_cli_tax_command():
    """Verify real estate tax depreciation and cost segregation CLI command."""
    runner = CliRunner()

    # Cost segregation enabled
    res_cs = runner.invoke(cli, ["tax", "--deal-id", "austin-multifamily", "--cost-seg"])
    assert res_cs.exit_code == 0
    assert "Real Estate Tax Analysis & Depreciation Shield" in res_cs.output
    assert "Cost Segregation Utilized: YES" in res_cs.output

    # Cost segregation disabled (straight-line)
    res_sl = runner.invoke(cli, ["tax", "--deal-id", "austin-multifamily", "--no-cost-seg"])
    assert res_sl.exit_code == 0
    assert "Cost Segregation Utilized: NO" in res_sl.output

    # JSON mode
    res_json = runner.invoke(cli, ["tax", "--deal-id", "austin-multifamily", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "after_tax_irr" in data
    assert "annual_schedule" in data


def test_cli_optimize_command():
    """Verify price and rent solver optimization commands."""
    runner = CliRunner()

    # 1. Price solve mode
    res_price = runner.invoke(
        cli,
        ["optimize", "--deal-id", "austin-multifamily", "--target-irr", "0.16", "--mode", "price"],
    )
    assert res_price.exit_code == 0
    assert "Deal Pricing & Hurdle Return Optimizer" in res_price.output
    assert "Max Supportable Purchase Price" in res_price.output

    # 2. Rent solve mode
    res_rent = runner.invoke(
        cli,
        ["optimize", "--deal-id", "austin-multifamily", "--target-irr", "0.16", "--mode", "rent"],
    )
    assert res_rent.exit_code == 0
    assert "Required Market Rent Solver Solution" in res_rent.output
    assert "Required Average Market Rent" in res_rent.output

    # 3. JSON mode
    res_json = runner.invoke(
        cli,
        ["optimize", "--deal-id", "austin-multifamily", "--target-irr", "0.16", "--json"],
    )
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "max_supportable_purchase_price" in data


def test_cli_debate_command():
    """Verify swarm deliberation transcript CLI command."""
    runner = CliRunner()

    # Visual mode
    res = runner.invoke(cli, ["debate", "--deal-id", "austin-multifamily"])
    assert res.exit_code == 0
    assert "Autonomous Multi-Agent Deliberation & Debate" in res.output
    assert "Debate Round" in res.output

    # JSON mode
    res_json = runner.invoke(cli, ["debate", "--deal-id", "austin-multifamily", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "consensus_score" in data
    assert "rounds" in data


def test_cli_portfolio_advanced():
    """Verify portfolio command with custom deal selection and JSON export."""
    runner = CliRunner()

    # Specific deals selection
    res = runner.invoke(
        cli,
        ["portfolio", "--deals", "austin-multifamily,dallas-industrial", "--stress"],
    )
    assert res.exit_code == 0
    assert "Portfolio Investment Summary" in res.output
    assert "Portfolio Macroeconomic Stress Test Scenarios" in res.output

    # JSON output
    res_json = runner.invoke(cli, ["portfolio", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "rollup" in data
    assert "risk_profile" in data


def test_cli_deal_subcommands(tmp_path: Path):
    """Verify deal repository management subcommands: export, import, revisions, diff, delete, revert."""
    runner = CliRunner()
    export_file = tmp_path / "exported_deal.json"

    # 1. Export deal
    res_exp = runner.invoke(
        cli,
        ["deal", "export", "--deal-id", "austin-multifamily", "--out", str(export_file)],
    )
    assert res_exp.exit_code == 0
    assert export_file.exists()

    # 2. Modify JSON and import as custom deal
    deal_dict = json.loads(export_file.read_text(encoding="utf-8"))
    deal_dict["id"] = "phoenix-industrial"
    deal_dict["title"] = "Phoenix Logistics Center"
    custom_import_file = tmp_path / "phoenix.json"
    custom_import_file.write_text(json.dumps(deal_dict), encoding="utf-8")

    res_imp = runner.invoke(cli, ["deal", "import", "--file", str(custom_import_file)])
    assert res_imp.exit_code == 0
    assert "phoenix-industrial" in res_imp.output

    # Check imported deal appears in list
    repo = DealRepository()
    assert repo.get_deal("phoenix-industrial") is not None

    # 3. Create revisions in repository and list them via CLI
    res_create_rev = runner.invoke(
        cli,
        [
            "deal",
            "create-revision",
            "--deal-id",
            "phoenix-industrial",
            "--author",
            "analyst_jane",
            "--summary",
            "First rev",
        ],
    )
    assert res_create_rev.exit_code == 0
    res_revs = runner.invoke(cli, ["deal", "revisions", "--deal-id", "phoenix-industrial"])
    assert res_revs.exit_code == 0
    assert "Deal Revision Audit Trail" in res_revs.output
    assert "First rev" in res_revs.output
    assert "analyst" in res_revs.output

    # 4. Diff revisions
    res_diff = runner.invoke(
        cli,
        ["deal", "diff", "--deal-id", "phoenix-industrial", "--rev1", "1", "--rev2", "1"],
    )
    assert res_diff.exit_code == 0
    assert "No parameter differences found" in res_diff.output

    # 5. Revert revision
    res_rev = runner.invoke(cli, ["deal", "revert", "--deal-id", "phoenix-industrial", "--rev", "1"])
    assert res_rev.exit_code == 0
    assert "Successfully reverted deal" in res_rev.output

    # 6. Delete deal
    res_del = runner.invoke(cli, ["deal", "delete", "--deal-id", "phoenix-industrial"])
    assert res_del.exit_code == 0
    assert "deleted successfully" in res_del.output


def test_cli_interactive_exit():
    """Verify interactive wizard can be launched and cleanly exited."""
    runner = CliRunner()
    res = runner.invoke(cli, ["interactive"], input="0\n")
    assert res.exit_code == 0
    assert "Exiting interactive session." in res.output


def test_cli_interactive_list_and_exit():
    """Verify interactive wizard deal listing branch."""
    runner = CliRunner()
    # Choice 1: list deals, enter inspect deal ID, then choice 0: exit
    res = runner.invoke(cli, ["interactive"], input="1\naustin-multifamily\n0\n")
    assert res.exit_code == 0
    assert "Available Real Estate Underwriting Deals" in res.output
    assert "Travis Heights" in res.output
    assert "Exiting interactive session." in res.output


def test_cli_interactive_features():
    """Verify interactive wizard execution for sensitivity, waterfall, and portfolio."""
    runner = CliRunner()
    # Choice 4 (waterfall), austin-multifamily, pref 0.08
    # Then Choice 10 (portfolio)
    # Then Choice 0 (exit)
    commands_input = "4\naustin-multifamily\n0.08\n10\n0\n"
    res = runner.invoke(cli, ["interactive"], input=commands_input)
    assert res.exit_code == 0
    assert "Private Equity Waterfall Distribution Summary" in res.output
    assert "Portfolio Investment Summary" in res.output
    assert "Exiting interactive session." in res.output


def test_cli_interactive_comprehensive_commands():
    """Verify interactive wizard for full underwriting, sim, sens, tax, opt, audit, debate."""
    runner = CliRunner()
    # Sequence of commands through interactive menu:
    # 2 (underwrite), austin-multifamily, 100
    # 3 (simulate), austin-multifamily, 100
    # 5 (sensitivity), austin-multifamily
    # 6 (tax), austin-multifamily, y (cost-seg)
    # 7 (optimize rent), austin-multifamily, 0.15, rent
    # 7 (optimize price), austin-multifamily, 0.15, price
    # 8 (audit), austin-multifamily
    # 9 (debate), austin-multifamily
    # 99 (invalid choice)
    # 1 (inspect with non-existent deal)
    # 0 (exit)
    interactive_stream = (
        "2\naustin-multifamily\n100\n"
        "3\naustin-multifamily\n100\n"
        "5\naustin-multifamily\n"
        "6\naustin-multifamily\ny\n"
        "7\naustin-multifamily\n0.15\nrent\n"
        "7\naustin-multifamily\n0.15\nprice\n"
        "8\naustin-multifamily\n"
        "9\naustin-multifamily\n"
        "99\n"
        "1\nnon-existent-deal\n"
        "0\n"
    )
    res = runner.invoke(cli, ["interactive"], input=interactive_stream)
    assert res.exit_code == 0
    assert "Investment Committee Memorandum" in res.output
    assert "Monte Carlo Stochastic Stress Test" in res.output
    assert "Levered IRR Sensitivity" in res.output
    assert "Real Estate Tax Analysis" in res.output
    assert "Required Market Rent Solution" in res.output
    assert "Deal Pricing & Hurdle Return Optimizer" in res.output
    assert "Autonomous Multi-Agent Deliberation & Debate" in res.output
    assert "Unknown option" in res.output
    assert "Deal 'non-existent-deal' not found." in res.output


def test_cli_error_handling_and_fallback_branches(tmp_path: Path):
    """Verify error branches for invalid deals, JSON flags, and command fallbacks."""
    runner = CliRunner()

    # 1. Underwrite with nonexistent deal
    res_uw = runner.invoke(cli, ["underwrite", "--deal-id", "non-existent-deal"])
    assert res_uw.exit_code != 0
    assert "not found" in res_uw.output

    # 2. Simulate with nonexistent deal
    res_sim = runner.invoke(cli, ["simulate", "--deal-id", "non-existent-deal"])
    assert res_sim.exit_code != 0
    assert "not found" in res_sim.output

    # 3. Waterfall with nonexistent deal
    res_wf = runner.invoke(cli, ["waterfall", "--deal-id", "non-existent-deal"])
    assert res_wf.exit_code != 0
    assert "not found" in res_wf.output

    # 4. Sensitivity with nonexistent deal
    res_sens = runner.invoke(cli, ["sensitivity", "--deal-id", "non-existent-deal"])
    assert res_sens.exit_code != 0
    assert "not found" in res_sens.output

    # 5. Tax with nonexistent deal
    res_tax = runner.invoke(cli, ["tax", "--deal-id", "non-existent-deal"])
    assert res_tax.exit_code != 0
    assert "not found" in res_tax.output

    # 6. Optimize with mode="rent" and --json
    res_opt_rent_json = runner.invoke(
        cli,
        ["optimize", "--deal-id", "austin-multifamily", "--mode", "rent", "--json"],
    )
    assert res_opt_rent_json.exit_code == 0
    data_rent = json.loads(res_opt_rent_json.output)
    assert "required_avg_market_rent" in data_rent

    # Optimize with nonexistent deal
    res_opt_none = runner.invoke(cli, ["optimize", "--deal-id", "non-existent-deal"])
    assert res_opt_none.exit_code != 0

    # 7. Audit with nonexistent deal and --json
    res_audit_none = runner.invoke(cli, ["audit", "--deal-id", "non-existent-deal"])
    assert res_audit_none.exit_code != 0

    res_audit_json = runner.invoke(cli, ["audit", "--deal-id", "austin-multifamily", "--json"])
    assert res_audit_json.exit_code == 0
    data_audit = json.loads(res_audit_json.output)
    assert "is_compliant" in data_audit
    assert "rules_checked" in data_audit

    # 8. Debate with nonexistent deal
    res_deb_none = runner.invoke(cli, ["debate", "--deal-id", "non-existent-deal"])
    assert res_deb_none.exit_code != 0

    # 9. Memo with nonexistent deal and memo to file
    res_memo_none = runner.invoke(cli, ["memo", "--deal-id", "non-existent-deal"])
    assert res_memo_none.exit_code != 0

    memo_file = tmp_path / "memo.md"
    res_memo_save = runner.invoke(
        cli,
        ["memo", "--deal-id", "austin-multifamily", "-o", str(memo_file), "-i", "50"],
    )
    assert res_memo_save.exit_code == 0
    assert memo_file.exists()

    # 10. Export formats to stdout and nonexistent deal
    res_exp_none = runner.invoke(cli, ["export", "--deal-id", "non-existent-deal"])
    assert res_exp_none.exit_code != 0

    res_exp_wf = runner.invoke(cli, ["export", "--deal-id", "austin-multifamily", "-f", "waterfall"])
    assert res_exp_wf.exit_code == 0
    assert "Total Distributable Cash" in res_exp_wf.output

    res_exp_sens = runner.invoke(cli, ["export", "--deal-id", "austin-multifamily", "-f", "sensitivity"])
    assert res_exp_sens.exit_code == 0
    assert "Rent Growth / Exit Cap" in res_exp_sens.output

    # Export to stdout (default format: cashflow CSV)
    res_exp_stdout = runner.invoke(cli, ["export", "--deal-id", "austin-multifamily"])
    assert res_exp_stdout.exit_code == 0
    assert "Gross Potential Rent" in res_exp_stdout.output

    # Export json to stdout
    res_exp_json = runner.invoke(cli, ["export", "--deal-id", "austin-multifamily", "-f", "json"])
    assert res_exp_json.exit_code == 0
    assert "austin-multifamily" in res_exp_json.output

    # 11. Deal group error paths
    res_deal_exp_none = runner.invoke(cli, ["deal", "export", "--deal-id", "non-existent-deal", "-o", str(tmp_path / "out.json")])
    assert res_deal_exp_none.exit_code != 0

    res_deal_del_none = runner.invoke(cli, ["deal", "delete", "--deal-id", "non-existent-deal"])
    assert "not found" in res_deal_del_none.output

    res_deal_rev_none = runner.invoke(cli, ["deal", "create-revision", "--deal-id", "non-existent-deal"])
    assert res_deal_rev_none.exit_code != 0

    res_deal_revert_none = runner.invoke(cli, ["deal", "revert", "--deal-id", "austin-multifamily", "--rev", "999"])
    assert "not found" in res_deal_revert_none.output

    res_deal_rev_empty = runner.invoke(cli, ["deal", "revisions", "--deal-id", "austin-multifamily"])
    assert res_deal_rev_empty.exit_code == 0
