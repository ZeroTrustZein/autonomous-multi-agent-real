"""Vectorized Monte Carlo simulation engine for real estate cash flows and returns."""

from __future__ import annotations

from typing import Optional

import numpy as np

from autonomous_multi_agent_real.engine.financial import (
    calculate_exit_sale_proceeds,
    calculate_irr,
)
from autonomous_multi_agent_real.types import (
    DebtSizingResult,
    MonteCarloSimulationResult,
    PropertyDeal,
)


class MonteCarloEngine:
    """High-speed stochastic cash flow simulator using NumPy."""

    def __init__(self, seed: Optional[int] = 42):
        self.rng = np.random.default_rng(seed)

    def simulate(
        self,
        deal: PropertyDeal,
        debt_sizing: DebtSizingResult,
        iterations: int = 1000,
    ) -> MonteCarloSimulationResult:
        """Run multi-variable Monte Carlo simulation on the property cash flows."""
        iterations = max(50, min(iterations, 20000))
        hold_years = deal.hold_period_years
        units = deal.total_units

        # Initial baseline parameters
        base_annual_rent = deal.total_market_annual_rent
        fixed_expenses = deal.expenses.fixed_annual_expenses(units)
        mgmt_rate = deal.expenses.property_management_pct
        annual_debt_service = debt_sizing.annual_debt_service
        initial_equity = debt_sizing.equity_required

        # 1. Stochastic parameter distributions
        rent_growth_shocks = self.rng.normal(
            loc=deal.annual_rent_growth_pct,
            scale=0.015,
            size=(iterations, hold_years),
        )
        rent_growth_shocks = np.clip(rent_growth_shocks, -0.08, 0.15)

        base_vacancy = 1.0 - deal.market_occupancy_pct
        vacancy_shocks = self.rng.normal(
            loc=base_vacancy,
            scale=0.02,
            size=(iterations, hold_years),
        )
        vacancy_shocks = np.clip(vacancy_shocks, 0.02, 0.35)

        expense_growth_shocks = self.rng.normal(
            loc=deal.annual_expense_growth_pct,
            scale=0.01,
            size=(iterations, hold_years),
        )
        expense_growth_shocks = np.clip(expense_growth_shocks, -0.02, 0.12)

        exit_cap_shocks = self.rng.normal(
            loc=deal.exit_cap_rate,
            scale=0.0075,
            size=iterations,
        )
        exit_cap_shocks = np.clip(exit_cap_shocks, 0.035, 0.14)

        # 2. Simulate cash flows across iterations
        irrs = np.zeros(iterations, dtype=float)
        equity_multiples = np.zeros(iterations, dtype=float)
        dscr_breaches = 0

        # Approximate ending loan balance in Year N for terminal payoff
        # (Using baseline ending balance from amortization schedule)
        from autonomous_multi_agent_real.engine.financial import (
            calculate_loan_amortization_schedule,
        )

        amort_sched = calculate_loan_amortization_schedule(
            principal=debt_sizing.loan_amount,
            annual_interest_rate=deal.financing.interest_rate,
            amortization_years=deal.financing.amortization_years,
            hold_period_years=hold_years,
            interest_only_months=deal.financing.interest_only_months,
        )
        terminal_loan_balance = amort_sched[-1][2] if amort_sched else 0.0

        for i in range(iterations):
            cf_stream = [-initial_equity]
            curr_gpr = base_annual_rent
            curr_fixed_exp = fixed_expenses
            min_dscr_iter = 99.0
            total_cash_returned = 0.0

            last_noi = 0.0
            for yr in range(hold_years):
                curr_gpr *= 1.0 + rent_growth_shocks[i, yr]
                curr_fixed_exp *= 1.0 + expense_growth_shocks[i, yr]

                vac_loss = curr_gpr * vacancy_shocks[i, yr]
                egi = curr_gpr - vac_loss
                opex = curr_fixed_exp + (egi * mgmt_rate)
                noi = max(0.0, egi - opex)
                last_noi = noi

                # DSCR check
                dscr = (noi / annual_debt_service) if annual_debt_service > 0 else 99.0
                if dscr < min_dscr_iter:
                    min_dscr_iter = dscr

                btcf = noi - annual_debt_service
                if yr == hold_years - 1:
                    # Terminal disposition
                    next_noi = last_noi * (1.0 + deal.annual_rent_growth_pct)
                    exit_proceeds = calculate_exit_sale_proceeds(
                        exit_year_noi=next_noi,
                        exit_cap_rate=exit_cap_shocks[i],
                        selling_costs_pct=deal.selling_costs_pct,
                    )
                    net_terminal = max(0.0, exit_proceeds - terminal_loan_balance)
                    net_year_cf = btcf + net_terminal
                else:
                    net_year_cf = btcf

                cf_stream.append(net_year_cf)
                total_cash_returned += max(0.0, net_year_cf)

            if min_dscr_iter < 1.0:
                dscr_breaches += 1

            iter_irr = calculate_irr(cf_stream)
            irrs[i] = iter_irr
            equity_multiples[i] = (
                (total_cash_returned / initial_equity) if initial_equity > 0 else 0.0
            )

        # Calculate statistics
        mean_irr = float(np.mean(irrs))
        std_irr = float(np.std(irrs))
        p10_irr = float(np.percentile(irrs, 10))
        p50_irr = float(np.percentile(irrs, 50))
        p90_irr = float(np.percentile(irrs, 90))

        prob_neg_irr = float(np.sum(irrs <= 0.0) / iterations)
        prob_dscr_breach = float(dscr_breaches / iterations)

        mean_em = float(np.mean(equity_multiples))
        p10_em = float(np.percentile(equity_multiples, 10))
        p90_em = float(np.percentile(equity_multiples, 90))

        quantiles = {
            "p5": round(float(np.percentile(irrs, 5)), 4),
            "p10": round(p10_irr, 4),
            "p25": round(float(np.percentile(irrs, 25)), 4),
            "p50": round(p50_irr, 4),
            "p75": round(float(np.percentile(irrs, 75)), 4),
            "p90": round(p90_irr, 4),
            "p95": round(float(np.percentile(irrs, 95)), 4),
        }

        return MonteCarloSimulationResult(
            iterations=iterations,
            mean_levered_irr=round(mean_irr, 4),
            std_levered_irr=round(std_irr, 4),
            p10_irr=round(p10_irr, 4),
            p50_irr=round(p50_irr, 4),
            p90_irr=round(p90_irr, 4),
            probability_negative_irr=round(prob_neg_irr, 4),
            probability_dscr_breach=round(prob_dscr_breach, 4),
            mean_equity_multiple=round(mean_em, 3),
            p10_equity_multiple=round(p10_em, 3),
            p90_equity_multiple=round(p90_em, 3),
            distribution_quantiles=quantiles,
        )
