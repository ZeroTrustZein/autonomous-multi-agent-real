"""Vectorized Monte Carlo simulation engine with correlated macro shocks and VaR/CVaR."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from autonomous_multi_agent_real.engine.financial import (
    calculate_exit_sale_proceeds,
    calculate_irr,
    calculate_loan_amortization_schedule,
)
from autonomous_multi_agent_real.types import (
    DebtSizingResult,
    MonteCarloSimulationResult,
    PropertyDeal,
)


class MonteCarloEngine:
    """High-speed stochastic cash flow simulator using NumPy with correlated risk factors."""

    def __init__(self, seed: Optional[int] = 42, enable_correlated_shocks: bool = True):
        self.rng = np.random.default_rng(seed)
        self.enable_correlated_shocks = enable_correlated_shocks

    def _generate_correlated_shocks(
        self,
        iterations: int,
        hold_years: int,
        deal: PropertyDeal,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Generate stochastic macro shocks with empirical correlation structure."""
        means = np.array(
            [
                deal.annual_rent_growth_pct,
                1.0 - deal.market_occupancy_pct,
                deal.annual_expense_growth_pct,
                deal.exit_cap_rate,
            ]
        )
        stds = np.array([0.015, 0.020, 0.010, 0.0075])

        if self.enable_correlated_shocks:
            # Empirical commercial real estate correlation matrix:
            # [rent_growth, vacancy_rate, expense_inflation, exit_cap_rate]
            corr_matrix = np.array(
                [
                    [1.00, -0.45, 0.30, -0.35],
                    [-0.45, 1.00, -0.10, 0.25],
                    [0.30, -0.10, 1.00, 0.10],
                    [-0.35, 0.25, 0.10, 1.00],
                ]
            )
            # Cholesky decomposition
            try:
                chol = np.linalg.cholesky(corr_matrix)
            except np.linalg.LinAlgError:
                chol = np.eye(4)
        else:
            chol = np.eye(4)

        # Generate standard normal variates
        z = self.rng.standard_normal(size=(iterations, hold_years, 4))
        # Project through Cholesky factor: (iterations, hold_years, 4)
        correlated_z = np.einsum("ijk,lk->ijl", z, chol)

        rent_growth = np.clip(
            means[0] + correlated_z[:, :, 0] * stds[0],
            -0.08,
            0.15,
        )
        vacancy = np.clip(
            means[1] + correlated_z[:, :, 1] * stds[1],
            0.02,
            0.35,
        )
        expense_growth = np.clip(
            means[2] + correlated_z[:, :, 2] * stds[2],
            -0.02,
            0.12,
        )

        # Exit cap shock is evaluated at Year N
        exit_cap = np.clip(
            means[3] + correlated_z[:, -1, 3] * stds[3],
            0.035,
            0.14,
        )

        return rent_growth, vacancy, expense_growth, exit_cap

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

        # Generate correlated macro shocks
        (
            rent_growth_shocks,
            vacancy_shocks,
            expense_growth_shocks,
            exit_cap_shocks,
        ) = self._generate_correlated_shocks(iterations, hold_years, deal)

        # Terminal loan balance from schedule
        amort_sched = calculate_loan_amortization_schedule(
            principal=debt_sizing.loan_amount,
            annual_interest_rate=deal.financing.interest_rate,
            amortization_years=deal.financing.amortization_years,
            hold_period_years=hold_years,
            interest_only_months=deal.financing.interest_only_months,
        )
        terminal_loan_balance = amort_sched[-1][2] if amort_sched else 0.0

        # Simulate cash flows across iterations
        irrs = np.zeros(iterations, dtype=float)
        equity_multiples = np.zeros(iterations, dtype=float)
        dscr_breaches = 0

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

        # Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR / Expected Shortfall)
        var_95 = float(np.percentile(irrs, 5))
        cvar_95_tail = irrs[irrs <= var_95]
        cvar_95 = float(np.mean(cvar_95_tail)) if len(cvar_95_tail) > 0 else var_95

        var_99 = float(np.percentile(irrs, 1))
        cvar_99_tail = irrs[irrs <= var_99]
        cvar_99 = float(np.mean(cvar_99_tail)) if len(cvar_99_tail) > 0 else var_99

        quantiles = {
            "p5": round(var_95, 4),
            "p10": round(p10_irr, 4),
            "p25": round(float(np.percentile(irrs, 25)), 4),
            "p50": round(p50_irr, 4),
            "p75": round(float(np.percentile(irrs, 75)), 4),
            "p90": round(p90_irr, 4),
            "p95": round(float(np.percentile(irrs, 95)), 4),
        }

        # Sensitivity Variance Attribution (Correlation with IRR)
        def _calc_corr(x: np.ndarray, y: np.ndarray) -> float:
            if np.std(x) == 0 or np.std(y) == 0:
                return 0.0
            return float(np.corrcoef(x, y)[0, 1])

        mean_rent_shock = np.mean(rent_growth_shocks, axis=1)
        mean_vac_shock = np.mean(vacancy_shocks, axis=1)
        mean_exp_shock = np.mean(expense_growth_shocks, axis=1)

        variance_attrib: Dict[str, float] = {
            "rent_growth_impact": round(_calc_corr(mean_rent_shock, irrs), 3),
            "vacancy_impact": round(_calc_corr(mean_vac_shock, irrs), 3),
            "expense_growth_impact": round(_calc_corr(mean_exp_shock, irrs), 3),
            "exit_cap_rate_impact": round(_calc_corr(exit_cap_shocks, irrs), 3),
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
            var_95_irr=round(var_95, 4),
            cvar_95_irr=round(cvar_95, 4),
            var_99_irr=round(var_99, 4),
            cvar_99_irr=round(cvar_99, 4),
            variance_attribution=variance_attrib,
        )
