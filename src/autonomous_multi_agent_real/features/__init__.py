"""Real-time streaming feature extraction pipeline and Parquet columnar storage engine for real estate underwriting."""

from __future__ import annotations

from autonomous_multi_agent_real.features.types import (
    FeatureCategory,
    FeatureDataType,
    FeatureMetadata,
    FeatureQualityReport,
    FeatureRecord,
    FeatureStatistics,
    FeatureStreamEvent,
    FeatureStreamStatus,
    FeatureTimeWindow,
    FeatureValue,
    FeatureVector,
    ParquetPartitionSpec,
    PartitionStrategy,
    StreamBufferConfig,
    FeatureStoreManifest,
    feature_records_to_arrow_table,
    feature_vectors_to_arrow_table,
    to_arrow_schema,
)

__all__ = [
    "FEATURE_STORE_VERSION",
    "FeatureCategory",
    "FeatureDataType",
    "FeatureMetadata",
    "FeatureQualityReport",
    "FeatureRecord",
    "FeatureStatistics",
    "FeatureStreamEvent",
    "FeatureStreamStatus",
    "FeatureTimeWindow",
    "FeatureValue",
    "FeatureVector",
    "ParquetPartitionSpec",
    "PartitionStrategy",
    "StreamBufferConfig",
    "FeatureStoreManifest",
    "feature_records_to_arrow_table",
    "feature_vectors_to_arrow_table",
    "to_arrow_schema",
]

FEATURE_STORE_VERSION = "0.1.0"

