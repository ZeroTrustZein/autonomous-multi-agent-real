"""Parquet columnar storage engine and partition management for feature store."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from autonomous_multi_agent_real.features.types import (
    FeatureStoreManifest,
    FeatureRecord,
    FeatureVector,
    ParquetPartitionSpec,
    PartitionStrategy,
    feature_records_to_arrow_table,
    feature_vectors_to_arrow_table,
    table_to_safe_pydict,
)


class ParquetFeatureStore:
    """Columnar feature persistence engine supporting automated partitioning, point-in-time joins, and compaction."""

    def __init__(
        self,
        base_path: Union[str, Path],
        partition_spec: Optional[ParquetPartitionSpec] = None,
        dataset_id: str = "cre_feature_store",
    ) -> None:
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.partition_spec = partition_spec or ParquetPartitionSpec()
        self.dataset_id = dataset_id
        self._manifest_file = self.base_path / "manifest.json"
        self._ensure_manifest()

    def _ensure_manifest(self) -> None:
        """Initialize or load store manifest."""
        if not self._manifest_file.exists():
            manifest = FeatureStoreManifest(
                dataset_id=self.dataset_id,
                store_path=str(self.base_path),
                created_at=datetime.now(timezone.utc),
                last_updated_at=datetime.now(timezone.utc),
                total_records=0,
                total_files=0,
                partition_keys=list(self.partition_spec.partition_columns),
                feature_names=[],
            )
            self._save_manifest(manifest)

    def get_manifest(self) -> FeatureStoreManifest:
        """Load feature store manifest."""
        if not self._manifest_file.exists():
            self._ensure_manifest()
        data = json.loads(self._manifest_file.read_text(encoding="utf-8"))
        return FeatureStoreManifest.model_validate(data)

    def _save_manifest(self, manifest: FeatureStoreManifest) -> None:
        """Persist updated manifest to disk."""
        self._manifest_file.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    def _update_manifest_stats(
        self,
        new_records_count: int,
        new_feature_names: Sequence[str],
        file_delta: int = 1,
    ) -> None:
        """Incrementally update manifest counts and feature names."""
        manifest = self.get_manifest()
        combined_names = sorted(set(manifest.feature_names).union(new_feature_names))
        updated = manifest.model_copy(
            update={
                "last_updated_at": datetime.now(timezone.utc),
                "total_records": manifest.total_records + new_records_count,
                "total_files": max(0, manifest.total_files + file_delta),
                "feature_names": combined_names,
            }
        )
        self._save_manifest(updated)

    def _resolve_partition_dir(
        self,
        record_timestamp: datetime,
        attributes: Dict[str, Any],
    ) -> Path:
        """Resolve directory path based on partition_spec columns and record attributes."""
        parts: List[str] = []
        for col in self.partition_spec.partition_columns:
            if col == "date":
                val = record_timestamp.strftime("%Y-%m-%d")
            else:
                raw_val = attributes.get(col)
                val = str(raw_val) if raw_val is not None else "unknown"
            parts.append(f"{col}={val}")

        if not parts:
            # Fallback to date partitioning
            parts.append(f"date={record_timestamp.strftime('%Y-%m-%d')}")

        target_dir = self.base_path
        for p in parts:
            target_dir = target_dir / p
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def write_vectors(self, vectors: Sequence[FeatureVector]) -> List[Path]:
        """Write feature vectors into partitioned Parquet files."""
        if not vectors:
            return []

        written_files: List[Path] = []
        grouped: Dict[Path, List[FeatureVector]] = {}
        all_feature_keys: set[str] = set()

        for vec in vectors:
            # Merge vector metadata, features, and standard fields for partition resolution
            attr_pool: Dict[str, Any] = {
                "entity_type": vec.entity_type,
                "entity_id": vec.entity_id,
            }
            attr_pool.update(vec.metadata)
            attr_pool.update(vec.features)

            p_dir = self._resolve_partition_dir(
                record_timestamp=vec.timestamp,
                attributes=attr_pool,
            )
            grouped.setdefault(p_dir, []).append(vec)
            all_feature_keys.update(vec.features.keys())

        for target_dir, p_vectors in grouped.items():
            table = feature_vectors_to_arrow_table(p_vectors)
            file_name = f"part_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.parquet"
            target_file = target_dir / file_name

            pq.write_table(
                table,
                target_file,
                compression=self.partition_spec.compression,
                use_dictionary=self.partition_spec.dictionary_encoding,
                row_group_size=self.partition_spec.row_group_size,
            )
            written_files.append(target_file)

        self._update_manifest_stats(
            new_records_count=len(vectors),
            new_feature_names=sorted(all_feature_keys),
            file_delta=len(written_files),
        )
        return written_files

    def write_records(self, records: Sequence[FeatureRecord]) -> List[Path]:
        """Write atomic feature records into partitioned Parquet files."""
        if not records:
            return []

        written_files: List[Path] = []
        grouped: Dict[Path, List[FeatureRecord]] = {}
        all_names = sorted({r.feature_name for r in records})

        for rec in records:
            attr_pool = {
                "entity_type": rec.entity_type,
                "entity_id": rec.entity_id,
                "source": rec.source,
                "partition_key": rec.partition_key,
            }
            p_dir = self._resolve_partition_dir(
                record_timestamp=rec.timestamp,
                attributes=attr_pool,
            )
            grouped.setdefault(p_dir, []).append(rec)

        for target_dir, p_records in grouped.items():
            table = feature_records_to_arrow_table(p_records)
            file_name = f"records_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.parquet"
            target_file = target_dir / file_name

            pq.write_table(
                table,
                target_file,
                compression=self.partition_spec.compression,
                use_dictionary=self.partition_spec.dictionary_encoding,
                row_group_size=self.partition_spec.row_group_size,
            )
            written_files.append(target_file)

        self._update_manifest_stats(
            new_records_count=len(records),
            new_feature_names=all_names,
            file_delta=len(written_files),
        )
        return written_files

    def list_parquet_files(self) -> List[Path]:
        """Discover all Parquet files across the store directory tree."""
        return sorted(self.base_path.glob("**/*.parquet"))

    def list_partitions(self) -> List[str]:
        """List partition directory names relative to base path."""
        partitions: set[str] = set()
        for p in self.list_parquet_files():
            rel_parent = p.parent.relative_to(self.base_path)
            if str(rel_parent) != ".":
                partitions.add(str(rel_parent).replace("\\", "/"))
        return sorted(partitions)

    def read_all_tables(self) -> Optional[pa.Table]:
        """Read and concatenate all stored Parquet files into a unified Arrow Table."""
        files = self.list_parquet_files()
        if not files:
            return None

        tables = []
        for f in files:
            try:
                tables.append(pq.read_table(f))
            except Exception:
                continue

        if not tables:
            return None

        return pa.concat_tables(tables, promote_options="default")

    def query(
        self,
        entity_ids: Optional[Sequence[str]] = None,
        feature_names: Optional[Sequence[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        entity_type: Optional[str] = None,
    ) -> pa.Table:
        """Filter and retrieve features as a PyArrow Table."""
        full_table = self.read_all_tables()
        if full_table is None or full_table.num_rows == 0:
            empty_schema = pa.schema(
                [
                    pa.field("entity_id", pa.string()),
                    pa.field("timestamp", pa.timestamp("ms", tz="UTC")),
                ]
            )
            return empty_schema.empty_table()

        mask = pc.equal(pc.is_null(full_table["entity_id"]), False)

        if entity_ids is not None and len(entity_ids) > 0:
            target_set = pa.array(list(entity_ids), type=pa.string())
            mask = pc.and_(mask, pc.is_in(full_table["entity_id"], target_set))

        if entity_type is not None and "entity_type" in full_table.column_names:
            mask = pc.and_(mask, pc.equal(full_table["entity_type"], entity_type))

        if start_time is not None:
            ts_scalar = pa.scalar(start_time, type=pa.timestamp("ms", tz="UTC"))
            mask = pc.and_(mask, pc.greater_equal(full_table["timestamp"], ts_scalar))

        if end_time is not None:
            ts_scalar = pa.scalar(end_time, type=pa.timestamp("ms", tz="UTC"))
            mask = pc.and_(mask, pc.less_equal(full_table["timestamp"], ts_scalar))

        filtered_table = full_table.filter(mask)

        # Column projection if requested
        if feature_names is not None and filtered_table.num_columns > 0:
            keep_cols = ["entity_id", "timestamp"]
            if "entity_type" in filtered_table.column_names:
                keep_cols.append("entity_type")
            for fn in feature_names:
                if fn in filtered_table.column_names and fn not in keep_cols:
                    keep_cols.append(fn)
            filtered_table = filtered_table.select(keep_cols)

        return filtered_table

    def get_as_of_vector(
        self,
        entity_id: str,
        as_of: datetime,
        entity_type: str = "deal",
    ) -> Optional[FeatureVector]:
        """Perform a point-in-time lookup for an entity's features as of a given timestamp.

        Ensures zero future lookahead data leakage by only including observations
        recorded at or before `as_of`.
        """
        table = self.query(
            entity_ids=[entity_id],
            end_time=as_of,
            entity_type=entity_type,
        )

        if table.num_rows == 0:
            return None

        pydict = table_to_safe_pydict(table)
        timestamps = pydict["timestamp"]
        latest_idx = -1
        latest_ts = None

        for idx, ts in enumerate(timestamps):
            if ts is not None and ts <= as_of:
                if latest_ts is None or ts > latest_ts:
                    latest_ts = ts
                    latest_idx = idx

        if latest_idx == -1:
            return None

        extracted_features: Dict[str, Any] = {}
        for col, values in pydict.items():
            if col in ("entity_id", "timestamp", "entity_type", "schema_version"):
                continue
            val = values[latest_idx]
            if val is not None:
                extracted_features[col] = val

        return FeatureVector(
            entity_id=entity_id,
            entity_type=entity_type,
            features=extracted_features,
            timestamp=latest_ts,
            schema_version="1.0.0",
        )

    def get_latest_vector(
        self,
        entity_id: str,
        entity_type: str = "deal",
    ) -> Optional[FeatureVector]:
        """Retrieve latest state for a given entity."""
        return self.get_as_of_vector(
            entity_id=entity_id,
            as_of=datetime.now(timezone.utc),
            entity_type=entity_type,
        )

    def get_vectors(
        self,
        entity_ids: Sequence[str],
        as_of: Optional[datetime] = None,
        entity_type: str = "deal",
    ) -> List[FeatureVector]:
        """Batch retrieve point-in-time feature vectors for multiple entities."""
        query_time = as_of or datetime.now(timezone.utc)
        results: List[FeatureVector] = []
        for eid in entity_ids:
            vec = self.get_as_of_vector(eid, as_of=query_time, entity_type=entity_type)
            if vec is not None:
                results.append(vec)
        return results

    def compact_partitions(self) -> int:
        """Compact fragmented small Parquet files inside each partition directory into single consolidated files."""
        partitions = self.list_partitions()
        compacted_count = 0

        check_dirs = [self.base_path / p for p in partitions]
        for p_dir in check_dirs:
            p_files = list(p_dir.glob("*.parquet"))
            if len(p_files) >= 2:
                tables = []
                for pf in p_files:
                    try:
                        tables.append(pq.read_table(pf))
                    except Exception:
                        continue
                if tables:
                    merged = pa.concat_tables(tables, promote_options="default")
                    consolidated_file = p_dir / f"consolidated_{uuid.uuid4().hex[:8]}.parquet"
                    pq.write_table(
                        merged,
                        consolidated_file,
                        compression=self.partition_spec.compression,
                        row_group_size=self.partition_spec.row_group_size,
                    )
                    for pf in p_files:
                        pf.unlink(missing_ok=True)
                    compacted_count += len(p_files)

        # Update manifest file count
        manifest = self.get_manifest()
        current_total_files = len(self.list_parquet_files())
        self._save_manifest(
            manifest.model_copy(
                update={
                    "total_files": current_total_files,
                    "last_updated_at": datetime.now(timezone.utc),
                }
            )
        )
        return compacted_count
