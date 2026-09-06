"""Tax depreciation, MACRS schedules, cost segregation, and after-tax return engine."""

from __future__ import annotations

from typing import List

from autonomous_multi_agent_real.engine.financial import (
    calculate_equity_multiple,
    calculate_irr,
    calculate_loan_amortization_schedule,
)
from autonomous_multi_agent_real.types import (
    DebtSizingResult,
    PropertyDeal,
    PropertyType,
    TaxAnalysisResult,
    TaxScheduleItem,
)


class TaxEngine:
    """Computes straight-line MACRS depreciation, cost segregation, and after-tax returns."""

    def __init__(
        self,
        land_value_pct: float = 0.20,
        ordinary_income_tax_rate: float = 0.37,
        capital_gains_tax_rate: float = 0.20,
        depreciation_recapture_rate: float = 0.25,
        enable_cost_segregation: bool = False,
        cost_seg_5yr_pct: float = 0.12,
        cost_seg_15yr_pct: float = 0.08,
        year1_bonus_depreciation_pct: float = 0.60,
    ):
        self.land_value_pct = land_value_pct
        self.ordinary_income_tax_rate = ordinary_income_tax_rate
        self.capital_gains_tax_rate = capital_gains_tax_rate
        self.depreciation_recapture_rate = depreciation_recapture_rate
        self.enable_cost_segregation = enable_cost_segregation
        self.cost_seg_5yr_pct = cost_seg_5yr_pct
        self.cost_seg_15yr_pct = cost_seg_15yr_pct
        self.year1_bonus_depreciation_pct = year1_bonus_depreciation_pct

    def compute_depreciation_schedule(
        self,
        deal: PropertyDeal,
        hold_years: int,
    ) -> List[float]:
        """Compute yearly depreciation deduction allowances."""
        total_basis = deal.total_acquisition_basis
        depreciable_basis = total_basis * (1.0 - self.land_value_pct)

        # Recovery period: 27.5 years for multifamily residential, 39.0 years for commercial
        is_residential = deal.property_type in (
            PropertyType.MULTI_FAMILY,
            PropertyType.SINGLE_FAMILY,
        )
        macrs_years = 27.5 if is_residential else 39.0

        if not self.enable_cost_segregation:
            annual_straight_line = depreciable_basis / macrs_years
            return [round(annual_straight_line, 2) for _ in range(hold_years)]

        # Cost segregation breakdown
        basis_5yr = depreciable_basis * self.cost_seg_5yr_pct
        basis_15yr = depreciable_basis * self.cost_seg_15yr_pct
        basis_building = depreciable_basis - basis_5yr - basis_15yr

        building_annual = basis_building / macrs_years
        year1_bonus = (basis_5yr + basis_15yr) * self.year1_bonus_depreciation_pct
        remaining_5yr = basis_5yr * (1.0 - self.year1_bonus_depreciation_pct)
        remaining_15yr = basis_15yr * (1.0 - self.year1_bonus_depreciation_pct)

        schedule: List[float] = []
        for yr in range(1, hold_years + 1):
            yr_dep = building_annual
            if yr == 1:
                yr_dep += year1_bonus + (remaining_5yr / 5.0) + (remaining_15yr / 15.0)
            else:
                if yr <= 5:
                    yr_dep += remaining_5yr / 5.0
                if yr <= 15:
                    yr_dep += remaining_15yr / 15.0
            schedule.append(round(yr_dep, 2))

        return schedule

    def analyze(
        self,
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
        annual_nois: List[float],
        exit_gross_proceeds: float,
    ) -> TaxAnalysisResult:
        """Calculate complete pre-tax vs after-tax schedule and exit tax liabilities."""
        hold_years = deal.hold_period_years
        fin = deal.financing

        amort_sched = calculate_loan_amortization_schedule(
            principal=debt_sizing.loan_amount,
            annual_interest_rate=fin.interest_rate,
            amortization_years=fin.amortization_years,
            hold_period_years=hold_years,
            interest_only_months=fin.interest_only_months,
        )

        dep_schedule = self.compute_depreciation_schedule(deal, hold_years)

        schedule_items: List[TaxScheduleItem] = []
        pre_tax_flows = [-debt_sizing.equity_required]
        after_tax_flows = [-debt_sizing.equity_required]

        accumulated_depreciation = 0.0

        for yr_idx in range(hold_years):
            yr = yr_idx + 1
            noi = annual_nois[yr_idx] if yr_idx < len(annual_nois) else 0.0
            interest_paid = amort_sched[yr_idx][1] if yr_idx < len(amort_sched) else 0.0
            depreciation = dep_schedule[yr_idx] if yr_idx < len(dep_schedule) else 0.0
            accumulated_depreciation += depreciation

            taxable_income = noi - interest_paid - depreciation
            tax_liability = taxable_income * self.ordinary_income_tax_rate

            capex = (deal.expenses.replacement_reserves_per_unit * deal.total_units) * (
                (1.0 + deal.annual_expense_growth_pct) ** yr
            )
            pre_tax_cf = noi - capex - debt_sizing.annual_debt_service
            after_tax_cf = pre_tax_cf - tax_liability

            schedule_items.append(
                TaxScheduleItem(
                    year=yr,
                    noi=round(noi, 2),
                    interest_deduction=round(interest_paid, 2),
                    depreciation_deduction=round(depreciation, 2),
                    taxable_income=round(taxable_income, 2),
                    tax_liability=round(tax_liability, 2),
                    pre_tax_cash_flow=round(pre_tax_cf, 2),
                    after_tax_cash_flow=round(after_tax_cf, 2),
                )
            )

            if yr < hold_years:
                pre_tax_flows.append(round(pre_tax_cf, 2))
                after_tax_flows.append(round(after_tax_cf, 2))

        # Terminal Disposition Tax Calculation
        terminal_debt = amort_sched[-1][2] if amort_sched else 0.0
        net_sale_proceeds = exit_gross_proceeds  # after selling costs
        terminal_pre_tax_equity = max(0.0, net_sale_proceeds - terminal_debt)

        total_acquisition_basis = deal.total_acquisition_basis
        adjusted_basis = max(0.0, total_acquisition_basis - accumulated_depreciation)
        total_gain = max(0.0, net_sale_proceeds - adjusted_basis)

        # Section 1250 Depreciation Recapture (taxed up to 25%)
        recapture_gain = min(accumulated_depreciation, total_gain)
        recapture_tax = recapture_gain * self.depreciation_recapture_rate

        # Remaining Capital Gain (taxed at 20%)
        capital_gain = max(0.0, total_gain - recapture_gain)
        cap_gains_tax = capital_gain * self.capital_gains_tax_rate

        total_exit_taxes = round(recapture_tax + cap_gains_tax, 2)
        final_pre_tax_flow = schedule_items[-1].pre_tax_cash_flow + terminal_pre_tax_equity
        final_after_tax_flow = (
            schedule_items[-1].after_tax_cash_flow + terminal_pre_tax_equity - total_exit_taxes
        )

        pre_tax_flows.append(round(final_pre_tax_flow, 2))
        after_tax_flows.append(round(final_after_tax_flow, 2))

        pre_irr = calculate_irr(pre_tax_flows)
        post_irr = calculate_irr(after_tax_flows)
        pre_em = calculate_equity_multiple(
            debt_sizing.equity_required, sum(max(0.0, f) for f in pre_tax_flows[1:])
        )
        post_em = calculate_equity_multiple(
            debt_sizing.equity_required, sum(max(0.0, f) for f in after_tax_flows[1:])
        )

        return TaxAnalysisResult(
            annual_schedule=schedule_items,
            total_depreciation_claimed=round(accumulated_depreciation, 2),
            accumulated_depreciation_at_sale=round(accumulated_depreciation, 2),
            depreciation_recapture_tax=round(recapture_tax, 2),
            capital_gains_tax=round(cap_gains_tax, 2),
            total_exit_taxes=total_exit_taxes,
            pre_tax_irr=round(pre_irr, 4),
            after_tax_irr=round(post_irr, 4),
            pre_tax_equity_multiple=round(pre_em, 3),
            after_tax_equity_multiple=round(post_em, 3),
        )
