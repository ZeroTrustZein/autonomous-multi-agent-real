"""Domain models and type definitions for real-time feature extraction and columnar feature storage."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator
import pyarrow as pa


class FeatureDataType(str, Enum):
    """Primitive and composite data types supported by the feature store."""

    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    VECTOR = "vector"
    JSON = "json"

    def to_arrow_type(self) -> pa.DataType:
        """Convert feature data type to corresponding PyArrow DataType."""
        mapping = {
            FeatureDataType.FLOAT: pa.float64(),
            FeatureDataType.INT: pa.int64(),
            FeatureDataType.STRING: pa.string(),
            FeatureDataType.BOOLEAN: pa.bool_(),
            FeatureDataType.TIMESTAMP: pa.timestamp("ms", tz="UTC"),
            FeatureDataType.VECTOR: pa.list_(pa.float64()),
            FeatureDataType.JSON: pa.string(),
        }
        return mapping[self]


class FeatureCategory(str, Enum):
    """Domain grouping for underwriting features."""

    PROPERTY = "property"
    FINANCIAL = "financial"
    MARKET = "market"
    DEBT = "debt"
    RISK = "risk"
    LOCATION = "location"
    DERIVED = "derived"
    TIME_SERIES = "time_series"


class FeatureTimeWindow(str, Enum):
    """Aggregation window durations for streaming feature rollups."""

    REALTIME = "realtime"
    HOURLY = "1h"
    DAILY = "24h"
    WEEKLY = "7d"
    MONTHLY = "30d"
    QUARTERLY = "90d"
    ANNUAL = "365d"


class FeatureStreamStatus(str, Enum):
    """Lifecycle status of streaming feature ingestion events."""

    BUFFERED = "buffered"
    STREAMING = "streaming"
    COMMITTED = "committed"
    FAILED = "failed"
    DROPPED = "dropped"


class PartitionStrategy(str, Enum):
    """Partitioning schemes for Parquet table layout."""

    PROPERTY_TYPE = "property_type"
    VINTAGE_YEAR = "vintage_year"
    COMPOSITE = "composite"
    DATE = "date"


class FeatureMetadata(BaseModel):
    """Schema definition and catalog metadata for a registered feature."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Unique feature identifier (snake_case)")
    data_type: FeatureDataType = Field(..., description="Value representation type")
    category: FeatureCategory = Field(..., description="Domain category")
    description: str = Field("", description="Descriptive definition and business formula")
    entity_key: str = Field("deal_id", description="Primary entity partition or join key")
    version: str = Field("1.0.0", description="Semantic version of the feature calculation")
    tags: List[str] = Field(default_factory=list, description="Categorical tags for discovery")
    is_nullable: bool = Field(True, description="Whether null values are permissible")
    default_value: Optional[Any] = Field(None, description="Fallback value if feature missing")
    unit: Optional[str] = Field(
        None, description="Measurement unit (e.g. 'USD', 'ratio', 'bps', 'sqft', 'pct')"
    )
    window: FeatureTimeWindow = Field(
        FeatureTimeWindow.REALTIME, description="Aggregation window"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Feature name cannot be empty")
        return clean

    def to_arrow_field(self) -> pa.Field:
        """Generate PyArrow Field definition matching this metadata."""
        return pa.field(
            name=self.name,
            type=self.data_type.to_arrow_type(),
            nullable=self.is_nullable,
            metadata={
                "category": self.category.value,
                "version": self.version,
                "unit": self.unit or "",
            },
        )


class FeatureValue(BaseModel):
    """Single evaluated feature point with confidence score and timestamp."""

    model_config = ConfigDict(extra="ignore")

    feature_name: str
    value: Any
    data_type: Optional[FeatureDataType] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FeatureRecord(BaseModel):
    """Atomic feature record observed for an entity."""

    model_config = ConfigDict(extra="ignore")

    entity_id: str = Field(..., description="Entity identifier (deal id, property id)")
    entity_type: str = Field("deal", description="Entity type discriminator")
    feature_name: str = Field(..., description="Name of the feature")
    value: Any = Field(..., description="Feature value")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field("pipeline", description="Originating agent or ingestion source")
    partition_key: Optional[str] = Field(None, description="Partition routing key")


class FeatureVector(BaseModel):
    """Consolidated multi-feature snapshot for model scoring or analytics."""

    model_config = ConfigDict(extra="ignore")

    entity_id: str = Field(..., description="Target entity ID (e.g., deal_id)")
    entity_type: str = Field("deal", description="Target entity type")
    features: Dict[str, Any] = Field(default_factory=dict, description="Feature dictionary")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field("1.0.0", description="Feature set schema version")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplementary metadata")

    def get(self, feature_name: str, default: Any = None) -> Any:
        """Retrieve a specific feature value with optional default."""
        return self.features.get(feature_name, default)

    def has_feature(self, feature_name: str) -> bool:
        """Check if feature is present in the vector."""
        return feature_name in self.features

    def to_numeric_array(self, ordered_keys: Optional[Sequence[str]] = None) -> List[float]:
        """Extract numeric features as an ordered floating-point array for model inference."""
        keys = ordered_keys if ordered_keys is not None else sorted(self.features.keys())
        result: List[float] = []
        for key in keys:
            val = self.features.get(key)
            if val is None:
                result.append(0.0)
            elif isinstance(val, (int, float)):
                result.append(float(val))
            elif isinstance(val, bool):
                result.append(1.0 if val else 0.0)
            else:
                try:
                    result.append(float(val))
                except (ValueError, TypeError):
                    result.append(0.0)
        return result


class FeatureStreamEvent(BaseModel):
    """In-flight ingestion event traveling through streaming buffer."""

    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stream_name: str = Field("real_estate_underwriting_stream")
    entity_id: str
    entity_type: str = Field("deal")
    payload: Dict[str, Any] = Field(default_factory=dict)
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: FeatureStreamStatus = Field(FeatureStreamStatus.BUFFERED)
    retry_count: int = Field(0, ge=0)
    error_message: Optional[str] = None


class StreamBufferConfig(BaseModel):
    """Streaming buffer sizing and durability configuration."""

    model_config = ConfigDict(extra="ignore")

    buffer_size: int = Field(1000, gt=0, description="Max in-memory buffered records before flush")
    flush_interval_seconds: float = Field(5.0, gt=0.0, description="Max dwell time before flush")
    max_retries: int = Field(3, ge=0, description="Max delivery retries before dead-lettering")
    dead_letter_queue_enabled: bool = Field(True, description="Capture failed events")


class ParquetPartitionSpec(BaseModel):
    """Partitioning and encoding configuration for columnar Parquet files."""

    model_config = ConfigDict(extra="ignore")

    partition_columns: List[str] = Field(
        default_factory=lambda: ["property_type", "vintage_year"],
        description="Columns to partition directory structure by",
    )
    compression: str = Field("snappy", description="Parquet compression codec (snappy, gzip, zstd)")
    row_group_size: int = Field(10000, gt=0, description="Rows per Parquet row group")
    dictionary_encoding: bool = Field(True, description="Enable dictionary encoding for low cardinality")
    enable_statistics: bool = Field(True, description="Calculate min/max column statistics")


class FeatureStoreManifest(BaseModel):
    """Catalog manifest recording table state, partitions, and file inventory."""

    model_config = ConfigDict(extra="ignore")

    dataset_id: str
    store_path: str
    total_records: int = Field(0, ge=0)
    total_files: int = Field(0, ge=0)
    partition_keys: List[str] = Field(default_factory=list)
    feature_names: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_fingerprint: Optional[str] = None


class FeatureStatistics(BaseModel):
    """Descriptive statistics for feature distribution monitoring and drift detection."""

    model_config = ConfigDict(extra="ignore")

    feature_name: str
    count: int = Field(0, ge=0)
    null_count: int = Field(0, ge=0)
    distinct_count: Optional[int] = Field(None, ge=0)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    std_dev: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None

    @property
    def null_rate(self) -> float:
        """Fraction of observations that are null."""
        return (self.null_count / self.count) if self.count > 0 else 0.0


class FeatureQualityReport(BaseModel):
    """Validation audit of features against expected schemas and bounds."""

    model_config = ConfigDict(extra="ignore")

    is_valid: bool
    total_features_checked: int = Field(0, ge=0)
    missing_features: List[str] = Field(default_factory=list)
    null_rate_violations: Dict[str, float] = Field(default_factory=dict)
    range_violations: Dict[str, str] = Field(default_factory=dict)
    validation_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# PyArrow Schema & Table Conversion Helpers
# ---------------------------------------------------------------------------


def to_arrow_schema(definitions: Sequence[FeatureMetadata]) -> pa.Schema:
    """Build a PyArrow Schema from a sequence of FeatureMetadata definitions.

    Standard entity partition fields (entity_id, timestamp) are automatically
    prepended if not explicitly defined in the features list.
    """
    fields: List[pa.Field] = [
        pa.field("entity_id", pa.string(), nullable=False),
        pa.field("timestamp", pa.timestamp("ms", tz="UTC"), nullable=False),
    ]

    existing_names = {"entity_id", "timestamp"}
    for defn in definitions:
        if defn.name not in existing_names:
            fields.append(defn.to_arrow_field())
            existing_names.add(defn.name)

    return pa.schema(fields)


def feature_vectors_to_arrow_table(
    vectors: Sequence[FeatureVector],
    schema: Optional[pa.Schema] = None,
) -> pa.Table:
    """Convert a sequence of FeatureVectors into a columnar PyArrow Table.

    If schema is omitted, dynamically infers schema from the union of features.
    """
    if not vectors:
        if schema is not None:
            return schema.empty_table()
        empty_schema = pa.schema([
            pa.field("entity_id", pa.string(), nullable=False),
            pa.field("timestamp", pa.timestamp("ms", tz="UTC"), nullable=False),
        ])
        return empty_schema.empty_table()

    # If schema provided, conform rows to schema
    if schema is not None:
        col_names = schema.names
        data_by_col: Dict[str, List[Any]] = {name: [] for name in col_names}

        for vec in vectors:
            for name in col_names:
                if name == "entity_id":
                    data_by_col[name].append(vec.entity_id)
                elif name == "timestamp":
                    data_by_col[name].append(vec.timestamp)
                elif name == "entity_type":
                    data_by_col[name].append(vec.entity_type)
                elif name == "schema_version":
                    data_by_col[name].append(vec.schema_version)
                else:
                    data_by_col[name].append(vec.features.get(name))

        arrays = []
        for field in schema:
            arrays.append(pa.array(data_by_col[field.name], type=field.type))
        return pa.Table.from_arrays(arrays, schema=schema)

    # Inferred schema path
    all_feature_keys = sorted({k for vec in vectors for k in vec.features.keys()})
    names = ["entity_id", "timestamp", "entity_type"] + all_feature_keys

    entity_ids = [v.entity_id for v in vectors]
    timestamps = [v.timestamp for v in vectors]
    entity_types = [v.entity_type for v in vectors]

    arrays = [
        pa.array(entity_ids, type=pa.string()),
        pa.array(timestamps, type=pa.timestamp("ms", tz="UTC")),
        pa.array(entity_types, type=pa.string()),
    ]

    for key in all_feature_keys:
        vals = [v.features.get(key) for v in vectors]
        arrays.append(pa.array(vals))

    return pa.Table.from_arrays(arrays, names=names)


def feature_records_to_arrow_table(
    records: Sequence[FeatureRecord],
) -> pa.Table:
    """Convert a sequence of atomic FeatureRecord instances into a PyArrow Table."""
    if not records:
        schema = pa.schema([
            pa.field("entity_id", pa.string(), nullable=False),
            pa.field("entity_type", pa.string(), nullable=False),
            pa.field("feature_name", pa.string(), nullable=False),
            pa.field("value_str", pa.string(), nullable=True),
            pa.field("timestamp", pa.timestamp("ms", tz="UTC"), nullable=False),
            pa.field("source", pa.string(), nullable=False),
            pa.field("partition_key", pa.string(), nullable=True),
        ])
        return schema.empty_table()

    return pa.Table.from_arrays(
        [
            pa.array([r.entity_id for r in records], type=pa.string()),
            pa.array([r.entity_type for r in records], type=pa.string()),
            pa.array([r.feature_name for r in records], type=pa.string()),
            pa.array(
                [
                    json.dumps(r.value)
                    if isinstance(r.value, (dict, list))
                    else str(r.value)
                    if r.value is not None
                    else None
                    for r in records
                ],
                type=pa.string(),
            ),
            pa.array([r.timestamp for r in records], type=pa.timestamp("ms", tz="UTC")),
            pa.array([r.source for r in records], type=pa.string()),
            pa.array([r.partition_key for r in records], type=pa.string()),
        ],
        names=[
            "entity_id",
            "entity_type",
            "feature_name",
            "value_str",
            "timestamp",
            "source",
            "partition_key",
        ],
    )
