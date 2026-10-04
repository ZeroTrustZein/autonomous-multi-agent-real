"""Feature quality auditing, statistical profiling, and distribution drift detection."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pyarrow as pa

from autonomous_multi_agent_real.features.registry import FeatureRegistry, get_default_registry
from autonomous_multi_agent_real.features.types import (
    FeatureQualityReport,
    FeatureStatistics,
    FeatureVector,
)


class FeatureQualityEngine:
    """Statistical profiling and data quality engine for feature monitoring and validation."""

    def __init__(self, registry: Optional[FeatureRegistry] = None) -> None:
        self.registry = registry if registry is not None else get_default_registry()

    def _extract_column_values(
        self,
        data: Union[pa.Table, Sequence[FeatureVector]],
        feature_name: str,
    ) -> List[Any]:
        """Extract all values for a feature from an Arrow Table or sequence of FeatureVectors."""
        if isinstance(data, pa.Table):
            if feature_name not in data.column_names:
                return []
            col = data[feature_name]
            return col.to_pylist()
        else:
            return [v.features.get(feature_name) for v in data]

    def compute_statistics(
        self,
        data: Union[pa.Table, Sequence[FeatureVector]],
        feature_name: str,
    ) -> FeatureStatistics:
        """Compute comprehensive descriptive statistics and percentiles for a feature."""
        raw_values = self._extract_column_values(data, feature_name)
        total_count = len(raw_values)

        if total_count == 0:
            return FeatureStatistics(
                feature_name=feature_name,
                count=0,
                null_count=0,
            )

        non_null_values = [v for v in raw_values if v is not None]
        null_count = total_count - len(non_null_values)
        distinct_count = len(set(non_null_values)) if non_null_values else 0

        # Filter for numeric computations
        numeric_vals = [
            float(v)
            for v in non_null_values
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(float(v))
        ]

        if not numeric_vals:
            return FeatureStatistics(
                feature_name=feature_name,
                count=total_count,
                null_count=null_count,
                distinct_count=distinct_count,
            )

        arr = np.array(numeric_vals, dtype=np.float64)
        min_v = float(np.min(arr))
        max_v = float(np.max(arr))
        mean_v = float(np.mean(arr))
        std_v = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0

        p25 = float(np.percentile(arr, 25))
        p50 = float(np.percentile(arr, 50))
        p75 = float(np.percentile(arr, 75))
        p95 = float(np.percentile(arr, 95))
        p99 = float(np.percentile(arr, 99))

        return FeatureStatistics(
            feature_name=feature_name,
            count=total_count,
            null_count=null_count,
            distinct_count=distinct_count,
            min_value=min_v,
            max_value=max_v,
            mean=mean_v,
            std_dev=std_v,
            p25=p25,
            p50=p50,
            p75=p75,
            p95=p95,
            p99=p99,
        )

    def compute_all_statistics(
        self,
        data: Union[pa.Table, Sequence[FeatureVector]],
    ) -> Dict[str, FeatureStatistics]:
        """Compute statistics for all features present in the dataset."""
        if isinstance(data, pa.Table):
            names = [
                c
                for c in data.column_names
                if c not in ("entity_id", "timestamp", "entity_type", "schema_version")
            ]
        else:
            names = sorted({k for v in data for k in v.features.keys()})

        return {name: self.compute_statistics(data, name) for name in names}

    def audit_quality(
        self,
        data: Union[pa.Table, Sequence[FeatureVector]],
        max_null_rate: float = 0.20,
    ) -> FeatureQualityReport:
        """Audit features against schema rules, completeness requirements, and domain bounds."""
        stats = self.compute_all_statistics(data)
        missing_features: List[str] = []
        null_rate_violations: Dict[str, float] = {}
        range_violations: Dict[str, str] = {}

        # Check registered definitions
        for meta in self.registry.list_features():
            feature_stat = stats.get(meta.name)
            if feature_stat is None:
                if not meta.is_nullable:
                    missing_features.append(meta.name)
                continue

            # Check null rates
            if not meta.is_nullable and feature_stat.null_rate > 0.0:
                null_rate_violations[meta.name] = feature_stat.null_rate
            elif feature_stat.null_rate > max_null_rate:
                null_rate_violations[meta.name] = feature_stat.null_rate

            # Check range boundaries
            if meta.min_value is not None and feature_stat.min_value is not None:
                if feature_stat.min_value < meta.min_value:
                    range_violations[meta.name] = (
                        f"Observed min {feature_stat.min_value} < constraint {meta.min_value}"
                    )
            if meta.max_value is not None and feature_stat.max_value is not None:
                if feature_stat.max_value > meta.max_value:
                    range_violations[meta.name] = (
                        f"Observed max {feature_stat.max_value} > constraint {meta.max_value}"
                    )

        is_valid = (
            len(missing_features) == 0
            and len(null_rate_violations) == 0
            and len(range_violations) == 0
        )

        return FeatureQualityReport(
            is_valid=is_valid,
            total_features_checked=len(self.registry.list_features()),
            missing_features=missing_features,
            null_rate_violations=null_rate_violations,
            range_violations=range_violations,
            validation_timestamp=datetime.now(timezone.utc),
        )

    def detect_drift(
        self,
        baseline: FeatureStatistics,
        current: FeatureStatistics,
        z_threshold: float = 2.0,
    ) -> Dict[str, Any]:
        """Detect statistical drift between a baseline distribution and a current observation window."""
        reasons: List[str] = []
        has_drift = False

        # 1. Null rate surge
        null_delta = current.null_rate - baseline.null_rate
        if null_delta > 0.10:
            has_drift = True
            reasons.append(
                f"Null rate surged from {baseline.null_rate:.2%} to {current.null_rate:.2%}"
            )

        # 2. Mean shift
        mean_shift_z = 0.0
        if (
            baseline.mean is not None
            and current.mean is not None
            and baseline.std_dev is not None
            and baseline.std_dev > 1e-6
        ):
            mean_shift_z = abs(current.mean - baseline.mean) / baseline.std_dev
            if mean_shift_z > z_threshold:
                has_drift = True
                reasons.append(
                    f"Mean shifted by {mean_shift_z:.2f} standard deviations (baseline: {baseline.mean:.4f}, current: {current.mean:.4f})"
                )

        # 3. Variance / Spread shift
        variance_ratio = 1.0
        if (
            baseline.std_dev is not None
            and current.std_dev is not None
            and baseline.std_dev > 1e-6
        ):
            variance_ratio = current.std_dev / baseline.std_dev
            if variance_ratio > 3.0 or variance_ratio < 0.25:
                has_drift = True
                reasons.append(
                    f"Volatility ratio shifted significantly: {variance_ratio:.2f}x"
                )

        return {
            "feature_name": baseline.feature_name,
            "has_drift": has_drift,
            "mean_shift_z": round(mean_shift_z, 4),
            "variance_ratio": round(variance_ratio, 4),
            "null_rate_delta": round(null_delta, 4),
            "reasons": reasons,
        }
