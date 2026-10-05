"""Feature registry and schema catalog for institutional real estate underwriting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from autonomous_multi_agent_real.features.types import (
    FeatureCategory,
    FeatureDataType,
    FeatureMetadata,
    FeatureQualityReport,
    FeatureVector,
)

DerivedComputeFn = Callable[[Dict[str, Any]], Any]


class FeatureRegistry:
    """Central repository and schema catalog for feature definitions and derived computations."""

    def __init__(self) -> None:
        self._definitions: Dict[str, FeatureMetadata] = {}
        self._derived_computations: Dict[str, DerivedComputeFn] = {}
        self._dependencies: Dict[str, List[str]] = {}

    def register(self, metadata: FeatureMetadata) -> None:
        """Register a feature definition in the registry."""
        self._definitions[metadata.name] = metadata

    def register_derived(
        self,
        metadata: FeatureMetadata,
        compute_fn: DerivedComputeFn,
        dependencies: Optional[Sequence[str]] = None,
    ) -> None:
        """Register a derived feature along with its deterministic calculation function."""
        # Ensure category is marked as DERIVED if not explicitly set
        if metadata.category != FeatureCategory.DERIVED:
            metadata = metadata.model_copy(update={"category": FeatureCategory.DERIVED})
        self.register(metadata)
        self._derived_computations[metadata.name] = compute_fn
        self._dependencies[metadata.name] = list(dependencies or [])

    def get(self, name: str) -> Optional[FeatureMetadata]:
        """Lookup feature metadata by canonical name."""
        return self._definitions.get(name)

    def has_feature(self, name: str) -> bool:
        """Check if feature is registered."""
        return name in self._definitions

    def list_features(
        self,
        category: Optional[FeatureCategory] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> List[FeatureMetadata]:
        """List registered features matching optional category and tag filters."""
        results: List[FeatureMetadata] = []
        target_tags = set(tags) if tags is not None else None

        for meta in self._definitions.values():
            if category is not None and meta.category != category:
                continue
            if target_tags is not None and not target_tags.issubset(set(meta.tags)):
                continue
            results.append(meta)

        return sorted(results, key=lambda m: m.name)

    def list_derived_features(self) -> List[str]:
        """Return names of all registered derived features."""
        return sorted(self._derived_computations.keys())

    def get_dependencies(self, feature_name: str) -> List[str]:
        """Get required upstream features for a derived feature."""
        return list(self._dependencies.get(feature_name, []))

    def compute_derived(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Compute all applicable derived features given an input feature dictionary.

        Resolves dependencies in topological order so derived features can depend
        on other derived features.
        """
        enriched: Dict[str, Any] = dict(features)

        # Determine execution order via simple topological dependency resolution
        unresolved: Set[str] = set(self._derived_computations.keys())
        resolved: List[str] = []

        max_passes = len(unresolved) + 1
        for _ in range(max_passes):
            newly_resolved: List[str] = []
            for name in list(unresolved):
                deps = self._dependencies.get(name, [])
                # A feature can be computed if all its dependencies are already present in enriched or in resolved
                if all(dep in enriched or dep in resolved for dep in deps):
                    newly_resolved.append(name)

            if not newly_resolved:
                break

            for name in newly_resolved:
                resolved.append(name)
                unresolved.remove(name)

        # Compute in resolved order
        for name in resolved:
            compute_fn = self._derived_computations[name]
            try:
                val = compute_fn(enriched)
                if val is not None:
                    enriched[name] = val
            except Exception:
                # If computation fails due to missing optional inputs, leave as None
                enriched[name] = None

        return enriched

    def validate_vector(self, vector: FeatureVector) -> FeatureQualityReport:
        """Validate a FeatureVector against all registered feature definitions and constraints."""
        missing: List[str] = []
        range_violations: Dict[str, str] = {}

        for name, meta in self._definitions.items():
            if not meta.is_nullable and name not in vector.features:
                missing.append(name)
                continue

            val = vector.features.get(name)
            if val is None:
                if not meta.is_nullable:
                    missing.append(name)
                continue

            # Validate range constraints for numeric features
            min_val = getattr(meta, "min_value", None)
            max_val = getattr(meta, "max_value", None)
            if isinstance(val, (int, float)):
                if min_val is not None and val < min_val:
                    range_violations[name] = f"Value {val} below minimum {min_val}"
                elif max_val is not None and val > max_val:
                    range_violations[name] = f"Value {val} above maximum {max_val}"

        is_valid = len(missing) == 0 and len(range_violations) == 0
        return FeatureQualityReport(
            is_valid=is_valid,
            total_features_checked=len(self._definitions),
            missing_features=missing,
            range_violations=range_violations,
            validation_timestamp=datetime.now(timezone.utc),
        )


def get_default_registry() -> FeatureRegistry:
    """Initialize standard CRE feature registry populated with institutional definitions."""
    reg = FeatureRegistry()

    # --- Property Features ---
    reg.register(
        FeatureMetadata(
            name="unit_count",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.INT,
            description="Total rentable residential or commercial units",
            is_nullable=False,
            min_value=1.0,
            tags=["property", "scale"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="total_square_feet",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.FLOAT,
            description="Gross leasable or rentable square footage",
            is_nullable=False,
            min_value=100.0,
            tags=["property", "size"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="purchase_price",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.FLOAT,
            description="Base contracted asset acquisition price",
            is_nullable=False,
            min_value=1000.0,
            tags=["property", "basis"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="rehab_budget",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.FLOAT,
            description="Upfront planned capital improvement and rehabilitation expenditure",
            is_nullable=False,
            default_value=0.0,
            min_value=0.0,
            tags=["property", "capex"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="year_built",
            category=FeatureCategory.PROPERTY,
            data_type=FeatureDataType.INT,
            description="Year property construction was completed",
            is_nullable=True,
            min_value=1800.0,
            max_value=2100.0,
            tags=["property", "vintage"],
        )
    )

    # --- Financial Features ---
    reg.register(
        FeatureMetadata(
            name="in_place_noi",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            description="Current trailing twelve month in-place net operating income",
            is_nullable=False,
            tags=["financial", "noi"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="stabilized_noi",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            description="Year 1 pro-forma stabilized net operating income",
            is_nullable=False,
            tags=["financial", "noi"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="in_place_cap_rate",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            description="In-place cap rate based on purchase price",
            is_nullable=False,
            min_value=0.0,
            max_value=0.30,
            tags=["financial", "yield"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="exit_cap_rate",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            description="Assumed terminal capitalization rate upon asset disposition",
            is_nullable=False,
            min_value=0.01,
            max_value=0.25,
            tags=["financial", "exit"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="expense_ratio",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            description="Operating expense percentage of effective gross income",
            is_nullable=False,
            min_value=0.0,
            max_value=1.0,
            tags=["financial", "efficiency"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="levered_irr",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            description="Projected levered internal rate of return over hold period",
            is_nullable=True,
            min_value=-1.0,
            max_value=5.0,
            tags=["financial", "returns"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="equity_multiple",
            category=FeatureCategory.FINANCIAL,
            data_type=FeatureDataType.FLOAT,
            description="Projected equity multiple on invested capital",
            is_nullable=True,
            min_value=0.0,
            max_value=20.0,
            tags=["financial", "returns"],
        )
    )

    # --- Debt Features ---
    reg.register(
        FeatureMetadata(
            name="loan_amount",
            category=FeatureCategory.DEBT,
            data_type=FeatureDataType.FLOAT,
            description="Principal senior debt funding",
            is_nullable=False,
            min_value=0.0,
            tags=["debt", "principal"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="equity_required",
            category=FeatureCategory.DEBT,
            data_type=FeatureDataType.FLOAT,
            description="Sponsor and LP equity contribution required at closing",
            is_nullable=False,
            min_value=0.0,
            tags=["debt", "equity"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="ltv_ratio",
            category=FeatureCategory.DEBT,
            data_type=FeatureDataType.FLOAT,
            description="Loan-to-value percentage",
            is_nullable=False,
            min_value=0.0,
            max_value=1.0,
            tags=["debt", "leverage"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="dscr_year1",
            category=FeatureCategory.DEBT,
            data_type=FeatureDataType.FLOAT,
            description="Year 1 debt service coverage ratio",
            is_nullable=False,
            min_value=0.0,
            tags=["debt", "coverage"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="debt_yield",
            category=FeatureCategory.DEBT,
            data_type=FeatureDataType.FLOAT,
            description="Net operating income divided by loan principal",
            is_nullable=False,
            min_value=0.0,
            tags=["debt", "yield"],
        )
    )

    # --- Market Features ---
    reg.register(
        FeatureMetadata(
            name="submarket_vacancy_rate",
            category=FeatureCategory.MARKET,
            data_type=FeatureDataType.FLOAT,
            description="Prevailing submarket vacancy rate benchmark",
            is_nullable=True,
            min_value=0.0,
            max_value=0.50,
            tags=["market", "vacancy"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="market_rent_growth_rate",
            category=FeatureCategory.MARKET,
            data_type=FeatureDataType.FLOAT,
            description="Projected annual submarket rent growth rate",
            is_nullable=True,
            min_value=-0.20,
            max_value=0.30,
            tags=["market", "growth"],
        )
    )

    # --- Risk Features ---
    reg.register(
        FeatureMetadata(
            name="break_even_occupancy",
            category=FeatureCategory.RISK,
            data_type=FeatureDataType.FLOAT,
            description="Physical occupancy required to cover opex and debt service",
            is_nullable=True,
            min_value=0.0,
            max_value=1.50,
            tags=["risk", "occupancy"],
        )
    )
    reg.register(
        FeatureMetadata(
            name="default_probability",
            category=FeatureCategory.RISK,
            data_type=FeatureDataType.FLOAT,
            description="Simulated probability of insolvency or DSCR breach",
            is_nullable=True,
            min_value=0.0,
            max_value=1.0,
            tags=["risk", "monte_carlo"],
        )
    )

    # --- Derived Features ---
    # 1. Purchase price per unit
    reg.register_derived(
        FeatureMetadata(
            name="purchase_price_per_unit",
            category=FeatureCategory.DERIVED,
            data_type=FeatureDataType.FLOAT,
            description="Acquisition price divided by total unit count",
            is_nullable=True,
            min_value=0.0,
            tags=["derived", "basis"],
        ),
        compute_fn=lambda f: (
            f["purchase_price"] / f["unit_count"]
            if f.get("unit_count", 0) > 0 and f.get("purchase_price") is not None
            else None
        ),
        dependencies=["purchase_price", "unit_count"],
    )

    # 2. Total acquisition basis
    reg.register_derived(
        FeatureMetadata(
            name="total_acquisition_basis",
            category=FeatureCategory.DERIVED,
            data_type=FeatureDataType.FLOAT,
            description="Purchase price + upfront rehab capital",
            is_nullable=True,
            min_value=0.0,
            tags=["derived", "basis"],
        ),
        compute_fn=lambda f: (
            float(f.get("purchase_price", 0.0) + f.get("rehab_budget", 0.0))
            if f.get("purchase_price") is not None
            else None
        ),
        dependencies=["purchase_price", "rehab_budget"],
    )

    # 3. Yield on cost (unlevered stabilized return on total basis)
    reg.register_derived(
        FeatureMetadata(
            name="yield_on_cost",
            category=FeatureCategory.DERIVED,
            data_type=FeatureDataType.FLOAT,
            description="Stabilized Year 1 NOI divided by total acquisition basis",
            is_nullable=True,
            min_value=0.0,
            max_value=0.50,
            tags=["derived", "yield"],
        ),
        compute_fn=lambda f: (
            f["stabilized_noi"] / f["total_acquisition_basis"]
            if f.get("total_acquisition_basis", 0) > 0 and f.get("stabilized_noi") is not None
            else None
        ),
        dependencies=["stabilized_noi", "total_acquisition_basis"],
    )

    # 4. Debt service coverage cushion (dscr - 1.0)
    reg.register_derived(
        FeatureMetadata(
            name="dscr_cushion",
            category=FeatureCategory.DERIVED,
            data_type=FeatureDataType.FLOAT,
            description="Coverage buffer above parity (dscr_year1 - 1.0)",
            is_nullable=True,
            tags=["derived", "debt"],
        ),
        compute_fn=lambda f: f["dscr_year1"] - 1.0 if f.get("dscr_year1") is not None else None,
        dependencies=["dscr_year1"],
    )

    return reg
