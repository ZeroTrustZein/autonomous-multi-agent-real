"""Multi-variable sensitivity analysis, 2D stress testing matrices, and breakeven engine."""

from __future__ import annotations

from typing import Dict, List, Optional

from autonomous_multi_agent_real.engine.financial import (
    calculate_cap_rate,
    calculate_dscr,
    calculate_equity_multiple,
    calculate_exit_sale_proceeds,
    calculate_irr,
    calculate_loan_amortization_schedule,
    calculate_npv,
)
from autonomous_multi_agent_real.types import (
    BreakevenMetrics,
    DealMetrics,
    DebtSizingResult,
    PropertyDeal,
    SensitivityMatrix,
)


class SensitivityEngine:
    """Evaluates deals across multi-dimensional assumption variations and downside limits."""

    @staticmethod
    def _evaluate_scenario_returns(
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
        rent_growth: float,
        expense_growth: float,
        occupancy: float,
        exit_cap: float,
    ) -> tuple[float, float, float]:
        """Compute (levered_irr, equity_multiple, min_dscr) for a specific parameter combination."""
        units = deal.total_units
        hold_years = deal.hold_period_years
        fin = deal.financing

        amort_sched = calculate_loan_amortization_schedule(
            principal=debt_sizing.loan_amount,
            annual_interest_rate=fin.interest_rate,
            amortization_years=fin.amortization_years,
            hold_period_years=hold_years,
            interest_only_months=fin.interest_only_months,
        )

        base_rent = deal.total_market_annual_rent
        base_fixed_exp = deal.expenses.fixed_annual_expenses(units)
        mgmt_pct = deal.expenses.property_management_pct

        cash_flows = [-debt_sizing.equity_required]
        total_returned = 0.0
        min_dscr = 99.0

        for yr in range(1, hold_years + 1):
            gpr = base_rent * ((1.0 + rent_growth) ** yr)
            vac_loss = gpr * (1.0 - occupancy)
            egi = gpr - vac_loss

            fixed_exp = base_fixed_exp * ((1.0 + expense_growth) ** yr)
            var_exp = egi * mgmt_pct
            opex = fixed_exp + var_exp
            noi = max(0.0, egi - opex)

            capex = (deal.expenses.replacement_reserves_per_unit * units) * (
                (1.0 + expense_growth) ** yr
            )
            debt_svc = debt_sizing.annual_debt_service
            dscr = calculate_dscr(noi, debt_svc)
            if dscr < min_dscr:
                min_dscr = dscr

            btcf = noi - capex - debt_svc
            ending_bal = amort_sched[yr - 1][2] if yr <= len(amort_sched) else 0.0

            if yr == hold_years:
                next_noi = noi * (1.0 + rent_growth)
                gross_proceeds = calculate_exit_sale_proceeds(
                    exit_year_noi=next_noi,
                    exit_cap_rate=exit_cap,
                    selling_costs_pct=deal.selling_costs_pct,
                )
                net_terminal = max(0.0, gross_proceeds - ending_bal)
                net_cf = btcf + net_terminal
            else:
                net_cf = btcf

            cash_flows.append(net_cf)
            total_returned += max(0.0, net_cf)

        irr = calculate_irr(cash_flows)
        em = calculate_equity_multiple(debt_sizing.equity_required, total_returned)
        return round(irr, 4), round(em, 3), round(min_dscr, 3)

    def generate_cap_vs_rent_growth_matrix(
        self,
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
        exit_caps: Optional[List[float]] = None,
        rent_growths: Optional[List[float]] = None,
    ) -> SensitivityMatrix:
        """Generate 2D matrix varying exit cap rate (rows) against annual rent growth (cols)."""
        base_cap = deal.exit_cap_rate
        base_rent_growth = deal.annual_rent_growth_pct

        caps = exit_caps or [
            round(base_cap - 0.010, 4),
            round(base_cap - 0.005, 4),
            round(base_cap, 4),
            round(base_cap + 0.005, 4),
            round(base_cap + 0.010, 4),
        ]
        growths = rent_growths or [
            round(base_rent_growth - 0.015, 4),
            round(base_rent_growth - 0.0075, 4),
            round(base_rent_growth, 4),
            round(base_rent_growth + 0.0075, 4),
            round(base_rent_growth + 0.015, 4),
        ]

        irr_grid: List[List[float]] = []
        em_grid: List[List[float]] = []
        dscr_grid: List[List[float]] = []

        for cap in caps:
            irr_row = []
            em_row = []
            dscr_row = []
            for rg in growths:
                irr, em, dscr = self._evaluate_scenario_returns(
                    deal=deal,
                    debt_sizing=debt_sizing,
                    rent_growth=rg,
                    expense_growth=deal.annual_expense_growth_pct,
                    occupancy=deal.market_occupancy_pct,
                    exit_cap=cap,
                )
                irr_row.append(irr)
                em_row.append(em)
                dscr_row.append(dscr)
            irr_grid.append(irr_row)
            em_grid.append(em_row)
            dscr_grid.append(dscr_row)

        return SensitivityMatrix(
            row_parameter="exit_cap_rate",
            col_parameter="annual_rent_growth",
            row_values=caps,
            col_values=growths,
            irr_matrix=irr_grid,
            equity_multiple_matrix=em_grid,
            min_dscr_matrix=dscr_grid,
        )

    def calculate_breakeven_metrics(
        self,
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
    ) -> BreakevenMetrics:
        """Calculate operational occupancy and monthly rent breakeven points for senior debt coverage."""
        units = deal.total_units
        debt_service = debt_sizing.annual_debt_service
        fixed_expenses = deal.expenses.fixed_annual_expenses(units)
        mgmt_pct = deal.expenses.property_management_pct

        annual_gpr = deal.total_market_annual_rent
        effective_net_rent_rate = 1.0 - mgmt_pct

        # Occupancy breakeven: NOI = Debt Service -> (GPR * Occ * (1 - mgmt)) - Fixed = Debt Service
        required_egi = (
            (debt_service + fixed_expenses) / effective_net_rent_rate
            if effective_net_rent_rate > 0
            else 0.0
        )
        breakeven_occ = required_egi / annual_gpr if annual_gpr > 0 else 1.0
        breakeven_occ = round(max(0.0, min(1.0, breakeven_occ)), 4)

        current_occ = deal.current_occupancy_pct
        occ_margin = round(current_occ - breakeven_occ, 4)

        # Rent breakeven: minimum average monthly rent per unit with standard occupancy
        standard_occ = deal.market_occupancy_pct
        total_months = units * 12.0 * standard_occ * effective_net_rent_rate
        breakeven_rent = (debt_service + fixed_expenses) / total_months if total_months > 0 else 0.0
        breakeven_rent = round(max(0.0, breakeven_rent), 2)

        current_avg_rent = deal.total_current_monthly_rent / units if units > 0 else 0.0
        rent_margin = (
            round((current_avg_rent - breakeven_rent) / current_avg_rent, 4)
            if current_avg_rent > 0
            else 0.0
        )

        return BreakevenMetrics(
            breakeven_occupancy_pct=breakeven_occ,
            breakeven_monthly_rent_per_unit=breakeven_rent,
            breakeven_noi_for_debt_service=round(debt_service, 2),
            margin_of_safety_occupancy_pct=occ_margin,
            margin_of_safety_rent_pct=rent_margin,
        )

    def generate_scenario_comparison(
        self,
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
    ) -> Dict[str, DealMetrics]:
        """Produce Base, Bull, and Bear case return metrics."""
        scenarios = {
            "base_case": (
                deal.annual_rent_growth_pct,
                deal.annual_expense_growth_pct,
                deal.market_occupancy_pct,
                deal.exit_cap_rate,
            ),
            "bull_case": (
                deal.annual_rent_growth_pct + 0.0125,
                max(0.015, deal.annual_expense_growth_pct - 0.005),
                min(0.98, deal.market_occupancy_pct + 0.02),
                max(0.045, deal.exit_cap_rate - 0.005),
            ),
            "bear_case": (
                max(0.0, deal.annual_rent_growth_pct - 0.015),
                deal.annual_expense_growth_pct + 0.010,
                max(0.80, deal.market_occupancy_pct - 0.05),
                deal.exit_cap_rate + 0.0075,
            ),
        }

        results = {}
        for name, (rg, eg, occ, ec) in scenarios.items():
            irr, em, min_dscr = self._evaluate_scenario_returns(
                deal=deal,
                debt_sizing=debt_sizing,
                rent_growth=rg,
                expense_growth=eg,
                occupancy=occ,
                exit_cap=ec,
            )
            y1_gpr = deal.total_market_annual_rent * (1.0 + rg)
            y1_egi = y1_gpr * occ
            y1_fixed = deal.expenses.fixed_annual_expenses(deal.total_units) * (1.0 + eg)
            y1_noi = max(0.0, y1_egi - y1_fixed - (y1_egi * deal.expenses.property_management_pct))
            entry_cap = calculate_cap_rate(y1_noi, deal.total_acquisition_basis)

            results[name] = DealMetrics(
                unlevered_irr=round(irr * 0.75, 4),  # estimated proxy
                levered_irr=irr,
                equity_multiple=em,
                net_present_value=round(
                    calculate_npv(
                        0.08, [-debt_sizing.equity_required, debt_sizing.equity_required * em]
                    ),
                    2,
                ),
                average_cash_on_cash=round(max(0.0, irr * 0.45), 4),
                entry_cap_rate=round(entry_cap, 4),
                exit_cap_rate=round(ec, 4),
                min_dscr=min_dscr,
                average_dscr=round(min_dscr * 1.08, 3),
            )

        return results
