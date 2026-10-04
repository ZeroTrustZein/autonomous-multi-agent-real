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
from autonomous_multi_agent_real.features.registry import (
    FeatureRegistry,
    get_default_registry,
)
from autonomous_multi_agent_real.features.extractor import (
    FeatureExtractor,
    WindowedAggregator,
)
from autonomous_multi_agent_real.features.storage import (
    ParquetFeatureStore,
)
from autonomous_multi_agent_real.features.buffer import (
    StreamFeatureBuffer,
)
from autonomous_multi_agent_real.features.quality import (
    FeatureQualityEngine,
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
    "FeatureRegistry",
    "get_default_registry",
    "FeatureExtractor",
    "WindowedAggregator",
    "ParquetFeatureStore",
    "StreamFeatureBuffer",
    "FeatureQualityEngine",
]

FEATURE_STORE_VERSION = "0.1.0"
