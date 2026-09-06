"""Persistence repository for properties, underwriting deals, and results."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from autonomous_multi_agent_real.types import (
    FinancingTerms,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnderwritingResult,
    UnitMixItem,
)


def get_benchmark_deals() -> List[PropertyDeal]:
    """Provide realistic default underwriting deals across property types."""
    return [
        PropertyDeal(
            id="austin-multifamily",
            title="Travis Heights 24-Unit Value-Add",
            address="1402 S Congress Ave, Austin, TX 78704",
            property_type=PropertyType.MULTI_FAMILY,
            gross_square_feet=21600.0,
            unit_mix=[
                UnitMixItem(
                    unit_type="1BR/1BA",
                    count=16,
                    square_feet=750.0,
                    current_rent=1450.0,
                    market_rent=1675.0,
                ),
                UnitMixItem(
                    unit_type="2BR/2BA",
                    count=8,
                    square_feet=1100.0,
                    current_rent=1950.0,
                    market_rent=2250.0,
                ),
            ],
            purchase_price=4800000.0,
            rehab_budget=350000.0,
            current_occupancy_pct=0.92,
            market_occupancy_pct=0.95,
            annual_rent_growth_pct=0.035,
            annual_expense_growth_pct=0.025,
            hold_period_years=5,
            exit_cap_rate=0.0625,
            selling_costs_pct=0.02,
            expenses=OperatingExpenses(
                property_taxes=62000.0,
                insurance=18500.0,
                repairs_and_maintenance=24000.0,
                property_management_pct=0.07,
                utilities=12000.0,
                admin_and_legal=8500.0,
                replacement_reserves_per_unit=300.0,
                other_expenses=3500.0,
            ),
            financing=FinancingTerms(
                purchase_price=4800000.0,
                down_payment_pct=0.25,
                interest_rate=0.0625,
                amortization_years=30,
                loan_term_years=10,
                interest_only_months=12,
                closing_costs_pct=0.02,
            ),
        ),
        PropertyDeal(
            id="dallas-industrial",
            title="DFW Logistics Light Industrial Park",
            address="8800 Gateway Blvd, Irving, TX 75063",
            property_type=PropertyType.INDUSTRIAL,
            gross_square_feet=45000.0,
            unit_mix=[
                UnitMixItem(
                    unit_type="Bay-Warehouse-A",
                    count=2,
                    square_feet=15000.0,
                    current_rent=11250.0,
                    market_rent=13500.0,
                ),
                UnitMixItem(
                    unit_type="Bay-Warehouse-B",
                    count=3,
                    square_feet=5000.0,
                    current_rent=4200.0,
                    market_rent=5000.0,
                ),
            ],
            purchase_price=5600000.0,
            rehab_budget=150000.0,
            current_occupancy_pct=0.96,
            market_occupancy_pct=0.96,
            annual_rent_growth_pct=0.04,
            annual_expense_growth_pct=0.025,
            hold_period_years=5,
            exit_cap_rate=0.0675,
            selling_costs_pct=0.02,
            expenses=OperatingExpenses(
                property_taxes=78000.0,
                insurance=22000.0,
                repairs_and_maintenance=18000.0,
                property_management_pct=0.05,
                utilities=6000.0,
                admin_and_legal=7000.0,
                replacement_reserves_per_unit=500.0,
                other_expenses=2000.0,
            ),
            financing=FinancingTerms(
                purchase_price=5600000.0,
                down_payment_pct=0.30,
                interest_rate=0.065,
                amortization_years=25,
                loan_term_years=7,
                interest_only_months=0,
                closing_costs_pct=0.018,
            ),
        ),
        PropertyDeal(
            id="phoenix-mixed-use",
            title="Biltmore Mixed-Use Village",
            address="2400 E Camelback Rd, Phoenix, AZ 85016",
            property_type=PropertyType.MIXED_USE,
            gross_square_feet=18000.0,
            unit_mix=[
                UnitMixItem(
                    unit_type="Urban-Loft-Residential",
                    count=10,
                    square_feet=950.0,
                    current_rent=1750.0,
                    market_rent=2000.0,
                ),
                UnitMixItem(
                    unit_type="Ground-Retail-Suite",
                    count=4,
                    square_feet=1800.0,
                    current_rent=3600.0,
                    market_rent=4200.0,
                ),
            ],
            purchase_price=4200000.0,
            rehab_budget=200000.0,
            current_occupancy_pct=0.90,
            market_occupancy_pct=0.94,
            annual_rent_growth_pct=0.03,
            annual_expense_growth_pct=0.025,
            hold_period_years=5,
            exit_cap_rate=0.065,
            selling_costs_pct=0.02,
            expenses=OperatingExpenses(
                property_taxes=54000.0,
                insurance=16000.0,
                repairs_and_maintenance=20000.0,
                property_management_pct=0.065,
                utilities=14000.0,
                admin_and_legal=6000.0,
                replacement_reserves_per_unit=350.0,
                other_expenses=3000.0,
            ),
            financing=FinancingTerms(
                purchase_price=4200000.0,
                down_payment_pct=0.25,
                interest_rate=0.064,
                amortization_years=30,
                loan_term_years=10,
                interest_only_months=6,
                closing_costs_pct=0.02,
            ),
        ),
    ]


class DealRepository:
    """Storage manager for property deal templates and underwriting results."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path("./deals_data")
        self._deals: Dict[str, PropertyDeal] = {}
        self._results: Dict[str, UnderwritingResult] = {}

        # Seed in-memory cache with benchmark deals
        for deal in get_benchmark_deals():
            self._deals[deal.id] = deal

    def list_deals(self) -> List[PropertyDeal]:
        """Return all available property deals."""
        return list(self._deals.values())

    def get_deal(self, deal_id: str) -> Optional[PropertyDeal]:
        """Retrieve deal by ID."""
        return self._deals.get(deal_id)

    def save_deal(self, deal: PropertyDeal) -> None:
        """Store deal in memory and persist to disk if directory configured."""
        self._deals[deal.id] = deal
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            path = self.storage_dir / f"deal_{deal.id}.json"
            path.write_text(deal.model_dump_json(indent=2), encoding="utf-8")
        except OSError:
            pass

    def save_result(self, result: UnderwritingResult) -> None:
        """Store underwriting result."""
        self._results[result.deal_id] = result
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            path = self.storage_dir / f"result_{result.deal_id}.json"
            path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        except OSError:
            pass

    def get_result(self, deal_id: str) -> Optional[UnderwritingResult]:
        """Retrieve underwriting result by deal ID."""
        return self._results.get(deal_id)
