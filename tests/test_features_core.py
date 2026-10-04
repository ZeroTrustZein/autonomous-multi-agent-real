"""Comprehensive unit and integration tests for feature store core algorithms and primary logic (Stage 3/10: Core Logic)."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from autonomous_multi_agent_real.features.buffer import (
    StreamFeatureBuffer,
)
from autonomous_multi_agent_real.features.extractor import (
    FeatureExtractor,
    WindowedAggregator,
)
from autonomous_multi_agent_real.features.quality import (
    FeatureQualityEngine,
)
from autonomous_multi_agent_real.features.registry import (
    FeatureRegistry,
    get_default_registry,
)
from autonomous_multi_agent_real.features.storage import (
    ParquetFeatureStore,
)
from autonomous_multi_agent_real.features.types import (
    FeatureCategory,
    FeatureDataType,
    FeatureMetadata,
    FeatureRecord,
    FeatureStreamEvent,
    FeatureTimeWindow,
    FeatureVector,
    ParquetPartitionSpec,
    StreamBufferConfig,
)
from autonomous_multi_agent_real.types import (
    DealMetrics,
    DebtSizingResult,
    FinancingTerms,
    MonteCarloSimulationResult,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnitMixItem,
    WaterfallResult,
)


@pytest.fixture
def sample_property_deal() -> PropertyDeal:
    """Fixture providing a standard multi-family underwriting deal."""
    return PropertyDeal(
        id="deal-cre-austin-101",
        title="Austin Urban Flats",
        address="100 Congress Ave, Austin, TX",
        property_type=PropertyType.MULTI_FAMILY,
        gross_square_feet=45000.0,
        unit_mix=[
            UnitMixItem(
                unit_type="1BR",
                count=30,
                square_feet=750.0,
                current_rent=1600.0,
                market_rent=1800.0,
            ),
            UnitMixItem(
                unit_type="2BR",
                count=20,
                square_feet=1100.0,
                current_rent=2200.0,
                market_rent=2500.0,
            ),
        ],
        purchase_price=8000000.0,
        rehab_budget=500000.0,
        current_occupancy_pct=0.92,
        market_occupancy_pct=0.95,
        annual_rent_growth_pct=0.03,
        annual_expense_growth_pct=0.025,
        hold_period_years=5,
        exit_cap_rate=0.06,
        selling_costs_pct=0.02,
        expenses=OperatingExpenses(
            property_taxes=110000.0,
            insurance=45000.0,
            repairs_and_maintenance=50000.0,
            property_management_pct=0.08,
            utilities=25000.0,
            admin_and_legal=15000.0,
            replacement_reserves_per_unit=300.0,
        ),
        financing=FinancingTerms(
            purchase_price=8000000.0,
            down_payment_pct=0.25,
            interest_rate=0.065,
            amortization_years=30,
            loan_term_years=10,
            interest_only_months=12,
            closing_costs_pct=0.02,
        ),
    )


@pytest.fixture
def temp_store_dir() -> str:
    """Create a temporary directory for Parquet storage tests and cleanup afterwards."""
    path = tempfile.mkdtemp(prefix="test_feature_store_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


# ===========================================================================
# 1. Feature Registry & Catalog Tests
# ===========================================================================


def test_default_registry_initialization():
    """Verify default institutional CRE registry contains required features."""
    reg = get_default_registry()
    features = reg.list_features()
    assert len(features) >= 15

    # Check key features presence
    assert reg.has_feature("unit_count")
    assert reg.has_feature("in_place_noi")
    assert reg.has_feature("ltv_ratio")
    assert reg.has_feature("break_even_occupancy")
    assert reg.has_feature("purchase_price_per_unit")

    # Category filtering
    prop_feats = reg.list_features(category=FeatureCategory.PROPERTY)
    assert any(f.name == "unit_count" for f in prop_feats)
    assert not any(f.name == "ltv_ratio" for f in prop_feats)

    # Tag filtering
    yield_feats = reg.list_features(tags=["yield"])
    assert any(f.name == "in_place_cap_rate" for f in yield_feats)


def test_registry_custom_derived_computation():
    """Verify registration and topological computation of custom derived features."""
    reg = FeatureRegistry()

    reg.register(
        FeatureMetadata(
            name="purchase_price",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.FLOAT,
        )
    )
    reg.register(
        FeatureMetadata(
            name="unit_count",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.INT,
        )
    )

    # Derived 1: price per unit
    reg.register_derived(
        FeatureMetadata(
            name="price_per_unit",
            category=FeatureCategory.DERIVED,
            data_type=FeatureDataType.FLOAT,
        ),
        compute_fn=lambda f: f["purchase_price"] / f["unit_count"],
        dependencies=["purchase_price", "unit_count"],
    )

    # Derived 2: tier tag based on price_per_unit (depends on another derived feature)
    reg.register_derived(
        FeatureMetadata(
            name="price_tier",
            category=FeatureCategory.DERIVED,
            data_type=FeatureDataType.STRING,
        ),
        compute_fn=lambda f: "luxury" if f["price_per_unit"] > 150000.0 else "workforce",
        dependencies=["price_per_unit"],
    )

    raw = {"purchase_price": 10000000.0, "unit_count": 50}
    enriched = reg.compute_derived(raw)

    assert enriched["price_per_unit"] == 200000.0
    assert enriched["price_tier"] == "luxury"


def test_registry_vector_validation():
    """Verify registry validates FeatureVector against range and nullability rules."""
    reg = FeatureRegistry()
    reg.register(
        FeatureMetadata(
            name="dscr",
            category=FeatureCategory.DEBT,
            data_type=FeatureDataType.FLOAT,
            is_nullable=False,
            min_value=1.0,
            max_value=3.0,
        )
    )

    # Valid vector
    valid_vec = FeatureVector(
        entity_id="deal-1",
        features={"dscr": 1.45},
    )
    report_valid = reg.validate_vector(valid_vec)
    assert report_valid.is_valid
    assert len(report_valid.missing_features) == 0
    assert len(report_valid.range_violations) == 0

    # Range violation vector
    violating_vec = FeatureVector(
        entity_id="deal-2",
        features={"dscr": 0.85},
    )
    report_viol = reg.validate_vector(violating_vec)
    assert not report_viol.is_valid
    assert "dscr" in report_viol.range_violations

    # Missing non-nullable feature
    missing_vec = FeatureVector(
        entity_id="deal-3",
        features={},
    )
    report_missing = reg.validate_vector(missing_vec)
    assert not report_missing.is_valid
    assert "dscr" in report_missing.missing_features


# ===========================================================================
# 2. Feature Extractor & Streaming Window Aggregations
# ===========================================================================


def test_feature_extractor_from_deal(sample_property_deal):
    """Verify feature extraction directly from a PropertyDeal model."""
    extractor = FeatureExtractor()
    vector = extractor.extract_from_deal(sample_property_deal)

    assert vector.entity_id == "deal-cre-austin-101"
    assert vector.entity_type == "deal"
    assert vector.has_feature("unit_count")
    assert vector.get("unit_count") == 50
    assert vector.get("total_square_feet") == 45000.0
    assert vector.get("purchase_price") == 8000000.0
    assert vector.get("in_place_noi") > 0.0
    assert vector.get("in_place_cap_rate") > 0.0

    # Check auto-computed derived features
    assert vector.has_feature("purchase_price_per_unit")
    assert vector.get("purchase_price_per_unit") == 160000.0
    assert vector.get("total_acquisition_basis") == 8500000.0
    assert vector.get("yield_on_cost") > 0.0


def test_feature_extractor_from_deal_dict():
    """Verify feature extraction from a raw dictionary payload."""
    extractor = FeatureExtractor()
    deal_dict = {
        "id": "deal-dict-202",
        "purchase_price": 5000000.0,
        "rehab_budget": 250000.0,
        "gross_square_feet": 20000.0,
        "total_units": 20,
        "unit_mix": [{"count": 20, "current_rent": 1500.0, "market_rent": 1700.0}],
        "expenses": {
            "property_taxes": 60000.0,
            "insurance": 20000.0,
            "repairs_and_maintenance": 25000.0,
        },
    }
    vector = extractor.extract_from_deal(deal_dict)
    assert vector.entity_id == "deal-dict-202"
    assert vector.get("purchase_price") == 5000000.0
    assert vector.get("purchase_price_per_unit") == 250000.0
    assert vector.get("total_acquisition_basis") == 5250000.0


def test_feature_extractor_from_underwrite(sample_property_deal):
    """Verify enriched feature extraction with underwriting results."""
    extractor = FeatureExtractor()

    debt_res = DebtSizingResult(
        loan_amount=6000000.0,
        equity_required=2500000.0,
        monthly_payment=37924.0,
        annual_debt_service=455088.0,
        ltv_ratio=0.75,
        dscr_year1=1.35,
        debt_yield_pct=0.102,
        binding_constraint="LTV",
    )
    deal_metrics = DealMetrics(
        unlevered_irr=0.125,
        levered_irr=0.182,
        equity_multiple=1.92,
        net_present_value=750000.0,
        average_cash_on_cash=0.085,
        entry_cap_rate=0.062,
        exit_cap_rate=0.065,
        min_dscr=1.35,
        average_dscr=1.42,
    )
    mc_res = MonteCarloSimulationResult(
        iterations=500,
        mean_levered_irr=0.178,
        std_levered_irr=0.032,
        p10_irr=0.138,
        p50_irr=0.179,
        p90_irr=0.215,
        probability_negative_irr=0.02,
        probability_dscr_breach=0.03,
        mean_equity_multiple=1.95,
        p10_equity_multiple=1.60,
        p90_equity_multiple=2.30,
        var_95_irr=0.05,
        cvar_95_irr=0.08,
    )
    wf_res = WaterfallResult(
        lp_equity_invested=2250000.0,
        gp_equity_invested=250000.0,
        lp_total_distributions=4500000.0,
        gp_total_distributions=750000.0,
        gp_total_promote=250000.0,
        lp_irr=0.165,
        gp_irr=0.285,
        lp_equity_multiple=2.0,
        gp_equity_multiple=3.0,
    )

    underwrite_obj = {
        "debt_sizing": debt_res,
        "deal_metrics": deal_metrics,
        "monte_carlo": mc_res,
        "waterfall": wf_res,
    }

    vector = extractor.extract_from_underwrite(sample_property_deal, underwrite_obj)
    assert vector.get("loan_amount") == 6000000.0
    assert vector.get("ltv_ratio") == 0.75
    assert vector.get("dscr_year1") == 1.35
    assert vector.get("dscr_cushion") == pytest.approx(0.35, rel=1e-3)
    assert vector.get("levered_irr") == 0.182
    assert vector.get("equity_multiple") == 1.92
    assert vector.get("mean_irr") == 0.178
    assert vector.get("lp_net_irr") == 0.165
    assert vector.get("total_promote_dollars") == 250000.0

    # Verify atomic records generation
    records = extractor.extract_records(sample_property_deal, underwrite_obj)
    assert len(records) > 15
    assert any(r.feature_name == "levered_irr" and r.value == 0.182 for r in records)


def test_windowed_aggregator_and_streaming_rollups():
    """Verify sliding window calculations (mean, std, min, max, ema, momentum)."""
    agg = WindowedAggregator(window_seconds=10.0, ema_alpha=0.5)
    now = datetime.now(timezone.utc)

    # Ingest series: 10.0, 20.0, 30.0
    agg.add(10.0, dt=now - timedelta(seconds=5))
    agg.add(20.0, dt=now - timedelta(seconds=3))
    agg.add(30.0, dt=now)

    assert agg.count == 3
    assert agg.mean == 20.0
    assert agg.min_value == 10.0
    assert agg.max_value == 30.0
    assert agg.momentum == 20.0
    assert agg.std_dev == pytest.approx(10.0, rel=1e-3)
    # EMA: step 1 = 10, step 2 = 0.5*20 + 0.5*10 = 15, step 3 = 0.5*30 + 0.5*15 = 22.5
    assert agg.ema == pytest.approx(22.5, rel=1e-3)

    # Eviction test: add an observation 12s after first sample, which evicts the first two samples
    agg.add(50.0, dt=now + timedelta(seconds=7))
    assert agg.count == 2
    assert agg.max_value == 50.0

    # Test via FeatureExtractor helper
    extractor = FeatureExtractor()
    rollup = extractor.update_window_aggregation(
        entity_id="austin-101",
        feature_name="market_cap_rate",
        value=0.055,
        window=FeatureTimeWindow.REALTIME,
    )
    assert "market_cap_rate_realtime_mean" in rollup
    assert rollup["market_cap_rate_realtime_mean"] == 0.055


def test_extract_from_stream_event():
    """Verify unpacking of real-time FeatureStreamEvent into records."""
    extractor = FeatureExtractor()
    event = FeatureStreamEvent(
        entity_id="deal-stream-999",
        entity_type="deal",
        payload={
            "features": {
                "in_place_cap_rate": 0.062,
                "dscr": 1.40,
                "ltv": 0.70,
            },
        },
    )
    records = extractor.extract_from_stream_event(event)
    assert len(records) == 3
    rec_dict = {r.feature_name: r.value for r in records}
    assert rec_dict["in_place_cap_rate"] == 0.062
    assert rec_dict["dscr"] == 1.40
    assert rec_dict["ltv"] == 0.70


# ===========================================================================
# 3. Parquet Feature Store & Columnar Persistence
# ===========================================================================


def test_parquet_feature_store_write_and_query(temp_store_dir):
    """Verify writing feature vectors to Parquet, updating manifest, and querying."""
    store = ParquetFeatureStore(
        base_path=temp_store_dir,
        partition_spec=ParquetPartitionSpec(partition_columns=["date"]),
    )

    now = datetime.now(timezone.utc)
    v1 = FeatureVector(
        entity_id="deal-1",
        features={"noi": 500000.0, "cap_rate": 0.06, "dscr": 1.35},
        timestamp=now - timedelta(hours=2),
    )
    v2 = FeatureVector(
        entity_id="deal-2",
        features={"noi": 750000.0, "cap_rate": 0.055, "dscr": 1.50},
        timestamp=now - timedelta(hours=1),
    )

    written = store.write_vectors([v1, v2])
    assert len(written) > 0
    assert all(f.exists() for f in written)

    # Check manifest
    manifest = store.get_manifest()
    assert manifest.total_records == 2
    assert "noi" in manifest.feature_names
    assert "cap_rate" in manifest.feature_names
    assert "dscr" in manifest.feature_names

    # Query all
    tbl = store.query()
    assert tbl.num_rows == 2

    # Query filtered by entity_ids
    tbl_filtered = store.query(entity_ids=["deal-1"])
    assert tbl_filtered.num_rows == 1
    assert tbl_filtered["entity_id"][0].as_py() == "deal-1"

    # Query projection
    tbl_proj = store.query(feature_names=["cap_rate"])
    assert "cap_rate" in tbl_proj.column_names
    assert "noi" not in tbl_proj.column_names


def test_parquet_feature_store_as_of_time_travel(temp_store_dir):
    """Verify point-in-time time travel lookup prevents future information leakage."""
    store = ParquetFeatureStore(base_path=temp_store_dir)
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Entity 'deal-alpha' observed at t0 and t2
    vec_t0 = FeatureVector(
        entity_id="deal-alpha",
        features={"noi": 400000.0, "cap_rate": 0.07},
        timestamp=t0,
    )
    vec_t2 = FeatureVector(
        entity_id="deal-alpha",
        features={"noi": 480000.0, "cap_rate": 0.065},
        timestamp=t2,
    )
    store.write_vectors([vec_t0, vec_t2])

    # As-of query at t1 (before t2): MUST return t0 state, NOT t2 state
    as_of_t1 = store.get_as_of_vector("deal-alpha", as_of=t1)
    assert as_of_t1 is not None
    assert as_of_t1.get("noi") == 400000.0
    assert as_of_t1.get("cap_rate") == 0.07

    # As-of query at t2 or later: returns t2 state
    as_of_t2 = store.get_as_of_vector("deal-alpha", as_of=t2)
    assert as_of_t2 is not None
    assert as_of_t2.get("noi") == 480000.0

    # As-of query before t0: returns None
    as_of_prior = store.get_as_of_vector(
        "deal-alpha", as_of=datetime(2025, 12, 1, tzinfo=timezone.utc)
    )
    assert as_of_prior is None


def test_parquet_feature_store_records_and_compaction(temp_store_dir):
    """Verify atomic record writing and partition file compaction."""
    store = ParquetFeatureStore(
        base_path=temp_store_dir,
        partition_spec=ParquetPartitionSpec(partition_columns=["date"]),
    )
    now = datetime.now(timezone.utc)

    # Write chunk 1
    r1 = [
        FeatureRecord(
            entity_id="deal-c1", entity_type="deal", feature_name="irr", value=0.15, timestamp=now
        ),
    ]
    store.write_records(r1)

    # Write chunk 2 (same partition)
    r2 = [
        FeatureRecord(
            entity_id="deal-c2", entity_type="deal", feature_name="irr", value=0.18, timestamp=now
        ),
    ]
    store.write_records(r2)

    files_before = store.list_parquet_files()
    assert len(files_before) == 2

    # Compact partitions
    compacted_count = store.compact_partitions()
    assert compacted_count == 2
    files_after = store.list_parquet_files()
    assert len(files_after) == 1

    # Verify data integrity preserved
    tbl = store.read_all_tables()
    assert tbl.num_rows == 2


# ===========================================================================
# 4. Real-time Streaming Feature Buffer
# ===========================================================================


def test_stream_feature_buffer_capacity_flush():
    """Verify streaming buffer auto-flushes when max_records capacity is reached."""
    flushed_batches: List[List[FeatureRecord]] = []

    def sink(records: List[FeatureRecord]) -> None:
        flushed_batches.append(records)

    config = StreamBufferConfig(buffer_size=3, flush_interval_seconds=60.0)
    buffer = StreamFeatureBuffer(config=config, flush_sink=sink)

    now = datetime.now(timezone.utc)
    # Add 2 records -> buffer holds them
    buffer.add_record(
        FeatureRecord(
            entity_id="d1", entity_type="deal", feature_name="f1", value=1.0, timestamp=now
        )
    )
    buffer.add_record(
        FeatureRecord(
            entity_id="d1", entity_type="deal", feature_name="f2", value=2.0, timestamp=now
        )
    )
    assert len(flushed_batches) == 0
    assert buffer.get_status().records_in_buffer == 2

    # Add 3rd record -> triggers auto-flush
    buffer.add_record(
        FeatureRecord(
            entity_id="d1", entity_type="deal", feature_name="f3", value=3.0, timestamp=now
        )
    )
    assert len(flushed_batches) == 1
    assert len(flushed_batches[0]) == 3
    assert buffer.get_status().records_in_buffer == 0
    assert buffer.get_status().total_records_flushed == 3


def test_stream_feature_buffer_vector_and_event_ingestion():
    """Verify adding FeatureVectors and FeatureStreamEvents into buffer."""
    flushed_records: List[FeatureRecord] = []

    buffer = StreamFeatureBuffer(
        config=StreamBufferConfig(buffer_size=100),
        flush_sink=lambda recs: flushed_records.extend(recs),
    )

    # Ingest vector
    vec = FeatureVector(
        entity_id="deal-vec-1",
        features={"noi": 300000.0, "cap": 0.06},
    )
    buffer.add_vector(vec)

    # Ingest stream event
    ev = FeatureStreamEvent(
        entity_id="deal-ev-2",
        entity_type="deal",
        payload={"features": {"dscr": 1.42}},
    )
    buffer.add_event(ev)

    # Explicit flush
    flushed_count = buffer.flush()
    assert flushed_count == 3
    assert len(flushed_records) == 3
    status = buffer.get_status()
    assert status.total_records_ingested == 3
    assert status.is_healthy


def test_stream_feature_buffer_watermark_rejection():
    """Verify events older than the watermark delay are dropped as stale."""
    buffer = StreamFeatureBuffer(
        config=StreamBufferConfig(buffer_size=10),
        watermark_delay_seconds=30.0,
    )

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=60.0)
    stale_rec = FeatureRecord(
        entity_id="deal-stale",
        entity_type="deal",
        feature_name="old_metric",
        value=100.0,
        timestamp=stale_time,
    )

    accepted = buffer.add_record(stale_rec)
    assert not accepted
    status = buffer.get_status()
    assert status.dropped_records == 1
    assert status.records_in_buffer == 0


# ===========================================================================
# 5. Quality, Profiling & Drift Detection
# ===========================================================================


def test_feature_quality_statistics_calculation():
    """Verify statistical summary generation for numeric and categorical distributions."""
    engine = FeatureQualityEngine()
    vectors = [
        FeatureVector(entity_id="d1", features={"cap_rate": 0.05, "status": "active"}),
        FeatureVector(entity_id="d2", features={"cap_rate": 0.06, "status": "pending"}),
        FeatureVector(entity_id="d3", features={"cap_rate": 0.07, "status": "active"}),
        FeatureVector(entity_id="d4", features={"cap_rate": None, "status": "active"}),
    ]

    stats = engine.compute_statistics(vectors, "cap_rate")
    assert stats.count == 4
    assert stats.null_count == 1
    assert stats.null_rate == 0.25
    assert stats.min_value == 0.05
    assert stats.max_value == 0.07
    assert stats.mean == pytest.approx(0.06, rel=1e-3)
    assert stats.p50 == pytest.approx(0.06, rel=1e-3)


def test_feature_quality_audit_rules():
    """Verify dataset quality auditing against schema completeness and bounds."""
    reg = FeatureRegistry()
    reg.register(
        FeatureMetadata(
            name="occupancy",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.FLOAT,
            is_nullable=False,
            min_value=0.50,
            max_value=1.00,
        )
    )

    engine = FeatureQualityEngine(registry=reg)

    # Valid dataset
    valid_vectors = [
        FeatureVector(entity_id="d1", features={"occupancy": 0.95}),
        FeatureVector(entity_id="d2", features={"occupancy": 0.90}),
    ]
    report_valid = engine.audit_quality(valid_vectors)
    assert report_valid.is_valid

    # Dataset with violation (< 0.50)
    invalid_vectors = [
        FeatureVector(entity_id="d1", features={"occupancy": 0.95}),
        FeatureVector(entity_id="d2", features={"occupancy": 0.40}),
    ]
    report_invalid = engine.audit_quality(invalid_vectors)
    assert not report_invalid.is_valid
    assert "occupancy" in report_invalid.range_violations


def test_feature_drift_detection():
    """Verify statistical drift detection between baseline and current distributions."""
    engine = FeatureQualityEngine()

    baseline = engine.compute_statistics(
        [FeatureVector(entity_id=f"b{i}", features={"dscr": 1.35 + (i * 0.01)}) for i in range(20)],
        "dscr",
    )

    # Same distribution -> no drift
    current_stable = engine.compute_statistics(
        [FeatureVector(entity_id=f"s{i}", features={"dscr": 1.36 + (i * 0.01)}) for i in range(20)],
        "dscr",
    )
    drift_stable = engine.detect_drift(baseline, current_stable, z_threshold=2.0)
    assert not drift_stable["has_drift"]

    # Shifted distribution (mean shifted upwards significantly)
    current_shifted = engine.compute_statistics(
        [FeatureVector(entity_id=f"x{i}", features={"dscr": 1.85 + (i * 0.01)}) for i in range(20)],
        "dscr",
    )
    drift_detected = engine.detect_drift(baseline, current_shifted, z_threshold=2.0)
    assert drift_detected["has_drift"]
    assert drift_detected["mean_shift_z"] > 2.0
    assert len(drift_detected["reasons"]) > 0
