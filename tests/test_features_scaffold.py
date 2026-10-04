"""Scaffolding tests for real-time feature store and streaming extraction pipeline."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa

import autonomous_multi_agent_real.features as features


def test_feature_store_scaffold_metadata():
    """Verify feature store module is discoverable and exports version."""
    assert hasattr(features, "FEATURE_STORE_VERSION")
    assert features.FEATURE_STORE_VERSION == "0.1.0"


def test_pyarrow_integration_environment():
    """Verify PyArrow engine is available and functional."""
    table = pa.Table.from_arrays([pa.array([1, 2, 3])], names=["feature_id"])
    assert table.num_rows == 3
    assert table.num_columns == 1


def test_pyproject_contains_feature_store_dependencies():
    """Verify pyproject.toml includes pyarrow requirement."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")
    assert "pyarrow>=14.0.0" in content


def test_gitignore_contains_feature_store_artifacts():
    """Verify .gitignore ignores parquet and feature store directories."""
    gitignore_path = Path(__file__).resolve().parent.parent / ".gitignore"
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    assert "*.parquet" in content
    assert "feature_store/" in content


def test_env_example_contains_feature_store_configs():
    """Verify .env.example contains feature store settings."""
    env_example_path = Path(__file__).resolve().parent.parent / ".env.example"
    assert env_example_path.exists()
    content = env_example_path.read_text(encoding="utf-8")
    assert "FEATURE_STORE_PATH" in content
    assert "FEATURE_STREAM_BUFFER_SIZE" in content
