"""Real-time streaming ingestion buffer and backpressure manager for feature pipeline."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field

from autonomous_multi_agent_real.features.types import (
    FeatureRecord,
    FeatureStreamEvent,
    FeatureStreamStatus,
    FeatureVector,
    StreamBufferConfig,
)


FlushCallback = Callable[[List[FeatureRecord]], None]


class BufferMetrics(BaseModel):
    """Operational metrics and telemetry for in-memory streaming buffer."""

    model_config = ConfigDict(extra="ignore")

    records_in_buffer: int = Field(0, ge=0)
    total_records_ingested: int = Field(0, ge=0)
    total_records_flushed: int = Field(0, ge=0)
    total_flushes: int = Field(0, ge=0)
    dropped_records: int = Field(0, ge=0)
    buffer_utilization: float = Field(0.0, ge=0.0)
    is_healthy: bool = True
    last_flush_timestamp: Optional[datetime] = None


class StreamFeatureBuffer:
    """Thread-safe in-memory stream buffer with automated size- and time-based flushing."""

    def __init__(
        self,
        config: Optional[StreamBufferConfig] = None,
        flush_sink: Optional[FlushCallback] = None,
        watermark_delay_seconds: float = 86400.0,
    ) -> None:
        self.config = config or StreamBufferConfig()
        self.flush_sink = flush_sink
        self.watermark_delay_seconds = watermark_delay_seconds

        self._lock = threading.Lock()
        self._buffer: List[FeatureRecord] = []
        self._last_flush_time = time.monotonic()
        self._last_flush_datetime: Optional[datetime] = None

        # Telemetry counters
        self._total_ingested = 0
        self._total_flushed = 0
        self._total_flushes = 0
        self._dropped_records = 0

    @property
    def capacity(self) -> int:
        return getattr(self.config, "buffer_size", 1000)

    def add_record(self, record: FeatureRecord) -> bool:
        """Add a single feature record to the streaming buffer.

        Flushes automatically if buffer reaches buffer_size capacity or timeout.
        """
        now_utc = datetime.now(timezone.utc)
        record_age = (now_utc - record.timestamp).total_seconds()

        # Late arrival check against watermark
        if record_age > self.watermark_delay_seconds:
            with self._lock:
                self._dropped_records += 1
            return False

        with self._lock:
            # Memory / capacity check
            if len(self._buffer) >= self.capacity:
                self._flush_locked()

            self._buffer.append(record)
            self._total_ingested += 1

            # Check if threshold reached
            if len(self._buffer) >= self.capacity:
                self._flush_locked()
            elif (time.monotonic() - self._last_flush_time) >= self.config.flush_interval_seconds:
                self._flush_locked()

        return True

    def add_records(self, records: Sequence[FeatureRecord]) -> int:
        """Add multiple feature records to the buffer in batch."""
        accepted = 0
        for rec in records:
            if self.add_record(rec):
                accepted += 1
        return accepted

    def add_vector(self, vector: FeatureVector, source: str = "vector_buffer") -> int:
        """Decompose and buffer a FeatureVector into atomic FeatureRecords."""
        records: List[FeatureRecord] = []
        for name, val in vector.features.items():
            records.append(
                FeatureRecord(
                    entity_id=vector.entity_id,
                    entity_type=vector.entity_type,
                    feature_name=name,
                    value=val,
                    timestamp=vector.timestamp,
                    source=source,
                )
            )
        return self.add_records(records)

    def add_event(self, event: FeatureStreamEvent, source: str = "stream_event") -> int:
        """Unpack a FeatureStreamEvent into the buffer."""
        payload = event.payload
        entity_id = getattr(event, "entity_id", None) or str(payload.get("entity_id") or payload.get("deal_id") or "event_entity")
        entity_type = getattr(event, "entity_type", None) or str(payload.get("entity_type") or "deal")
        ts = getattr(event, "event_time", None) or getattr(event, "timestamp", None) or datetime.now(timezone.utc)

        feat_dict = payload.get("features", payload)
        records: List[FeatureRecord] = []
        for k, v in feat_dict.items():
            if k in ("entity_id", "deal_id", "entity_type", "timestamp", "event_time"):
                continue
            records.append(
                FeatureRecord(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    feature_name=k,
                    value=v,
                    timestamp=ts,
                    source=source,
                )
            )
        return self.add_records(records)

    def flush(self) -> int:
        """Explicitly flush all buffered records to sink."""
        with self._lock:
            return self._flush_locked()

    def _flush_locked(self) -> int:
        """Internal lock-guarded flush implementation."""
        if not self._buffer:
            self._last_flush_time = time.monotonic()
            return 0

        to_flush = list(self._buffer)
        count = len(to_flush)
        self._buffer.clear()
        self._last_flush_time = time.monotonic()
        self._last_flush_datetime = datetime.now(timezone.utc)

        if self.flush_sink is not None:
            try:
                self.flush_sink(to_flush)
            except Exception:
                self._dropped_records += count
                return 0

        self._total_flushed += count
        self._total_flushes += 1
        return count

    def get_status(self) -> BufferMetrics:
        """Query current buffer operational metrics and status."""
        with self._lock:
            current_len = len(self._buffer)
            cap = self.capacity
            utilization = (current_len / cap) if cap > 0 else 0.0
            return BufferMetrics(
                records_in_buffer=current_len,
                total_records_ingested=self._total_ingested,
                total_records_flushed=self._total_flushed,
                total_flushes=self._total_flushes,
                dropped_records=self._dropped_records,
                buffer_utilization=round(utilization, 4),
                is_healthy=self._dropped_records == 0 or (self._dropped_records / max(1, self._total_ingested) < 0.05),
                last_flush_timestamp=self._last_flush_datetime,
            )

    def close(self) -> None:
        """Flush and shutdown the buffer."""
        self.flush()

    def __enter__(self) -> StreamFeatureBuffer:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
