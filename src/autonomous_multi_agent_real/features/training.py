"""Point-in-time joins and training dataset generation without lookahead data leakage."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pyarrow as pa
import pyarrow.parquet as pq

from autonomous_multi_agent_real.features.registry import FeatureRegistry, get_default_registry
from autonomous_multi_agent_real.features.storage import ParquetFeatureStore
from autonomous_multi_agent_real.features.types import (
    ObservationTarget,
    TrainingDatasetMetadata,
)


class TrainingDataset:
    """In-memory partitioned training dataset with PyArrow export and correlation analysis."""

    def __init__(
        self,
        metadata: TrainingDatasetMetadata,
        train_records: List[Dict[str, Any]],
        val_records: List[Dict[str, Any]],
        test_records: List[Dict[str, Any]],
    ) -> None:
        self.metadata = metadata
        self.train_records = train_records
        self.val_records = val_records
        self.test_records = test_records

    @property
    def total_records(self) -> int:
        return len(self.train_records) + len(self.val_records) + len(self.test_records)

    def get_records(self, split: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return combined or split-specific dataset records."""
        if split == "train":
            return list(self.train_records)
        elif split == "val":
            return list(self.val_records)
        elif split == "test":
            return list(self.test_records)
        return self.train_records + self.val_records + self.test_records

    def to_arrow_table(self, split: Optional[str] = None) -> pa.Table:
        """Convert split or entire dataset to PyArrow Table."""
        records = self.get_records(split)
        if not records:
            cols = (
                ["entity_id", "timestamp"]
                + self.metadata.feature_names
                + [self.metadata.label_name]
            )
            return pa.schema([pa.field(c, pa.string()) for c in cols]).empty_table()

        cols = ["entity_id", "timestamp"] + self.metadata.feature_names + [self.metadata.label_name]
        data: Dict[str, List[Any]] = {c: [] for c in cols}

        for r in records:
            for c in cols:
                data[c].append(r.get(c))

        arrays = []
        for c in cols:
            arrays.append(pa.array(data[c]))

        return pa.Table.from_arrays(arrays, names=cols)

    def to_xy(self, split: Optional[str] = "train") -> Tuple[Dict[str, List[Any]], List[Any]]:
        """Extract feature matrix (X) and label target vector (y) for machine learning models."""
        records = self.get_records(split)
        X: Dict[str, List[Any]] = {fn: [] for fn in self.metadata.feature_names}
        y: List[Any] = []

        for r in records:
            for fn in self.metadata.feature_names:
                X[fn].append(r.get(fn))
            y.append(r.get(self.metadata.label_name))

        return X, y

    def compute_correlations(self) -> Dict[str, float]:
        """Compute Pearson correlation coefficient between numeric features and numeric label."""
        records = self.get_records()
        label_vals = [r.get(self.metadata.label_name) for r in records]

        numeric_pairs = [
            (i, float(v))
            for i, v in enumerate(label_vals)
            if v is not None and isinstance(v, (int, float))
        ]
        if len(numeric_pairs) < 2:
            return {}

        valid_indices = [idx for idx, _ in numeric_pairs]
        y_valid = [val for _, val in numeric_pairs]
        mean_y = sum(y_valid) / len(y_valid)
        var_y = sum((y - mean_y) ** 2 for y in y_valid)

        if var_y == 0.0:
            return {}

        correlations: Dict[str, float] = {}

        for fn in self.metadata.feature_names:
            x_vals = [records[i].get(fn) for i in valid_indices]
            paired = [
                (float(x), y)
                for x, y in zip(x_vals, y_valid)
                if x is not None and isinstance(x, (int, float))
            ]

            if len(paired) < 2:
                continue

            x_subset, y_subset = zip(*paired)
            mean_x = sum(x_subset) / len(x_subset)
            mean_y_sub = sum(y_subset) / len(y_subset)

            cov = sum((x - mean_x) * (y - mean_y_sub) for x, y in zip(x_subset, y_subset))
            var_x = sum((x - mean_x) ** 2 for x in x_subset)
            var_y_sub = sum((y - mean_y_sub) ** 2 for y in y_subset)

            denom = math.sqrt(var_x * var_y_sub)
            if denom > 0:
                correlations[fn] = round(cov / denom, 4)

        return correlations

    def export_parquet(self, output_dir: Union[str, Path]) -> Dict[str, Path]:
        """Export train, val, and test splits into Parquet files."""
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)

        exported: Dict[str, Path] = {}
        for split in ("train", "val", "test"):
            table = self.to_arrow_table(split)
            if table.num_rows > 0:
                file_path = out / f"{self.metadata.dataset_name}_{split}.parquet"
                pq.write_table(table, file_path)
                exported[split] = file_path

        return exported


class TrainingDatasetGenerator:
    """Builds point-in-time joined training datasets avoiding temporal data leakage."""

    def __init__(
        self,
        offline_store: ParquetFeatureStore,
        registry: Optional[FeatureRegistry] = None,
    ) -> None:
        self.offline_store = offline_store
        self.registry = registry or get_default_registry()

    def build_dataset(
        self,
        observations: Sequence[ObservationTarget],
        dataset_name: str,
        feature_names: Optional[Sequence[str]] = None,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        temporal_split: bool = True,
    ) -> TrainingDataset:
        """Execute point-in-time as-of joins across observations and partition into splits."""
        if not observations:
            meta = TrainingDatasetMetadata(
                dataset_name=dataset_name,
                label_name="target",
                feature_names=list(feature_names or []),
            )
            return TrainingDataset(meta, [], [], [])

        label_name = observations[0].label_name
        joined_records: List[Dict[str, Any]] = []

        all_features_observed: set[str] = set()

        # Sort observations chronologically
        sorted_obs = sorted(observations, key=lambda o: o.timestamp)

        for obs in sorted_obs:
            vec = self.offline_store.get_as_of_vector(
                entity_id=obs.entity_id,
                as_of=obs.timestamp,
                entity_type=obs.entity_type,
            )

            rec: Dict[str, Any] = {
                "entity_id": obs.entity_id,
                "timestamp": obs.timestamp.isoformat(),
                obs.label_name: obs.label_value,
            }

            if vec is not None:
                for k, v in vec.features.items():
                    if feature_names is None or k in feature_names:
                        rec[k] = v
                        all_features_observed.add(k)
            else:
                # If no vector found before observation timestamp, populate None or registry defaults
                if feature_names is not None:
                    for k in feature_names:
                        meta = self.registry.get(k)
                        rec[k] = meta.default_value if meta else None
                        all_features_observed.add(k)

            joined_records.append(rec)

        final_feature_names = (
            sorted(feature_names) if feature_names is not None else sorted(all_features_observed)
        )

        # Split data
        total_len = len(joined_records)
        train_idx = int(total_len * train_ratio)
        val_idx = train_idx + int(total_len * val_ratio)

        if temporal_split:
            train_recs = joined_records[:train_idx]
            val_recs = joined_records[train_idx:val_idx]
            test_recs = joined_records[val_idx:]
        else:
            # Deterministic modulo split by entity hash
            train_recs, val_recs, test_recs = [], [], []
            for r in joined_records:
                h = hash(r["entity_id"]) % 100
                if h < int(train_ratio * 100):
                    train_recs.append(r)
                elif h < int((train_ratio + val_ratio) * 100):
                    val_recs.append(r)
                else:
                    test_recs.append(r)

        metadata = TrainingDatasetMetadata(
            dataset_name=dataset_name,
            label_name=label_name,
            feature_names=final_feature_names,
            train_count=len(train_recs),
            val_count=len(val_recs),
            test_count=len(test_recs),
        )

        return TrainingDataset(
            metadata=metadata,
            train_records=train_recs,
            val_records=val_recs,
            test_records=test_recs,
        )
