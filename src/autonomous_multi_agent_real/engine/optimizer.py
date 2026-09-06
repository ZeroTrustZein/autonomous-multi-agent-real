"""Pricing and deal terms optimization solver for target return hurdles."""

from __future__ import annotations

from typing import Tuple

from autonomous_multi_agent_real.engine.financial import (
    calculate_cap_rate,
    calculate_debt_yield,
    calculate_dscr,
    calculate_exit_sale_proceeds,
    calculate_irr,
    calculate_loan_amortization_schedule,
    calculate_monthly_mortgage_payment,
)
from autonomous_multi_agent_real.types import (
    DebtSizingResult,
    PricingOptimizationResult,
    PropertyDeal,
)


class DealOptimizer:
    """Solves for maximum purchase prices, hurdle returns, and minimum required rents."""

    @staticmethod
    def _size_debt_for_price(
        deal: PropertyDeal,
        test_price: float,
        target_min_dscr: float,
        target_min_debt_yield: float,
    ) -> DebtSizingResult:
        """Size debt dynamically for a test purchase price."""
        fin = deal.financing
        units = deal.total_units

        # Year 1 NOI
        gpr_y1 = deal.total_market_annual_rent * (1.0 + deal.annual_rent_growth_pct)
        egi_y1 = gpr_y1 * deal.market_occupancy_pct
        fixed_exp = deal.expenses.fixed_annual_expenses(units) * (
            1.0 + deal.annual_expense_growth_pct
        )
        var_exp = egi_y1 * deal.expenses.property_management_pct
        noi_y1 = max(1000.0, egi_y1 - fixed_exp - var_exp)

        # 1. LTV
        max_ltv = 1.0 - fin.down_payment_pct
        loan_by_ltv = test_price * max_ltv

        # 2. DSCR
        unit_pmt = calculate_monthly_mortgage_payment(
            1.0, fin.interest_rate, fin.amortization_years
        )
        unit_ads = unit_pmt * 12.0
        loan_by_dscr = (noi_y1 / (target_min_dscr * unit_ads)) if unit_ads > 0 else loan_by_ltv

        # 3. Debt Yield
        loan_by_dy = (noi_y1 / target_min_debt_yield) if target_min_debt_yield > 0 else loan_by_ltv

        binding_constraint, sized_loan = min(
            [("LTV", loan_by_ltv), ("DSCR", loan_by_dscr), ("Debt Yield", loan_by_dy)],
            key=lambda x: x[1],
        )
        sized_loan = round(max(0.0, sized_loan), 2)

        monthly_pmt = calculate_monthly_mortgage_payment(
            sized_loan, fin.interest_rate, fin.amortization_years
        )
        annual_debt_svc = monthly_pmt * 12.0
        ltv_actual = sized_loan / test_price if test_price > 0 else 0.0
        dscr_actual = calculate_dscr(noi_y1, annual_debt_svc)
        dy_actual = calculate_debt_yield(noi_y1, sized_loan)

        closing_costs = test_price * fin.closing_costs_pct
        total_basis = test_price + deal.rehab_budget + closing_costs
        equity_req = round(max(0.0, total_basis - sized_loan), 2)

        return DebtSizingResult(
            loan_amount=sized_loan,
            equity_required=equity_req,
            monthly_payment=monthly_pmt,
            annual_debt_service=annual_debt_svc,
            ltv_ratio=round(ltv_actual, 4),
            dscr_year1=round(dscr_actual, 3),
            debt_yield_pct=round(dy_actual, 4),
            binding_constraint=binding_constraint,
        )

    @classmethod
    def _evaluate_irr_at_price(
        cls,
        deal: PropertyDeal,
        test_price: float,
        target_min_dscr: float,
        target_min_debt_yield: float,
    ) -> Tuple[float, DebtSizingResult]:
        """Compute levered IRR at a given test purchase price."""
        debt = cls._size_debt_for_price(
            deal=deal,
            test_price=test_price,
            target_min_dscr=target_min_dscr,
            target_min_debt_yield=target_min_debt_yield,
        )
        units = deal.total_units
        hold_years = deal.hold_period_years
        fin = deal.financing

        amort_sched = calculate_loan_amortization_schedule(
            principal=debt.loan_amount,
            annual_interest_rate=fin.interest_rate,
            amortization_years=fin.amortization_years,
            hold_period_years=hold_years,
            interest_only_months=fin.interest_only_months,
        )

        base_rent = deal.total_market_annual_rent
        base_fixed_exp = deal.expenses.fixed_annual_expenses(units)
        mgmt_pct = deal.expenses.property_management_pct

        cash_flows = [-debt.equity_required]

        for yr in range(1, hold_years + 1):
            rent_growth = (1.0 + deal.annual_rent_growth_pct) ** yr
            exp_growth = (1.0 + deal.annual_expense_growth_pct) ** yr

            gpr = base_rent * rent_growth
            vac_loss = gpr * (1.0 - deal.market_occupancy_pct)
            egi = gpr - vac_loss

            fixed_exp = base_fixed_exp * exp_growth
            var_exp = egi * mgmt_pct
            opex = fixed_exp + var_exp
            noi = max(0.0, egi - opex)

            capex = (deal.expenses.replacement_reserves_per_unit * units) * exp_growth
            btcf = noi - capex - debt.annual_debt_service
            ending_bal = amort_sched[yr - 1][2] if yr <= len(amort_sched) else 0.0

            if yr == hold_years:
                next_noi = noi * (1.0 + deal.annual_rent_growth_pct)
                gross_proceeds = calculate_exit_sale_proceeds(
                    exit_year_noi=next_noi,
                    exit_cap_rate=deal.exit_cap_rate,
                    selling_costs_pct=deal.selling_costs_pct,
                )
                net_terminal = max(0.0, gross_proceeds - ending_bal)
                net_cf = btcf + net_terminal
            else:
                net_cf = btcf

            cash_flows.append(net_cf)

        return calculate_irr(cash_flows), debt

    def solve_max_offer_price(
        self,
        deal: PropertyDeal,
        target_levered_irr: float = 0.15,
        target_min_dscr: float = 1.25,
        target_min_debt_yield: float = 0.08,
        tolerance_dollars: float = 1000.0,
        max_iterations: int = 50,
    ) -> PricingOptimizationResult:
        """Find the maximum purchase price that achieves target levered IRR."""
        current_price = deal.purchase_price

        # Bisection search between low price and high price
        low = 100000.0
        high = current_price * 2.5

        best_price = low
        best_debt = self._size_debt_for_price(
            deal, best_price, target_min_dscr, target_min_debt_yield
        )

        for _ in range(max_iterations):
            mid = (low + high) / 2.0
            mid_irr, debt_res = self._evaluate_irr_at_price(
                deal=deal,
                test_price=mid,
                target_min_dscr=target_min_dscr,
                target_min_debt_yield=target_min_debt_yield,
            )

            if abs(high - low) < tolerance_dollars:
                best_price = mid
                best_debt = debt_res
                break

            # IRR decreases as price increases
            if mid_irr >= target_levered_irr:
                # Can afford to pay higher
                best_price = mid
                best_debt = debt_res
                low = mid
            else:
                # Must pay lower
                high = mid

        best_price = round(best_price, 2)
        y1_noi = (deal.total_market_annual_rent * deal.market_occupancy_pct) - (
            deal.expenses.fixed_annual_expenses(deal.total_units)
        )
        implied_cap = calculate_cap_rate(y1_noi, best_price)
        pricing_variance = round(current_price - best_price, 2)
        pricing_variance_pct = (
            round(pricing_variance / current_price, 4) if current_price > 0 else 0.0
        )

        return PricingOptimizationResult(
            target_hurdle_irr=round(target_levered_irr, 4),
            target_min_dscr=round(target_min_dscr, 3),
            target_min_debt_yield=round(target_min_debt_yield, 4),
            max_supportable_purchase_price=best_price,
            implied_entry_cap_rate=round(implied_cap, 4),
            implied_loan_amount=best_debt.loan_amount,
            implied_equity_required=best_debt.equity_required,
            current_purchase_price=round(current_price, 2),
            pricing_variance=pricing_variance,
            pricing_variance_pct=pricing_variance_pct,
            is_overpriced=pricing_variance > 0.0,
        )

    def solve_required_market_rent(
        self,
        deal: PropertyDeal,
        target_levered_irr: float = 0.15,
        target_min_dscr: float = 1.25,
        target_min_debt_yield: float = 0.08,
    ) -> float:
        """Find the average monthly market rent per unit needed to meet target IRR at current price."""
        units = deal.total_units
        if units <= 0:
            return 0.0

        low_multiplier = 0.5
        high_multiplier = 3.0
        best_multiplier = 1.0

        for _ in range(40):
            mid_mult = (low_multiplier + high_multiplier) / 2.0
            # Clone deal with scaled rents
            scaled_mix = [
                item.model_copy(update={"market_rent": item.market_rent * mid_mult})
                for item in deal.unit_mix
            ]
            test_deal = deal.model_copy(update={"unit_mix": scaled_mix})
            irr, _ = self._evaluate_irr_at_price(
                deal=test_deal,
                test_price=deal.purchase_price,
                target_min_dscr=target_min_dscr,
                target_min_debt_yield=target_min_debt_yield,
            )

            if abs(high_multiplier - low_multiplier) < 0.001:
                best_multiplier = mid_mult
                break

            if irr >= target_levered_irr:
                best_multiplier = mid_mult
                high_multiplier = mid_mult
            else:
                low_multiplier = mid_mult

        avg_current_market_rent = deal.total_market_monthly_rent / units
        return round(avg_current_market_rent * best_multiplier, 2)
