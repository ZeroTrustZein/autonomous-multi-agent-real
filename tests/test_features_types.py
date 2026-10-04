"""Unit and integration tests for feature store domain models and type system (Stage 2/10: Types)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pyarrow as pa
import pytest
from pydantic import ValidationError

from autonomous_multi_agent_real.features.types import (
    FeatureCategory,
    FeatureDataType,
    FeatureMetadata,
    FeatureQualityReport,
    FeatureRecord,
    FeatureStatistics,
    FeatureStoreManifest,
    FeatureStreamEvent,
    FeatureStreamStatus,
    FeatureTimeWindow,
    FeatureValue,
    FeatureVector,
    ParquetPartitionSpec,
    PartitionStrategy,
    StreamBufferConfig,
    feature_records_to_arrow_table,
    feature_vectors_to_arrow_table,
    to_arrow_schema,
)


def test_feature_data_type_enum_and_arrow_conversion():
    """Verify FeatureDataType enums map to proper PyArrow types."""
    assert FeatureDataType.FLOAT.value == "float"
    assert FeatureDataType.FLOAT.to_arrow_type() == pa.float64()
    assert FeatureDataType.INT.to_arrow_type() == pa.int64()
    assert FeatureDataType.STRING.to_arrow_type() == pa.string()
    assert FeatureDataType.BOOLEAN.to_arrow_type() == pa.bool_()
    assert FeatureDataType.TIMESTAMP.to_arrow_type() == pa.timestamp("ms", tz="UTC")
    assert FeatureDataType.VECTOR.to_arrow_type() == pa.list_(pa.float64())
    assert FeatureDataType.JSON.to_arrow_type() == pa.string()


def test_feature_categories_and_windows():
    """Verify domain categories, partition strategies, and time windows."""
    assert FeatureCategory.FINANCIAL.value == "financial"
    assert FeatureCategory.PROPERTY.value == "property"
    assert FeatureCategory.RISK.value == "risk"
    assert FeatureCategory.DEBT.value == "debt"
    assert FeatureCategory.MARKET.value == "market"

    assert FeatureTimeWindow.REALTIME.value == "realtime"
    assert FeatureTimeWindow.DAILY.value == "24h"
    assert FeatureTimeWindow.ANNUAL.value == "365d"

    assert PartitionStrategy.PROPERTY_TYPE.value == "property_type"
    assert PartitionStrategy.VINTAGE_YEAR.value == "vintage_year"


def test_feature_metadata_creation_and_arrow_field():
    """Test FeatureMetadata validation, defaults, and PyArrow field export."""
    meta = FeatureMetadata(
        name="debt_service_coverage_ratio",
        data_type=FeatureDataType.FLOAT,
        category=FeatureCategory.DEBT,
        description="Underwritten annual net operating income divided by total debt service",
        unit="ratio",
        tags=["debt", "underwriting", "solvency"],
    )

    assert meta.name == "debt_service_coverage_ratio"
    assert meta.entity_key == "deal_id"
    assert meta.version == "1.0.0"
    assert meta.is_nullable is True
    assert meta.unit == "ratio"

    arrow_field = meta.to_arrow_field()
    assert isinstance(arrow_field, pa.Field)
    assert arrow_field.name == "debt_service_coverage_ratio"
    assert arrow_field.type == pa.float64()
    assert arrow_field.nullable is True
    assert arrow_field.metadata[b"category"] == b"debt"
    assert arrow_field.metadata[b"unit"] == b"ratio"


def test_feature_metadata_validation_empty_name():
    """Verify validation error when feature name is whitespace or empty."""
    with pytest.raises(ValidationError):
        FeatureMetadata(
            name="   ",
            data_type=FeatureDataType.FLOAT,
            category=FeatureCategory.FINANCIAL,
        )


def test_feature_value_confidence_bounds():
    """Verify FeatureValue bounds enforcement for confidence parameter."""
    val = FeatureValue(
        feature_name="exit_cap_rate",
        value=0.0575,
        confidence=0.95,
    )
    assert val.confidence == 0.95
    assert val.value == 0.0575

    with pytest.raises(ValidationError):
        FeatureValue(
            feature_name="exit_cap_rate",
            value=0.0575,
            confidence=1.5,  # Exceeds 1.0 limit
        )

    with pytest.raises(ValidationError):
        FeatureValue(
            feature_name="exit_cap_rate",
            value=0.0575,
            confidence=-0.1,  # Below 0.0 limit
        )


def test_feature_record_initialization():
    """Verify FeatureRecord atomic observation model."""
    record = FeatureRecord(
        entity_id="deal-austin-101",
        feature_name="gross_potential_rent",
        value=150000.0,
        source="underwriting_agent",
        partition_key="multi_family/2024",
    )
    assert record.entity_id == "deal-austin-101"
    assert record.entity_type == "deal"
    assert record.feature_name == "gross_potential_rent"
    assert record.value == 150000.0
    assert record.partition_key == "multi_family/2024"


def test_feature_vector_operations():
    """Verify FeatureVector lookup and numeric vector conversion."""
    vector = FeatureVector(
        entity_id="deal-dallas-202",
        features={
            "loan_to_value": 0.65,
            "dscr": 1.45,
            "occupancy_rate": 0.94,
            "is_stabilized": True,
            "metro": "Dallas-Fort Worth",
        },
    )

    assert vector.has_feature("dscr")
    assert not vector.has_feature("non_existent")
    assert vector.get("loan_to_value") == 0.65
    assert vector.get("missing_key", default=0.0) == 0.0

    # Ordered extraction
    ordered_keys = ["dscr", "is_stabilized", "loan_to_value", "missing"]
    num_array = vector.to_numeric_array(ordered_keys)
    assert num_array == [1.45, 1.0, 0.65, 0.0]

    # Default extraction (sorted keys)
    default_array = vector.to_numeric_array()
    assert len(default_array) == 5


def test_feature_stream_event_lifecycle():
    """Verify streaming event structure, default uuid, and status progression."""
    event = FeatureStreamEvent(
        entity_id="deal-miami-303",
        payload={"in_place_noi": 420000.0, "cap_rate": 0.062},
    )

    assert event.event_id is not None
    assert len(event.event_id) > 0
    assert event.status == FeatureStreamStatus.BUFFERED
    assert event.retry_count == 0

    event.status = FeatureStreamStatus.STREAMING
    assert event.status == FeatureStreamStatus.STREAMING


def test_stream_buffer_and_parquet_partition_configs():
    """Verify stream buffer sizing and parquet storage partition specifications."""
    buf_cfg = StreamBufferConfig(buffer_size=500, flush_interval_seconds=2.5)
    assert buf_cfg.buffer_size == 500
    assert buf_cfg.flush_interval_seconds == 2.5
    assert buf_cfg.max_retries == 3

    pq_spec = ParquetPartitionSpec()
    assert "property_type" in pq_spec.partition_columns
    assert "vintage_year" in pq_spec.partition_columns
    assert pq_spec.compression == "snappy"
    assert pq_spec.row_group_size == 10000


def test_feature_manifest_and_statistics():
    """Verify catalog manifest tracking and distribution statistics."""
    manifest = FeatureStoreManifest(
        dataset_id="cre_underwriting_v1",
        store_path="/var/data/cre_features",
        total_records=1200,
        total_files=4,
        partition_keys=["multi_family/2023", "multi_family/2024"],
        feature_names=["noi", "cap_rate", "dscr", "ltv"],
    )
    assert manifest.total_records == 1200
    assert manifest.total_files == 4
    assert len(manifest.partition_keys) == 2

    stats = FeatureStatistics(
        feature_name="debt_yield",
        count=100,
        null_count=5,
        min_value=0.075,
        max_value=0.142,
        mean=0.105,
        std_dev=0.015,
        p50=0.102,
    )
    assert stats.null_rate == 0.05
    assert stats.mean == 0.105

    empty_stats = FeatureStatistics(feature_name="empty", count=0, null_count=0)
    assert empty_stats.null_rate == 0.0


def test_feature_quality_report():
    """Verify FeatureQualityReport tracking discrepancies and null violations."""
    report = FeatureQualityReport(
        is_valid=False,
        total_features_checked=15,
        missing_features=["market_rent_growth_1yr"],
        null_rate_violations={"expense_ratio": 0.25},
        range_violations={"cap_rate": "Value -0.01 outside valid range [0.01, 0.30]"},
    )
    assert not report.is_valid
    assert len(report.missing_features) == 1
    assert "expense_ratio" in report.null_rate_violations
    assert "cap_rate" in report.range_violations


def test_to_arrow_schema_generation():
    """Verify generating pa.Schema from FeatureMetadata sequence."""
    metadata_list = [
        FeatureMetadata(
            name="cap_rate",
            data_type=FeatureDataType.FLOAT,
            category=FeatureCategory.FINANCIAL,
        ),
        FeatureMetadata(
            name="unit_count",
            data_type=FeatureDataType.INT,
            category=FeatureCategory.PROPERTY,
        ),
        FeatureMetadata(
            name="city",
            data_type=FeatureDataType.STRING,
            category=FeatureCategory.LOCATION,
        ),
    ]

    schema = to_arrow_schema(metadata_list)
    assert isinstance(schema, pa.Schema)
    # entity_id and timestamp are auto-prepended
    assert schema.names == ["entity_id", "timestamp", "cap_rate", "unit_count", "city"]
    assert schema.field("entity_id").type == pa.string()
    assert schema.field("timestamp").type == pa.timestamp("ms", tz="UTC")
    assert schema.field("cap_rate").type == pa.float64()
    assert schema.field("unit_count").type == pa.int64()
    assert schema.field("city").type == pa.string()


def test_feature_vectors_to_arrow_table_inferred_and_explicit():
    """Verify converting FeatureVectors into PyArrow Table with both inferred and explicit schemas."""
    now = datetime.now(timezone.utc)
    v1 = FeatureVector(
        entity_id="deal-1",
        features={"noi": 100000.0, "dscr": 1.35},
        timestamp=now,
    )
    v2 = FeatureVector(
        entity_id="deal-2",
        features={"noi": 200000.0, "dscr": 1.55},
        timestamp=now,
    )

    # Inferred schema conversion
    table_inferred = feature_vectors_to_arrow_table([v1, v2])
    assert table_inferred.num_rows == 2
    assert "noi" in table_inferred.column_names
    assert "dscr" in table_inferred.column_names
    assert "entity_id" in table_inferred.column_names

    # Explicit schema conversion
    explicit_schema = pa.schema(
        [
            pa.field("entity_id", pa.string()),
            pa.field("timestamp", pa.timestamp("ms", tz="UTC")),
            pa.field("noi", pa.float64()),
        ]
    )
    table_explicit = feature_vectors_to_arrow_table([v1, v2], schema=explicit_schema)
    assert table_explicit.num_rows == 2
    assert table_explicit.column_names == ["entity_id", "timestamp", "noi"]
    assert table_explicit.column("noi").to_pylist() == [100000.0, 200000.0]

    # Empty vectors conversion
    empty_table = feature_vectors_to_arrow_table([])
    assert empty_table.num_rows == 0


def test_feature_records_to_arrow_table():
    """Verify converting atomic FeatureRecord list to PyArrow Table."""
    now = datetime.now(timezone.utc)
    r1 = FeatureRecord(
        entity_id="deal-10",
        feature_name="metrics",
        value={"irr": 0.18, "equity_multiple": 2.1},
        timestamp=now,
        source="risk_agent",
    )
    r2 = FeatureRecord(
        entity_id="deal-10",
        feature_name="status",
        value="approved",
        timestamp=now,
        source="committee",
    )

    table = feature_records_to_arrow_table([r1, r2])
    assert table.num_rows == 2
    assert table.column_names == [
        "entity_id",
        "entity_type",
        "feature_name",
        "value_str",
        "timestamp",
        "source",
        "partition_key",
    ]
    # Verify complex json serialization in value_str
    val_strs = table.column("value_str").to_pylist()
    parsed_json = json.loads(val_strs[0])
    assert parsed_json["irr"] == 0.18
    assert val_strs[1] == "approved"

    empty_records_table = feature_records_to_arrow_table([])
    assert empty_records_table.num_rows == 0
