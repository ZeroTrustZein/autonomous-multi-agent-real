"""Real-time streaming feature extraction pipeline and Parquet columnar storage engine for real estate underwriting."""

from __future__ import annotations

from autonomous_multi_agent_real.features.buffer import (
    StreamFeatureBuffer,
)
from autonomous_multi_agent_real.features.coordinator import (
    FeatureStoreCoordinator,
    create_feature_store,
)
from autonomous_multi_agent_real.features.enricher import (
    FeatureContextEnricher,
)
from autonomous_multi_agent_real.features.extractor import (
    FeatureExtractor,
    WindowedAggregator,
)
from autonomous_multi_agent_real.features.interceptor import (
    PipelineFeatureInterceptor,
)
from autonomous_multi_agent_real.features.materialization import (
    MaterializationEngine,
)
from autonomous_multi_agent_real.features.quality import (
    FeatureQualityEngine,
)
from autonomous_multi_agent_real.features.registry import (
    FeatureRegistry,
    get_default_registry,
)
from autonomous_multi_agent_real.features.serving import (
    FeatureServingService,
    OnlineFeatureStore,
)
from autonomous_multi_agent_real.features.storage import (
    ParquetFeatureStore,
)
from autonomous_multi_agent_real.features.training import (
    TrainingDataset,
    TrainingDatasetGenerator,
)
from autonomous_multi_agent_real.features.types import (
    EnrichedFeatureContext,
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
    MaterializationJob,
    ObservationTarget,
    OnlineStoreConfig,
    ParquetPartitionSpec,
    PartitionStrategy,
    StreamBufferConfig,
    TrainingDatasetMetadata,
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
    "OnlineStoreConfig",
    "MaterializationJob",
    "ObservationTarget",
    "TrainingDatasetMetadata",
    "EnrichedFeatureContext",
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
    "OnlineFeatureStore",
    "FeatureServingService",
    "MaterializationEngine",
    "TrainingDataset",
    "TrainingDatasetGenerator",
    "FeatureContextEnricher",
    "PipelineFeatureInterceptor",
    "FeatureStoreCoordinator",
    "create_feature_store",
]

FEATURE_STORE_VERSION = "0.1.0"
