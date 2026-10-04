"""Materialization and offline-to-online synchronization engine for feature store."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from autonomous_multi_agent_real.features.buffer import StreamFeatureBuffer
from autonomous_multi_agent_real.features.extractor import FeatureExtractor
from autonomous_multi_agent_real.features.serving import OnlineFeatureStore
from autonomous_multi_agent_real.features.storage import ParquetFeatureStore
from autonomous_multi_agent_real.features.types import (
    FeatureRecord,
    FeatureVector,
    MaterializationJob,
)
from autonomous_multi_agent_real.types import PropertyDeal


class MaterializationEngine:
    """Orchestrates bidirectional synchronization, stream buffer flushing, and deal backfills."""

    def __init__(
        self,
        offline_store: ParquetFeatureStore,
        online_store: OnlineFeatureStore,
        buffer: Optional[StreamFeatureBuffer] = None,
        extractor: Optional[FeatureExtractor] = None,
    ) -> None:
        self.offline_store = offline_store
        self.online_store = online_store
        self.buffer = buffer
        self.extractor = extractor or FeatureExtractor()
        self._jobs: List[MaterializationJob] = []

    def get_job_history(self) -> List[MaterializationJob]:
        """Return history of executed materialization jobs."""
        return list(self._jobs)

    def materialize_to_online(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        entity_ids: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
    ) -> MaterializationJob:
        """Hydrate online feature store with latest point-in-time features from offline Parquet."""
        job_id = f"mat_online_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)

        try:
            # Query all matching records from parquet
            table = self.offline_store.query(
                entity_ids=entity_ids,
                start_time=start_time,
                end_time=end_time,
                entity_type=entity_type,
            )

            if table.num_rows == 0:
                job = MaterializationJob(
                    job_id=job_id,
                    job_type="sync_to_online",
                    status="completed",
                    entities_count=0,
                    features_count=0,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
                self._jobs.append(job)
                return job

            pydict = table.to_pydict()
            unique_eids = sorted(set(pydict["entity_id"]))
            total_features = 0

            vectors_to_put: List[FeatureVector] = []
            for eid in unique_eids:
                vec = self.offline_store.get_latest_vector(eid, entity_type=entity_type)
                if vec:
                    vectors_to_put.append(vec)
                    total_features += len(vec.features)

            self.online_store.put_vectors(vectors_to_put)

            job = MaterializationJob(
                job_id=job_id,
                job_type="sync_to_online",
                status="completed",
                entities_count=len(unique_eids),
                features_count=total_features,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
            self._jobs.append(job)
            return job

        except Exception as exc:
            job = MaterializationJob(
                job_id=job_id,
                job_type="sync_to_online",
                status="failed",
                entities_count=0,
                features_count=0,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
            self._jobs.append(job)
            raise

    def flush_buffer_to_parquet(
        self,
        buffer: Optional[StreamFeatureBuffer] = None,
    ) -> MaterializationJob:
        """Drain buffered stream events and persist them into partitioned Parquet storage."""
        target_buffer = buffer or self.buffer
        if target_buffer is None:
            raise ValueError("No StreamFeatureBuffer configured for flushing.")

        job_id = f"mat_buffer_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)

        try:
            records = target_buffer.drain()
            if not records:
                job = MaterializationJob(
                    job_id=job_id,
                    job_type="buffer_flush",
                    status="completed",
                    entities_count=0,
                    features_count=0,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                )
                self._jobs.append(job)
                return job

            written_files = self.offline_store.write_records(records)
            unique_entities = {r.entity_id for r in records}

            job = MaterializationJob(
                job_id=job_id,
                job_type="buffer_flush",
                status="completed",
                entities_count=len(unique_entities),
                features_count=len(records),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
            self._jobs.append(job)
            return job

        except Exception as exc:
            job = MaterializationJob(
                job_id=job_id,
                job_type="buffer_flush",
                status="failed",
                entities_count=0,
                features_count=0,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
            self._jobs.append(job)
            raise

    def backfill_deals(
        self,
        deals: Sequence[PropertyDeal],
        sync_online: bool = True,
        context_map: Optional[Dict[str, Any]] = None,
    ) -> MaterializationJob:
        """Extract and persist features across historical deals into offline Parquet and online cache."""
        job_id = f"mat_backfill_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)

        try:
            all_vectors: List[FeatureVector] = []
            all_records: List[FeatureRecord] = []

            for deal in deals:
                ctx = context_map.get(deal.id) if context_map else None
                vec = self.extractor.extract_deal_features(deal, context=ctx)
                recs = self.extractor.extract_deal_records(deal, context=ctx)
                all_vectors.append(vec)
                all_records.extend(recs)

            if all_vectors:
                self.offline_store.write_vectors(all_vectors)

            if sync_online and all_vectors:
                self.online_store.put_vectors(all_vectors)

            total_features = sum(len(v.features) for v in all_vectors)

            job = MaterializationJob(
                job_id=job_id,
                job_type="deal_backfill",
                status="completed",
                entities_count=len(deals),
                features_count=total_features,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
            self._jobs.append(job)
            return job

        except Exception as exc:
            job = MaterializationJob(
                job_id=job_id,
                job_type="deal_backfill",
                status="failed",
                entities_count=0,
                features_count=0,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
            self._jobs.append(job)
            raise

    def sync_audit(
        self,
        entity_ids: Optional[Sequence[str]] = None,
        entity_type: str = "deal",
    ) -> Dict[str, Any]:
        """Audit parity between online in-memory cache and offline Parquet records."""
        all_parquet_table = self.offline_store.read_all_tables()
        if all_parquet_table is None or all_parquet_table.num_rows == 0:
            offline_entities: set[str] = set()
        else:
            offline_entities = set(all_parquet_table.to_pydict()["entity_id"])

        if entity_ids is not None:
            check_entities = set(entity_ids)
        else:
            check_entities = offline_entities.union({k.split(":")[-1] for k in self.online_store.keys()})

        in_sync_count = 0
        missing_online: List[str] = []
        missing_offline: List[str] = []
        discrepancies: Dict[str, List[str]] = {}

        for eid in sorted(check_entities):
            online_vec = self.online_store.get_vector(eid, entity_type=entity_type)
            offline_vec = self.offline_store.get_latest_vector(eid, entity_type=entity_type)

            if online_vec is None and offline_vec is not None:
                missing_online.append(eid)
            elif online_vec is not None and offline_vec is None:
                missing_offline.append(eid)
            elif online_vec is not None and offline_vec is not None:
                mismatches = []
                for k, v in online_vec.features.items():
                    if k in offline_vec.features:
                        off_v = offline_vec.features[k]
                        if isinstance(v, float) and isinstance(off_v, float):
                            if abs(v - off_v) > 1e-4:
                                mismatches.append(k)
                        elif v != off_v:
                            mismatches.append(k)
                if mismatches:
                    discrepancies[eid] = mismatches
                else:
                    in_sync_count += 1
            else:
                pass

        return {
            "total_checked": len(check_entities),
            "in_sync_count": in_sync_count,
            "missing_online": missing_online,
            "missing_offline": missing_offline,
            "discrepancies": discrepancies,
            "parity_ratio": (in_sync_count / len(check_entities)) if check_entities else 1.0,
        }
