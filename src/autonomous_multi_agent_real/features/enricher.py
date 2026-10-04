"""Feature context enricher computing cohort percentiles, z-scores, and deliberation briefs."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Union

from autonomous_multi_agent_real.features.extractor import FeatureExtractor
from autonomous_multi_agent_real.features.serving import OnlineFeatureStore
from autonomous_multi_agent_real.features.storage import ParquetFeatureStore
from autonomous_multi_agent_real.features.types import EnrichedFeatureContext, FeatureVector
from autonomous_multi_agent_real.types import PropertyDeal


class FeatureContextEnricher:
    """Enriches deal features with cohort benchmark distributions, z-scores, and percentiles."""

    def __init__(
        self,
        extractor: Optional[FeatureExtractor] = None,
        online_store: Optional[OnlineFeatureStore] = None,
        offline_store: Optional[ParquetFeatureStore] = None,
    ) -> None:
        self.extractor = extractor or FeatureExtractor()
        self.online_store = online_store
        self.offline_store = offline_store

    def enrich_deal(
        self,
        deal: PropertyDeal,
        context: Optional[Any] = None,
        cohort_deals: Optional[Sequence[PropertyDeal]] = None,
        cohort_name: str = "market_peers",
    ) -> EnrichedFeatureContext:
        """Calculate cohort percentiles and z-scores for target deal features."""
        target_vec = self.extractor.extract_deal_features(deal, context=context)
        target_features = target_vec.features

        cohort_vectors: List[FeatureVector] = []
        if cohort_deals:
            for cd in cohort_deals:
                cohort_vectors.append(self.extractor.extract_deal_features(cd))
        elif self.online_store:
            cohort_vectors = [
                self.online_store.get_vector(k.split(":")[-1])
                for k in self.online_store.keys()
            ]
            cohort_vectors = [v for v in cohort_vectors if v is not None]

        percentiles: Dict[str, float] = {}
        z_scores: Dict[str, float] = {}
        cohort_medians: Dict[str, float] = {}

        if cohort_vectors:
            for k, val in target_features.items():
                if val is None or not isinstance(val, (int, float)):
                    continue

                cohort_vals = [
                    float(cv.features[k])
                    for cv in cohort_vectors
                    if k in cv.features and isinstance(cv.features[k], (int, float))
                ]

                if not cohort_vals:
                    continue

                cohort_vals.sort()
                n = len(cohort_vals)

                # Median
                if n % 2 == 1:
                    median_val = cohort_vals[n // 2]
                else:
                    median_val = (cohort_vals[n // 2 - 1] + cohort_vals[n // 2]) / 2.0
                cohort_medians[k] = round(median_val, 4)

                # Percentile rank
                lesser = sum(1 for cv in cohort_vals if cv < val)
                equal = sum(1 for cv in cohort_vals if cv == val)
                pct_rank = (lesser + 0.5 * equal) / n
                percentiles[k] = round(pct_rank, 4)

                # Z-score
                mean_val = sum(cohort_vals) / n
                variance = sum((x - mean_val) ** 2 for x in cohort_vals) / n
                std_dev = math.sqrt(variance)

                if std_dev > 1e-6:
                    z = (float(val) - mean_val) / std_dev
                    z_scores[k] = round(z, 3)
                else:
                    z_scores[k] = 0.0

        return EnrichedFeatureContext(
            entity_id=deal.id,
            cohort_name=cohort_name,
            features=target_features,
            percentiles=percentiles,
            z_scores=z_scores,
            cohort_medians=cohort_medians,
            timestamp=datetime.now(timezone.utc),
        )

    def format_deliberation_brief(self, enriched: EnrichedFeatureContext) -> str:
        """Format human and agent-readable Markdown brief highlighting relative positioning."""
        lines = [
            f"### Statistical Feature Context: {enriched.entity_id} (Cohort: {enriched.cohort_name})",
            "| Feature | Value | Cohort Median | Percentile Rank | Z-Score |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        priority_keys = [
            "cap_rate",
            "price_per_unit",
            "price_per_sqft",
            "occupancy_rate",
            "operating_expense_ratio",
            "debt_yield",
            "underwritten_dscr",
            "composite_deal_score",
        ]

        for key in priority_keys:
            if key in enriched.features:
                raw_val = enriched.features[key]
                val_str = f"{raw_val:,.2f}" if isinstance(raw_val, (int, float)) else str(raw_val)
                median_val = enriched.cohort_medians.get(key)
                med_str = f"{median_val:,.2f}" if median_val is not None else "N/A"
                pct = enriched.percentiles.get(key)
                pct_str = f"{pct * 100:.1f}%" if pct is not None else "N/A"
                z = enriched.z_scores.get(key)
                z_str = f"{z:+.2f}σ" if z is not None else "N/A"

                lines.append(f"| `{key}` | {val_str} | {med_str} | {pct_str} | {z_str} |")

        return "\n".join(lines)
