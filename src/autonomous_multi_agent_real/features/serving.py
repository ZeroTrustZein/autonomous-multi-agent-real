"""Low-latency online feature serving and multi-tier feature retrieval engine."""

from __future__ import annotations

import collections
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

from autonomous_multi_agent_real.features.registry import FeatureRegistry, get_default_registry
from autonomous_multi_agent_real.features.storage import ParquetFeatureStore
from autonomous_multi_agent_real.features.types import (
    FeatureMetadata,
    FeatureRecord,
    FeatureVector,
    OnlineStoreConfig,
)


class OnlineFeatureStore:
    """Thread-safe, low-latency in-memory feature cache with TTL and LRU/FIFO eviction."""

    def __init__(self, config: Optional[OnlineStoreConfig] = None) -> None:
        self.config = config or OnlineStoreConfig()
        self._lock = threading.RLock()
        self._store: collections.OrderedDict[str, tuple[FeatureVector, float]] = collections.OrderedDict()
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    def put_vector(self, vector: FeatureVector) -> None:
        """Upsert a feature vector into the online cache."""
        with self._lock:
            key = f"{vector.entity_type}:{vector.entity_id}"
            now = time.time()

            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = (vector, now)
                return

            # Check capacity limits
            if len(self._store) >= self.config.max_entries:
                self._evict_one()

            self._store[key] = (vector, now)

    def put_vectors(self, vectors: Sequence[FeatureVector]) -> None:
        """Batch upsert feature vectors."""
        with self._lock:
            for vec in vectors:
                self.put_vector(vec)

    def put_records(self, records: Sequence[FeatureRecord]) -> None:
        """Merge atomic feature records into existing cached vector or create new vector."""
        if not records:
            return

        with self._lock:
            grouped: Dict[tuple[str, str], List[FeatureRecord]] = {}
            for rec in records:
                grouped.setdefault((rec.entity_type, rec.entity_id), []).append(rec)

            for (e_type, e_id), recs in grouped.items():
                existing_vec = self.get_vector(e_id, entity_type=e_type, check_ttl=False)
                features: Dict[str, Any] = dict(existing_vec.features) if existing_vec else {}
                latest_ts = existing_vec.timestamp if existing_vec else datetime.now(timezone.utc)

                for r in recs:
                    features[r.feature_name] = r.value
                    if r.timestamp > latest_ts:
                        latest_ts = r.timestamp

                new_vec = FeatureVector(
                    entity_id=e_id,
                    entity_type=e_type,
                    features=features,
                    timestamp=latest_ts,
                    schema_version="1.0.0",
                )
                self.put_vector(new_vec)

    def get_vector(
        self,
        entity_id: str,
        entity_type: str = "deal",
        check_ttl: bool = True,
    ) -> Optional[FeatureVector]:
        """Retrieve a cached feature vector by entity ID."""
        with self._lock:
            key = f"{entity_type}:{entity_id}"
            if key not in self._store:
                self._misses += 1
                return None

            vector, insertion_time = self._store[key]

            # Evaluate TTL freshness
            if check_ttl and self.config.ttl_seconds is not None:
                if (time.time() - insertion_time) > self.config.ttl_seconds:
                    del self._store[key]
                    self._misses += 1
                    self._evictions += 1
                    return None

            self._hits += 1
            if self.config.eviction_policy == "lru":
                self._store.move_to_end(key)
            return vector

    def get_vectors(
        self,
        entity_ids: Sequence[str],
        entity_type: str = "deal",
        check_ttl: bool = True,
    ) -> List[FeatureVector]:
        """Batch retrieve cached vectors."""
        with self._lock:
            results: List[FeatureVector] = []
            for eid in entity_ids:
                vec = self.get_vector(eid, entity_type=entity_type, check_ttl=check_ttl)
                if vec is not None:
                    results.append(vec)
            return results

    def invalidate(self, entity_id: str, entity_type: str = "deal") -> bool:
        """Evict a specific entity vector from cache."""
        with self._lock:
            key = f"{entity_type}:{entity_id}"
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries in the online store."""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Return the current number of cached entities."""
        with self._lock:
            return len(self._store)

    def keys(self) -> List[str]:
        """List cached entity keys."""
        with self._lock:
            return list(self._store.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Provide cache health, hit rate, and telemetry statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0
            return {
                "active_entries": len(self._store),
                "max_entries": self.config.max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total_requests,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "ttl_seconds": self.config.ttl_seconds,
                "eviction_policy": self.config.eviction_policy,
            }

    def _evict_one(self) -> None:
        """Evict oldest item according to eviction policy."""
        if not self._store:
            return
        # Pop from beginning (oldest access in LRU or oldest insertion in FIFO)
        self._store.popitem(last=False)
        self._evictions += 1


class FeatureServingService:
    """Unified feature retrieval facade supporting online caching, offline fallback, and registry defaults."""

    def __init__(
        self,
        online_store: OnlineFeatureStore,
        offline_store: Optional[ParquetFeatureStore] = None,
        registry: Optional[FeatureRegistry] = None,
    ) -> None:
        self.online_store = online_store
        self.offline_store = offline_store
        self.registry = registry or get_default_registry()

    def get_feature_vector(
        self,
        entity_id: str,
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
    ) -> Optional[FeatureVector]:
        """Retrieve full feature vector, attempting online cache first, then falling back to Parquet."""
        vec = self.online_store.get_vector(entity_id, entity_type=entity_type)
        if vec is not None:
            return vec

        if fallback_to_offline and self.offline_store is not None:
            offline_vec = self.offline_store.get_latest_vector(entity_id, entity_type=entity_type)
            if offline_vec is not None:
                # Hydrate online cache
                self.online_store.put_vector(offline_vec)
                return offline_vec

        return None

    def get_online_features(
        self,
        entity_id: str,
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
        fill_missing: bool = True,
    ) -> Dict[str, Any]:
        """Retrieve specific named features for an entity with imputation and default handling."""
        vec = self.get_feature_vector(
            entity_id=entity_id,
            entity_type=entity_type,
            fallback_to_offline=fallback_to_offline,
        )

        extracted: Dict[str, Any] = dict(vec.features) if vec else {}

        if feature_names is None:
            return extracted

        projected: Dict[str, Any] = {}
        for name in feature_names:
            val = extracted.get(name)
            if val is None and fill_missing:
                meta = self.registry.get(name)
                if meta and meta.default_value is not None:
                    val = meta.default_value
            projected[name] = val

        return projected

    def get_batch_features(
        self,
        entity_ids: Sequence[str],
        feature_names: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
        fill_missing: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Batch retrieve features across multiple entities."""
        results: Dict[str, Dict[str, Any]] = {}
        for eid in entity_ids:
            results[eid] = self.get_online_features(
                entity_id=eid,
                feature_names=feature_names,
                entity_type=entity_type,
                fallback_to_offline=fallback_to_offline,
                fill_missing=fill_missing,
            )
        return results

    def get_feature_matrix(
        self,
        entity_ids: Sequence[str],
        feature_names: Sequence[str],
        entity_type: str = "deal",
        fallback_to_offline: bool = True,
        fill_missing: bool = True,
    ) -> Dict[str, List[Any]]:
        """Extract a column-oriented 2D feature matrix suitable for tabular ML models or numpy arrays."""
        matrix: Dict[str, List[Any]] = {name: [] for name in feature_names}
        for eid in entity_ids:
            feat_dict = self.get_online_features(
                entity_id=eid,
                feature_names=feature_names,
                entity_type=entity_type,
                fallback_to_offline=fallback_to_offline,
                fill_missing=fill_missing,
            )
            for name in feature_names:
                matrix[name].append(feat_dict.get(name))
        return matrix
