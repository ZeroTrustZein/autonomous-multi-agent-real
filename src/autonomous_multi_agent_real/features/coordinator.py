"""Unified coordinator facade orchestrating all feature store subsystems."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from autonomous_multi_agent_real.features.buffer import StreamFeatureBuffer
from autonomous_multi_agent_real.features.enricher import FeatureContextEnricher
from autonomous_multi_agent_real.features.extractor import FeatureExtractor
from autonomous_multi_agent_real.features.interceptor import PipelineFeatureInterceptor
from autonomous_multi_agent_real.features.materialization import MaterializationEngine
from autonomous_multi_agent_real.features.quality import FeatureQualityEngine
from autonomous_multi_agent_real.features.registry import FeatureRegistry, get_default_registry
from autonomous_multi_agent_real.features.serving import FeatureServingService, OnlineFeatureStore
from autonomous_multi_agent_real.features.storage import ParquetFeatureStore
from autonomous_multi_agent_real.features.training import TrainingDataset, TrainingDatasetGenerator
from autonomous_multi_agent_real.features.types import (
    EnrichedFeatureContext,
    FeatureQualityReport,
    FeatureVector,
    MaterializationJob,
    ObservationTarget,
    OnlineStoreConfig,
    ParquetPartitionSpec,
    StreamBufferConfig,
    table_to_safe_pydict,
)
from autonomous_multi_agent_real.types import PropertyDeal


class FeatureStoreCoordinator:
    """Master subsystem coordinator providing high-level feature operations."""

    def __init__(
        self,
        base_path: Union[str, Path],
        registry: Optional[FeatureRegistry] = None,
        partition_spec: Optional[ParquetPartitionSpec] = None,
        online_config: Optional[OnlineStoreConfig] = None,
        buffer_config: Optional[StreamBufferConfig] = None,
    ) -> None:
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.registry = registry or get_default_registry()
        self.extractor = FeatureExtractor(registry=self.registry)
        self.quality_engine = FeatureQualityEngine(registry=self.registry)
        self.offline_store = ParquetFeatureStore(
            base_path=self.base_path / "offline",
            partition_spec=partition_spec,
        )
        self.online_store = OnlineFeatureStore(config=online_config)
        self.buffer = StreamFeatureBuffer(
            config=buffer_config,
        )

        self.serving_service = FeatureServingService(
            online_store=self.online_store,
            offline_store=self.offline_store,
            registry=self.registry,
        )

        self.materialization_engine = MaterializationEngine(
            offline_store=self.offline_store,
            online_store=self.online_store,
            buffer=self.buffer,
            extractor=self.extractor,
        )

        self.training_generator = TrainingDatasetGenerator(
            offline_store=self.offline_store,
            registry=self.registry,
        )

        self.enricher = FeatureContextEnricher(
            extractor=self.extractor,
            online_store=self.online_store,
            offline_store=self.offline_store,
        )

        self.interceptor = PipelineFeatureInterceptor(
            extractor=self.extractor,
            buffer=self.buffer,
            online_store=self.online_store,
            offline_store=self.offline_store,
        )

    def extract_and_persist(
        self,
        deal: PropertyDeal,
        context: Optional[Any] = None,
        sync_online: bool = True,
    ) -> FeatureVector:
        """Extract deal features, write to offline Parquet, and optionally update online cache."""
        vector = self.extractor.extract_deal_features(deal, context=context)
        records = self.extractor.extract_deal_records(deal, context=context)

        self.offline_store.write_vectors([vector])
        if records:
            self.offline_store.write_records(records)

        if sync_online:
            self.online_store.put_vector(vector)

        return vector

    def get_features(
        self,
        entity_id: str,
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
    ) -> Dict[str, Any]:
        """Serve features with online-first lookup and offline fallback."""
        return self.serving_service.get_online_features(
            entity_id=entity_id,
            feature_names=feature_names,
            entity_type=entity_type,
            fallback_to_offline=fallback_to_offline,
        )

    def get_feature_vector(
        self,
        entity_id: str,
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
    ) -> Optional[FeatureVector]:
        """Retrieve full feature vector for an entity."""
        return self.serving_service.get_feature_vector(
            entity_id=entity_id,
            entity_type=entity_type,
            fallback_to_offline=fallback_to_offline,
        )

    def get_batch_features(
        self,
        entity_ids: Sequence[str],
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
    ) -> Dict[str, Dict[str, Any]]:
        """Batch retrieve features across multiple entities."""
        return self.serving_service.get_batch_features(
            entity_ids=entity_ids,
            feature_names=feature_names,
            entity_type=entity_type,
        )

    def get_feature_matrix(
        self,
        entity_ids: Sequence[str],
        feature_names: Sequence[str],
        entity_type: str = "deal",
    ) -> Dict[str, List[Any]]:
        """Retrieve column-oriented feature matrix for ML model scoring."""
        return self.serving_service.get_feature_matrix(
            entity_ids=entity_ids,
            feature_names=feature_names,
            entity_type=entity_type,
        )

    def enrich_deal(
        self,
        deal: PropertyDeal,
        cohort_deals: Optional[Sequence[PropertyDeal]] = None,
        cohort_name: str = "market_peers",
    ) -> EnrichedFeatureContext:
        """Enrich deal with benchmark percentiles, z-scores, and medians."""
        return self.enricher.enrich_deal(
            deal=deal,
            cohort_deals=cohort_deals,
            cohort_name=cohort_name,
        )

    def materialize_to_online(
        self,
        start_time: Optional[Any] = None,
        end_time: Optional[Any] = None,
        entity_ids: Optional[Sequence[str]] = None,
    ) -> MaterializationJob:
        """Hydrate online store from offline store."""
        return self.materialization_engine.materialize_to_online(
            start_time=start_time,
            end_time=end_time,
            entity_ids=entity_ids,
        )

    def flush_buffer(self) -> MaterializationJob:
        """Flush streaming buffer to offline Parquet storage."""
        return self.materialization_engine.flush_buffer_to_parquet()

    def backfill_deals(
        self,
        deals: Sequence[PropertyDeal],
        sync_online: bool = True,
    ) -> MaterializationJob:
        """Extract and persist features across historical deals."""
        return self.materialization_engine.backfill_deals(
            deals=deals,
            sync_online=sync_online,
        )

    def build_training_dataset(
        self,
        observations: Sequence[ObservationTarget],
        dataset_name: str,
        feature_names: Optional[Sequence[str]] = None,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> TrainingDataset:
        """Generate point-in-time training dataset without data leakage."""
        return self.training_generator.build_dataset(
            observations=observations,
            dataset_name=dataset_name,
            feature_names=feature_names,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
        )

    def audit_quality(
        self,
        entity_ids: Optional[Sequence[str]] = None,
    ) -> FeatureQualityReport:
        """Run statistical quality audit on stored features."""
        table = self.offline_store.query(entity_ids=entity_ids)
        if table.num_rows == 0:
            return FeatureQualityReport(
                dataset_name="offline_feature_store",
                total_records=0,
                valid_records=0,
                invalid_records=0,
                overall_quality_score=1.0,
            )

        pydict = table_to_safe_pydict(table)
        unique_eids = sorted(set(pydict["entity_id"]))
        vectors: List[FeatureVector] = []
        for eid in unique_eids:
            v = self.offline_store.get_latest_vector(eid)
            if v:
                vectors.append(v)

        return self.quality_engine.audit_dataset(
            vectors=vectors,
            dataset_name="offline_feature_store",
        )

    def audit_sync(self) -> Dict[str, Any]:
        """Audit parity between online and offline stores."""
        return self.materialization_engine.sync_audit()

    def get_status(self) -> Dict[str, Any]:
        """Return operational telemetry across offline, online, and buffer tiers."""
        buf_metrics = self.buffer.get_status()
        manifest = self.offline_store.get_manifest()
        return {
            "offline_store": {
                "base_path": str(self.base_path),
                "total_files": manifest.total_files,
                "total_records": manifest.total_records,
                "entity_count": len(self.offline_store.list_entities()),
            },
            "online_store": {
                "cached_entities": self.online_store.size(),
                "max_capacity": self.online_store.config.max_entries,
                "eviction_policy": getattr(
                    self.online_store.config.eviction_policy,
                    "value",
                    str(self.online_store.config.eviction_policy),
                ),
                "ttl_seconds": self.online_store.config.ttl_seconds,
            },
            "buffer": {
                "records_in_buffer": buf_metrics.records_in_buffer,
                "buffer_capacity": self.buffer.capacity,
                "buffer_utilization": buf_metrics.buffer_utilization,
                "total_records_ingested": buf_metrics.total_records_ingested,
                "total_flushes": buf_metrics.total_flushes,
                "dropped_records": buf_metrics.dropped_records,
                "is_healthy": buf_metrics.is_healthy,
            },
        }

    def get_pipeline_interceptor(self) -> PipelineFeatureInterceptor:
        """Retrieve configured pipeline interceptor hook."""
        return self.interceptor


def create_feature_store(
    base_path: Union[str, Path, None] = None,
    registry: Optional[FeatureRegistry] = None,
) -> FeatureStoreCoordinator:
    """Convenience factory creating a feature store coordinator."""
    if base_path is None:
        base_path = Path(".feature_store").resolve()
    return FeatureStoreCoordinator(base_path=base_path, registry=registry)
