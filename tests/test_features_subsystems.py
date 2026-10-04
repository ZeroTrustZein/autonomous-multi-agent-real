"""Comprehensive unit and integration test suite for Stage 4: Subsystems.

Covers:
1. Online feature store (low-latency cache, TTL, LRU/FIFO eviction, atomic records).
2. Feature serving service (multi-tier lookup, offline fallback, default imputation).
3. Materialization and synchronization engine (offline-to-online sync, buffer flush, backfill, audit).
4. Point-in-time historical joins and training dataset generator (as-of joins, zero lookahead bias).
5. Feature context enricher (cohort percentiles, z-scores, deliberation markdown brief).
6. Pipeline feature interceptor (stage transitions, stream events, automated persistence).
7. Feature store coordinator facade (unified management of all subsystems).
8. End-to-end DealPipeline and DealRepository integration.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pytest

from autonomous_multi_agent_real.engine.workflow import DealPipeline
from autonomous_multi_agent_real.features.buffer import StreamFeatureBuffer
from autonomous_multi_agent_real.features.coordinator import (
    create_feature_store,
)
from autonomous_multi_agent_real.features.enricher import FeatureContextEnricher
from autonomous_multi_agent_real.features.extractor import FeatureExtractor
from autonomous_multi_agent_real.features.interceptor import PipelineFeatureInterceptor
from autonomous_multi_agent_real.features.materialization import MaterializationEngine
from autonomous_multi_agent_real.features.registry import FeatureRegistry
from autonomous_multi_agent_real.features.serving import (
    FeatureServingService,
    OnlineFeatureStore,
)
from autonomous_multi_agent_real.features.storage import ParquetFeatureStore
from autonomous_multi_agent_real.features.training import (
    TrainingDatasetGenerator,
)
from autonomous_multi_agent_real.features.types import (
    EnrichedFeatureContext,
    FeatureCategory,
    FeatureDataType,
    FeatureMetadata,
    FeatureRecord,
    FeatureStreamEvent,
    FeatureVector,
    ObservationTarget,
    OnlineStoreConfig,
)
from autonomous_multi_agent_real.storage.repository import DealRepository, get_benchmark_deals
from autonomous_multi_agent_real.types import (
    FinancingTerms,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnitMixItem,
    WorkflowStage,
)


@pytest.fixture
def temp_dir():
    """Create and cleanly tear down a temporary test directory."""
    d = tempfile.mkdtemp(prefix="fs_subsystems_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_deal():
    """Construct a clean multi-family deal instance."""
    return PropertyDeal(
        id="test-subsystem-deal-01",
        title="Austin Urban Flats",
        address="300 Colorado St, Austin, TX",
        property_type=PropertyType.MULTI_FAMILY,
        gross_square_feet=18000.0,
        unit_mix=[
            UnitMixItem(
                unit_type="1BR",
                count=12,
                square_feet=750.0,
                current_rent=1600.0,
                market_rent=1800.0,
            ),
            UnitMixItem(
                unit_type="2BR",
                count=6,
                square_feet=1000.0,
                current_rent=2200.0,
                market_rent=2500.0,
            ),
        ],
        purchase_price=3600000.0,
        rehab_budget=150000.0,
        current_occupancy_pct=0.92,
        market_occupancy_pct=0.95,
        annual_rent_growth_pct=0.035,
        annual_expense_growth_pct=0.025,
        hold_period_years=5,
        exit_cap_rate=0.0575,
        expenses=OperatingExpenses(
            property_taxes=45000.0,
            insurance=18000.0,
            utilities=12000.0,
            repairs_and_maintenance=16000.0,
            property_management_pct=0.04,
            replacement_reserves_per_unit=300.0,
        ),
        financing=FinancingTerms(
            purchase_price=3600000.0,
            down_payment_pct=0.25,
            interest_rate=0.065,
            amortization_years=30,
            loan_term_years=10,
        ),
    )


# ===========================================================================
# 1. Online Feature Store Tests
# ===========================================================================


def test_online_store_lifecycle_and_crud():
    """Verify put, get, batch get, and invalidation in online store."""
    config = OnlineStoreConfig(max_entries=10, eviction_policy="lru")
    store = OnlineFeatureStore(config=config)

    v1 = FeatureVector(
        entity_id="deal-1",
        features={"cap_rate": 0.06, "occupancy": 0.95},
    )
    v2 = FeatureVector(
        entity_id="deal-2",
        features={"cap_rate": 0.055, "occupancy": 0.92},
    )

    store.put_vector(v1)
    store.put_vector(v2)

    assert store.size() == 2
    res_v1 = store.get_vector("deal-1")
    assert res_v1 is not None
    assert res_v1.features["cap_rate"] == 0.06

    # Batch get
    batch = store.get_vectors(["deal-1", "deal-2", "non-existent"])
    assert len(batch) == 2

    # Invalidate
    assert store.invalidate("deal-1") is True
    assert store.get_vector("deal-1") is None
    assert store.size() == 1


def test_online_store_ttl_expiration():
    """Verify that cached vectors expire after TTL threshold."""
    config = OnlineStoreConfig(ttl_seconds=0.05, max_entries=100)
    store = OnlineFeatureStore(config=config)

    vec = FeatureVector(entity_id="fast-deal", features={"noi": 250000.0})
    store.put_vector(vec)

    assert store.get_vector("fast-deal") is not None

    time.sleep(0.08)
    assert store.get_vector("fast-deal") is None
    stats = store.get_stats()
    assert stats["evictions"] >= 1
    assert stats["misses"] >= 1


def test_online_store_lru_capacity_eviction():
    """Verify that LRU eviction removes the least recently accessed vector."""
    config = OnlineStoreConfig(max_entries=3, eviction_policy="lru")
    store = OnlineFeatureStore(config=config)

    for i in range(1, 4):
        store.put_vector(FeatureVector(entity_id=f"d{i}", features={"v": i}))

    assert store.size() == 3

    # Access d1 so that d2 becomes least recently used
    _ = store.get_vector("d1")

    # Insert d4, which should evict d2
    store.put_vector(FeatureVector(entity_id="d4", features={"v": 4}))

    assert store.size() == 3
    assert store.get_vector("d2") is None
    assert store.get_vector("d1") is not None
    assert store.get_vector("d3") is not None
    assert store.get_vector("d4") is not None


def test_online_store_atomic_records_upsert():
    """Verify merging atomic records into online store."""
    store = OnlineFeatureStore()

    records = [
        FeatureRecord(
            entity_id="d-atomic",
            feature_name="debt_yield",
            value=0.095,
        ),
        FeatureRecord(
            entity_id="d-atomic",
            feature_name="dscr",
            value=1.35,
        ),
    ]

    store.put_records(records)
    vec = store.get_vector("d-atomic")
    assert vec is not None
    assert vec.features["debt_yield"] == 0.095
    assert vec.features["dscr"] == 1.35


# ===========================================================================
# 2. Feature Serving Service Tests
# ===========================================================================


def test_feature_serving_service_multi_tier_fallback(temp_dir):
    """Verify online cache hit, offline parquet fallback, and default imputation."""
    reg = FeatureRegistry()
    reg.register(
        FeatureMetadata(
            name="exit_cap_rate",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            default_value=0.060,
        )
    )
    reg.register(
        FeatureMetadata(
            name="market_rent_delta",
            category=FeatureCategory.MARKET,
            data_type=FeatureDataType.FLOAT,
            default_value=0.0,
        )
    )

    offline_path = temp_dir / "offline"
    offline_store = ParquetFeatureStore(base_path=offline_path)
    online_store = OnlineFeatureStore()

    service = FeatureServingService(
        online_store=online_store,
        offline_store=offline_store,
        registry=reg,
    )

    # 1. Entity exists only in offline parquet
    off_vec = FeatureVector(
        entity_id="deal-off",
        features={"exit_cap_rate": 0.055},
    )
    offline_store.write_vectors([off_vec])

    # Cache is cold initially
    assert online_store.get_vector("deal-off") is None

    # Retrieve features - should fall back to offline and warm online cache
    feats = service.get_online_features(
        entity_id="deal-off",
        feature_names=["exit_cap_rate", "market_rent_delta"],
    )

    assert feats["exit_cap_rate"] == 0.055
    # Default imputed for missing feature
    assert feats["market_rent_delta"] == 0.0

    # Cache is now warm
    assert online_store.get_vector("deal-off") is not None


def test_feature_serving_batch_and_matrix():
    """Verify batch retrieval and 2D feature matrix generation."""
    online_store = OnlineFeatureStore()
    online_store.put_vector(FeatureVector(entity_id="d1", features={"cap_rate": 0.05, "dscr": 1.4}))
    online_store.put_vector(
        FeatureVector(entity_id="d2", features={"cap_rate": 0.06, "dscr": 1.25})
    )

    service = FeatureServingService(online_store=online_store)

    # Batch
    batch = service.get_batch_features(["d1", "d2"], feature_names=["cap_rate", "dscr"])
    assert batch["d1"]["cap_rate"] == 0.05
    assert batch["d2"]["dscr"] == 1.25

    # Matrix
    mat = service.get_feature_matrix(["d1", "d2"], feature_names=["cap_rate", "dscr"])
    assert mat["cap_rate"] == [0.05, 0.06]
    assert mat["dscr"] == [1.4, 1.25]


# ===========================================================================
# 3. Materialization & Synchronization Engine Tests
# ===========================================================================


def test_materialization_engine_full_sync(temp_dir, sample_deal):
    """Verify materializing offline parquet into online cache and buffer flushing."""
    offline_store = ParquetFeatureStore(base_path=temp_dir / "offline")
    online_store = OnlineFeatureStore()
    buffer = StreamFeatureBuffer()
    extractor = FeatureExtractor()

    engine = MaterializationEngine(
        offline_store=offline_store,
        online_store=online_store,
        buffer=buffer,
        extractor=extractor,
    )

    # 1. Backfill deal
    job_backfill = engine.backfill_deals([sample_deal], sync_online=False)
    assert job_backfill.status == "completed"
    assert job_backfill.entities_count == 1
    assert online_store.size() == 0  # not synced online yet

    # 2. Materialize offline into online
    job_sync = engine.materialize_to_online()
    assert job_sync.status == "completed"
    assert job_sync.entities_count == 1
    assert online_store.get_vector(sample_deal.id) is not None

    # 3. Stream buffer flush to parquet
    buffer.push(
        FeatureStreamEvent(
            entity_id="stream-deal-99",
            entity_type="deal",
            event_type="update",
            features={"custom_metric": 42.0},
        )
    )
    assert buffer.size() == 1

    job_flush = engine.flush_buffer_to_parquet()
    assert job_flush.status == "completed"
    assert job_flush.features_count == 1
    assert buffer.size() == 0

    # 4. Sync parity audit
    audit = engine.sync_audit()
    assert audit["total_checked"] >= 1
    assert audit["parity_ratio"] > 0.0


# ===========================================================================
# 4. Point-In-Time Joins & Training Dataset Generator Tests
# ===========================================================================


def test_point_in_time_join_prevents_lookahead_leakage(temp_dir):
    """Verify as-of historical join picks features strictly prior to observation time."""
    offline_store = ParquetFeatureStore(base_path=temp_dir / "offline")
    generator = TrainingDatasetGenerator(offline_store=offline_store)

    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 2, 1, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc)

    # Historical state at t0
    v0 = FeatureVector(
        entity_id="leakage-test-deal",
        features={"market_rent": 1500.0, "valuation": 3000000.0},
        timestamp=t0,
    )
    # Future state at t2
    v2 = FeatureVector(
        entity_id="leakage-test-deal",
        features={"market_rent": 1800.0, "valuation": 3500000.0},
        timestamp=t2,
    )
    offline_store.write_vectors([v0, v2])

    # Observation at intermediate time t1 (should see v0, NOT v2)
    obs = [
        ObservationTarget(
            entity_id="leakage-test-deal",
            timestamp=t1,
            label_name="deal_closed",
            label_value=1.0,
        )
    ]

    ds = generator.build_dataset(
        observations=obs,
        dataset_name="leakage_verification_ds",
        feature_names=["market_rent", "valuation"],
    )

    recs = ds.get_records()
    assert len(recs) == 1
    # Point-in-time correctness: must be 1500.0, NOT 1800.0
    assert recs[0]["market_rent"] == 1500.0
    assert recs[0]["valuation"] == 3000000.0
    assert recs[0]["deal_closed"] == 1.0


def test_training_dataset_splits_and_correlations(temp_dir):
    """Verify training dataset train/val/test splits, arrow conversion, and correlations."""
    offline_store = ParquetFeatureStore(base_path=temp_dir / "offline")
    generator = TrainingDatasetGenerator(offline_store=offline_store)

    vectors = []
    observations = []
    base_time = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)

    for i in range(10):
        ts = base_time + timedelta(days=i)
        eid = f"deal-{i:02d}"
        irr = 0.10 + 0.01 * i
        vectors.append(
            FeatureVector(
                entity_id=eid,
                features={"cap_rate": 0.05 + 0.002 * i, "risk_score": 10.0 - i},
                timestamp=ts,
            )
        )
        observations.append(
            ObservationTarget(
                entity_id=eid,
                timestamp=ts + timedelta(hours=1),
                label_name="realized_irr",
                label_value=irr,
            )
        )

    offline_store.write_vectors(vectors)

    ds = generator.build_dataset(
        observations=observations,
        dataset_name="irr_prediction",
        feature_names=["cap_rate", "risk_score"],
        train_ratio=0.7,
        val_ratio=0.2,
        test_ratio=0.1,
    )

    assert ds.metadata.train_count == 7
    assert ds.metadata.val_count == 2
    assert ds.metadata.test_count == 1
    assert ds.total_records == 10

    # Arrow table export
    arrow_tbl = ds.to_arrow_table("train")
    assert isinstance(arrow_tbl, pa.Table)
    assert arrow_tbl.num_rows == 7

    # X, y matrices
    X, y = ds.to_xy("train")
    assert len(y) == 7
    assert len(X["cap_rate"]) == 7

    # Correlations: cap_rate increases with realized_irr -> positive correlation
    corrs = ds.compute_correlations()
    assert "cap_rate" in corrs
    assert corrs["cap_rate"] > 0.90
    assert corrs["risk_score"] < -0.90

    # Parquet export
    export_dir = temp_dir / "ds_export"
    files = ds.export_parquet(export_dir)
    assert "train" in files
    assert files["train"].exists()


# ===========================================================================
# 5. Feature Context Enricher Tests
# ===========================================================================


def test_feature_context_enricher(sample_deal):
    """Verify cohort distribution percentiles, z-scores, and Markdown briefs."""
    enricher = FeatureContextEnricher()

    # Create cohort peers with varying prices
    peers = [
        sample_deal.model_copy(update={"id": "peer-1", "purchase_price": 3000000.0}),
        sample_deal.model_copy(update={"id": "peer-2", "purchase_price": 3500000.0}),
        sample_deal.model_copy(update={"id": "peer-3", "purchase_price": 4000000.0}),
        sample_deal.model_copy(update={"id": "peer-4", "purchase_price": 4500000.0}),
    ]

    enriched = enricher.enrich_deal(
        deal=sample_deal,
        cohort_deals=peers,
        cohort_name="austin_multifamily_peers",
    )

    assert isinstance(enriched, EnrichedFeatureContext)
    assert enriched.entity_id == sample_deal.id
    assert "price_per_unit" in enriched.percentiles
    assert "price_per_unit" in enriched.z_scores
    assert "price_per_unit" in enriched.cohort_medians

    # Brief generation
    brief = enricher.format_deliberation_brief(enriched)
    assert "### Statistical Feature Context" in brief
    assert "austin_multifamily_peers" in brief
    assert "| `price_per_unit` |" in brief


# ===========================================================================
# 6. Pipeline Feature Interceptor Tests
# ===========================================================================


def test_pipeline_feature_interceptor_stage_lifecycle(sample_deal, temp_dir):
    """Verify interceptor responds to stage events and populates buffer and stores."""
    offline_store = ParquetFeatureStore(base_path=temp_dir / "offline")
    online_store = OnlineFeatureStore()
    buffer = StreamFeatureBuffer()

    interceptor = PipelineFeatureInterceptor(
        buffer=buffer,
        online_store=online_store,
        offline_store=offline_store,
        auto_persist_on_complete=True,
    )

    class MockContext:
        def __init__(self, deal):
            self.deal = deal
            self.debt_sizing = None
            self.cash_flows = []
            self.deal_metrics = None
            self.monte_carlo = None

    ctx = MockContext(sample_deal)

    # Trigger stage start & end
    interceptor.on_stage_start(WorkflowStage.INTAKE, ctx)
    assert buffer.size() == 1

    interceptor.on_stage_end(WorkflowStage.INTAKE, ctx)
    assert interceptor.extracted_vectors_count == 1
    assert online_store.get_vector(sample_deal.id) is not None

    # Complete workflow
    interceptor.on_workflow_complete(ctx, underwriting_result=None)
    offline_vec = offline_store.get_latest_vector(sample_deal.id)
    assert offline_vec is not None


# ===========================================================================
# 7. Unified FeatureStoreCoordinator Tests
# ===========================================================================


def test_feature_store_coordinator_unified_facade(temp_dir, sample_deal):
    """Verify all-in-one operations through FeatureStoreCoordinator."""
    coordinator = create_feature_store(base_path=temp_dir / "coordinator")

    # 1. Extract & persist
    vec = coordinator.extract_and_persist(sample_deal)
    assert vec.entity_id == sample_deal.id

    # 2. Serve features
    feats = coordinator.get_features(sample_deal.id, feature_names=["price_per_unit", "cap_rate"])
    assert "price_per_unit" in feats
    assert feats["price_per_unit"] == pytest.approx(200000.0, rel=1e-2)

    # 3. Batch serving
    batch = coordinator.get_batch_features([sample_deal.id])
    assert sample_deal.id in batch

    # 4. Feature matrix
    mat = coordinator.get_feature_matrix([sample_deal.id], feature_names=["price_per_unit"])
    assert len(mat["price_per_unit"]) == 1

    # 5. Enrich deal
    enriched = coordinator.enrich_deal(sample_deal)
    assert enriched.entity_id == sample_deal.id

    # 6. Quality audit
    quality = coordinator.audit_quality()
    assert quality.overall_quality_score > 0.0

    # 7. Parity audit
    audit = coordinator.audit_sync()
    assert audit["parity_ratio"] == 1.0


# ===========================================================================
# 8. End-to-End Pipeline & Repository Integration Tests
# ===========================================================================


def test_deal_pipeline_with_feature_coordinator_integration(temp_dir, sample_deal):
    """Verify DealPipeline automatically executes feature interception into FeatureStoreCoordinator."""
    coordinator = create_feature_store(base_path=temp_dir / "pipeline_coord")

    # Initialize DealPipeline hooked with coordinator
    pipeline = DealPipeline(
        monte_carlo_iterations=50,
        random_seed=42,
        feature_coordinator=coordinator,
    )

    result = pipeline.run(sample_deal)
    assert result.decision is not None

    # Verify features were captured online and offline
    online_vec = coordinator.online_store.get_vector(sample_deal.id)
    assert online_vec is not None
    assert "underwritten_dscr" in online_vec.features
    assert "levered_irr" in online_vec.features
    assert "composite_deal_score" in online_vec.features

    offline_vec = coordinator.offline_store.get_latest_vector(sample_deal.id)
    assert offline_vec is not None
    assert offline_vec.features["composite_deal_score"] == pytest.approx(
        result.committee_score, rel=1e-3
    )


def test_deal_repository_sync_to_feature_store(temp_dir):
    """Verify DealRepository backfills deals directly into FeatureStoreCoordinator."""
    repo = DealRepository(storage_dir=temp_dir / "repo_data")
    coordinator = create_feature_store(base_path=temp_dir / "backfill_coord")

    job = repo.sync_to_feature_store(coordinator)
    assert job.status == "completed"
    assert job.entities_count >= 1

    benchmark_ids = [d.id for d in get_benchmark_deals()]
    for bid in benchmark_ids:
        vec = coordinator.online_store.get_vector(bid)
        assert vec is not None
        assert "price_per_unit" in vec.features
