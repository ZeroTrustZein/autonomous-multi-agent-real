"""Pipeline lifecycle hook interceptor for real-time feature extraction during underwriting."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from autonomous_multi_agent_real.features.buffer import StreamFeatureBuffer
from autonomous_multi_agent_real.features.extractor import FeatureExtractor
from autonomous_multi_agent_real.features.serving import OnlineFeatureStore
from autonomous_multi_agent_real.features.storage import ParquetFeatureStore
from autonomous_multi_agent_real.features.types import (
    FeatureRecord,
    FeatureStreamEvent,
    FeatureVector,
)

logger = logging.getLogger(__name__)


class PipelineFeatureInterceptor:
    """Hooks into DealPipeline execution to stream features at stage transitions."""

    def __init__(
        self,
        extractor: Optional[FeatureExtractor] = None,
        buffer: Optional[StreamFeatureBuffer] = None,
        online_store: Optional[OnlineFeatureStore] = None,
        offline_store: Optional[ParquetFeatureStore] = None,
        auto_persist_on_complete: bool = True,
    ) -> None:
        self.extractor = extractor or FeatureExtractor()
        self.buffer = buffer
        self.online_store = online_store
        self.offline_store = offline_store
        self.auto_persist_on_complete = auto_persist_on_complete
        self.extracted_records_count: int = 0
        self.extracted_vectors_count: int = 0

    def on_stage_start(self, stage: Any, context: Any) -> None:
        """Invoked when a pipeline stage begins."""
        stage_name = getattr(stage, "value", str(stage))
        deal_id = getattr(context.deal, "id", "unknown")

        if self.buffer:
            event = FeatureStreamEvent(
                entity_id=deal_id,
                entity_type="deal",
                event_type="stage_start",
                features={"current_stage": stage_name},
                source="pipeline_interceptor",
            )
            self.buffer.push(event)

    def on_stage_end(
        self, stage: Any, context: Any, report: Optional[Any] = None
    ) -> None:
        """Invoked when a pipeline stage completes, capturing newly resolved metrics."""
        stage_name = getattr(stage, "value", str(stage))
        deal = getattr(context, "deal", None)
        if not deal:
            return

        # Extract features available up to this point in context
        vector = self.extractor.extract_deal_features(deal, context=context)
        records = self.extractor.extract_deal_records(deal, context=context)

        self.extracted_records_count += len(records)
        self.extracted_vectors_count += 1

        # Feed streaming buffer
        if self.buffer:
            event = FeatureStreamEvent(
                entity_id=deal.id,
                entity_type="deal",
                event_type=f"stage_end_{stage_name}",
                features=dict(vector.features),
                source="pipeline_interceptor",
            )
            self.buffer.push(event)

        # Update online store immediately for active inference
        if self.online_store:
            self.online_store.put_vector(vector)

    def on_workflow_complete(self, context: Any, underwriting_result: Any) -> None:
        """Invoked when the full deal pipeline concludes, optionally flushing to Parquet."""
        deal = getattr(context, "deal", None)
        if not deal:
            return

        final_vector = self.extractor.extract_deal_features(deal, context=context)
        final_records = self.extractor.extract_deal_records(deal, context=context)

        if self.online_store:
            self.online_store.put_vector(final_vector)

        if self.auto_persist_on_complete and self.offline_store:
            self.offline_store.write_vectors([final_vector])
            if final_records:
                self.offline_store.write_records(final_records)
