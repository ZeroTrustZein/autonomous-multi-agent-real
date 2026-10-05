"""Comprehensive test suite for Stage 5: CLI and terminal interfaces for Feature Store."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from autonomous_multi_agent_real.cli.main import cli


@pytest.fixture
def cli_temp_dir():
    """Create a temporary directory for CLI feature store operations."""
    d = tempfile.mkdtemp(prefix="cli_fs_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_cli_features_help():
    """Verify feature store group help lists all subcommands."""
    runner = CliRunner()
    res = runner.invoke(cli, ["features", "--help"])
    assert res.exit_code == 0
    assert "Real-time institutional feature store management" in res.output
    assert "status" in res.output
    assert "list" in res.output
    assert "show" in res.output
    assert "inspect" in res.output
    assert "backfill" in res.output
    assert "sync" in res.output
    assert "audit" in res.output
    assert "dataset" in res.output


def test_cli_features_status(cli_temp_dir):
    """Verify feature store status display."""
    runner = CliRunner()
    res = runner.invoke(cli, ["features", "status", "--store-path", str(cli_temp_dir)])
    assert res.exit_code == 0
    assert "Institutional Feature Store - Infrastructure Telemetry" in res.output
    assert "Offline Parquet Data Lake" in res.output
    assert "Online Low-Latency Key-Value Cache" in res.output
    assert "Real-Time Streaming Buffer" in res.output


def test_cli_features_list():
    """Verify listing registered features with and without category/tag filters."""
    runner = CliRunner()

    # 1. Full list
    res = runner.invoke(cli, ["features", "list"])
    assert res.exit_code == 0
    assert "Registered Features" in res.output
    assert "unit_count" in res.output
    assert "in_place_noi" in res.output
    assert "in_place_cap_rate" in res.output

    # 2. Category filter
    res_debt = runner.invoke(cli, ["features", "list", "--category", "debt"])
    assert res_debt.exit_code == 0
    assert "ltv_ratio" in res_debt.output or "dscr_year1" in res_debt.output

    # 3. Tag filter
    res_yield = runner.invoke(cli, ["features", "list", "--tag", "yield"])
    assert res_yield.exit_code == 0
    assert "in_place_cap_rate" in res_yield.output


def test_cli_features_show():
    """Verify inspecting single feature metadata definition."""
    runner = CliRunner()

    # Existing feature
    res = runner.invoke(cli, ["features", "show", "in_place_noi"])
    assert res.exit_code == 0
    assert "Feature Specification: in_place_noi" in res.output
    assert "Data Type" in res.output
    assert "Allowed Range" in res.output

    # Unknown feature error handling
    res_err = runner.invoke(cli, ["features", "show", "non_existent_feature_xyz"])
    assert res_err.exit_code != 0
    assert "not found in registry" in res_err.output


def test_cli_features_inspect_and_backfill(cli_temp_dir):
    """Verify backfilling deals into feature store and inspecting entity vectors."""
    runner = CliRunner()

    # 1. Backfill a specific deal
    res_bf = runner.invoke(
        cli,
        ["features", "backfill", "--store-path", str(cli_temp_dir), "--deal-id", "austin-multifamily"],
    )
    assert res_bf.exit_code == 0
    assert "Backfilling features across 1 deals" in res_bf.output
    assert "completed" in res_bf.output

    # 2. Inspect entity features from store
    res_insp = runner.invoke(
        cli,
        ["features", "inspect", "austin-multifamily", "--store-path", str(cli_temp_dir)],
    )
    assert res_insp.exit_code == 0
    assert "Feature Vector: austin-multifamily" in res_insp.output
    assert "unit_count" in res_insp.output
    assert "purchase_price" in res_insp.output

    # 3. Inspect dynamically from deal definition
    res_dyn = runner.invoke(
        cli,
        ["features", "inspect", "austin-multifamily", "--from-deal"],
    )
    assert res_dyn.exit_code == 0
    assert "Feature Vector: austin-multifamily" in res_dyn.output

    # 4. Unknown entity in store
    res_un = runner.invoke(
        cli,
        ["features", "inspect", "unknown-deal-999", "--store-path", str(cli_temp_dir)],
    )
    assert res_un.exit_code == 0
    assert "No features found for entity" in res_un.output


def test_cli_features_sync_and_audit(cli_temp_dir):
    """Verify buffer flush, online sync, and quality audit commands."""
    runner = CliRunner()

    # Backfill first so data exists
    runner.invoke(cli, ["features", "backfill", "--store-path", str(cli_temp_dir)])

    # Sync
    res_sync = runner.invoke(cli, ["features", "sync", "--store-path", str(cli_temp_dir)])
    assert res_sync.exit_code == 0
    assert "Materialization completed" in res_sync.output

    # Audit
    res_audit = runner.invoke(cli, ["features", "audit", "--store-path", str(cli_temp_dir)])
    assert res_audit.exit_code == 0
    assert "Feature Quality Audit" in res_audit.output
    assert "Parity Audit" in res_audit.output


def test_cli_features_dataset_compilation(cli_temp_dir):
    """Verify compiling training dataset with export option."""
    runner = CliRunner()
    export_out = cli_temp_dir / "compiled_dataset"

    res = runner.invoke(
        cli,
        [
            "features",
            "dataset",
            "--store-path",
            str(cli_temp_dir),
            "--name",
            "noi_forecasting",
            "--target",
            "in_place_noi",
            "--out-dir",
            str(export_out),
        ],
    )
    assert res.exit_code == 0
    assert "Point-In-Time Training Dataset Compilation" in res.output
    assert "Total Observations" in res.output
    assert "Dataset exported to" in res.output
    assert export_out.exists()


def test_cli_interactive_features_option():
    """Verify interactive wizard choice 11 (Feature Store Explorer)."""
    runner = CliRunner()
    # Choice 11 (feature store), then sub-action 1 (inspect deal vector), deal austin-multifamily, then choice 0 (exit)
    commands_input = "11\n1\naustin-multifamily\n0\n"
    res = runner.invoke(cli, ["interactive"], input=commands_input)
    assert res.exit_code == 0
    assert "Institutional Feature Store - Infrastructure Telemetry" in res.output
    assert "Feature Vector: austin-multifamily" in res.output
    assert "Exiting interactive session." in res.output
