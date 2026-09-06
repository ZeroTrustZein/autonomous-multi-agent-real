"""Pure financial engineering calculations for real estate deal underwriting."""

from __future__ import annotations

import math
from typing import List, Tuple


def calculate_monthly_mortgage_payment(
    principal: float,
    annual_interest_rate: float,
    amortization_years: int,
) -> float:
    """Calculate monthly fully amortizing principal and interest mortgage payment."""
    if principal <= 0.0:
        return 0.0
    if annual_interest_rate <= 0.0:
        total_months = max(1, amortization_years * 12)
        return principal / total_months

    monthly_rate = annual_interest_rate / 12.0
    total_months = amortization_years * 12
    factor = (1.0 + monthly_rate) ** total_months
    monthly_payment = principal * (monthly_rate * factor) / (factor - 1.0)
    return round(monthly_payment, 2)


def calculate_loan_amortization_schedule(
    principal: float,
    annual_interest_rate: float,
    amortization_years: int,
    hold_period_years: int,
    interest_only_months: int = 0,
) -> List[Tuple[float, float, float]]:
    """Build multi-year loan amortization summary.

    Returns a list of tuples for each year (1 to hold_period_years):
    (annual_principal_paid, annual_interest_paid, ending_loan_balance)
    """
    if principal <= 0.0:
        return [(0.0, 0.0, 0.0) for _ in range(hold_period_years)]

    monthly_rate = annual_interest_rate / 12.0
    # Payment when amortizing over remaining term or full term
    amort_months = max(1, (amortization_years * 12) - interest_only_months)
    if monthly_rate > 0.0:
        factor = (1.0 + monthly_rate) ** amort_months
        amort_monthly_payment = principal * (monthly_rate * factor) / (factor - 1.0)
    else:
        amort_monthly_payment = principal / amort_months

    schedule = []
    balance = principal
    total_months = hold_period_years * 12

    month_idx = 1
    for year in range(1, hold_period_years + 1):
        year_principal = 0.0
        year_interest = 0.0

        for _ in range(12):
            if month_idx > total_months or balance <= 0.0:
                break

            interest_payment = balance * monthly_rate
            if month_idx <= interest_only_months:
                principal_payment = 0.0
            else:
                principal_payment = min(balance, amort_monthly_payment - interest_payment)

            balance = max(0.0, balance - principal_payment)
            year_principal += principal_payment
            year_interest += interest_payment
            month_idx += 1

        schedule.append((round(year_principal, 2), round(year_interest, 2), round(balance, 2)))

    return schedule


def calculate_npv(discount_rate: float, cash_flows: List[float]) -> float:
    """Calculate Net Present Value (NPV) given a discount rate and cash flow stream."""
    npv = 0.0
    for t, cf in enumerate(cash_flows):
        npv += cf / ((1.0 + discount_rate) ** t)
    return round(npv, 2)


def calculate_irr(cash_flows: List[float], max_iter: int = 200, tol: float = 1e-6) -> float:
    """Calculate Internal Rate of Return (IRR) using hybrid Newton-Raphson and bisection."""
    if not cash_flows or len(cash_flows) < 2:
        return 0.0

    # Must have at least one negative and one positive cash flow
    has_negative = any(cf < 0 for cf in cash_flows)
    has_positive = any(cf > 0 for cf in cash_flows)
    if not (has_negative and has_positive):
        return 0.0

    # Objective function: NPV(r)
    def npv_func(rate: float) -> float:
        val = 0.0
        for t, cf in enumerate(cash_flows):
            val += cf / ((1.0 + rate) ** t)
        return val

    # Derivative: d/dr NPV(r)
    def npv_prime(rate: float) -> float:
        val = 0.0
        for t, cf in enumerate(cash_flows):
            if t > 0:
                val -= t * cf / ((1.0 + rate) ** (t + 1))
        return val

    # Try Newton-Raphson starting at 0.10 (10%)
    rate = 0.10
    for _ in range(max_iter):
        if rate <= -0.99:
            rate = -0.90
        val = npv_func(rate)
        if math.isclose(val, 0.0, abs_tol=tol):
            return round(rate, 6)
        prime = npv_prime(rate)
        if math.isclose(prime, 0.0, abs_tol=1e-12):
            break
        step = val / prime
        rate -= step
        if rate < -0.99 or rate > 10.0:
            break

    # Fallback: Bisection search between -0.95 and 5.0 (500%)
    low = -0.95
    high = 5.0
    f_low = npv_func(low)
    f_high = npv_func(high)

    if f_low * f_high > 0:
        # Check if 0.0 is better
        return round(rate if (-0.99 < rate < 10.0) else 0.0, 6)

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        f_mid = npv_func(mid)
        if math.isclose(f_mid, 0.0, abs_tol=tol) or (high - low) / 2.0 < tol:
            return round(mid, 6)
        if f_low * f_mid < 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return round((low + high) / 2.0, 6)


def calculate_equity_multiple(initial_equity: float, total_cash_returned: float) -> float:
    """Calculate equity multiple (total distributions / invested equity)."""
    if initial_equity <= 0.0:
        return 0.0
    return round(total_cash_returned / initial_equity, 3)


def calculate_dscr(noi: float, annual_debt_service: float) -> float:
    """Calculate Debt Service Coverage Ratio (DSCR = NOI / Debt Service)."""
    if annual_debt_service <= 0.0:
        return 99.99
    return round(noi / annual_debt_service, 3)


def calculate_debt_yield(noi: float, loan_amount: float) -> float:
    """Calculate Debt Yield (NOI / Loan Amount)."""
    if loan_amount <= 0.0:
        return 1.0
    return round(noi / loan_amount, 4)


def calculate_cap_rate(noi: float, property_value: float) -> float:
    """Calculate Capitalization Rate (NOI / Asset Value)."""
    if property_value <= 0.0:
        return 0.0
    return round(noi / property_value, 4)


def calculate_exit_sale_proceeds(
    exit_year_noi: float,
    exit_cap_rate: float,
    selling_costs_pct: float = 0.02,
) -> float:
    """Calculate net terminal asset sale proceeds before debt payoff."""
    if exit_cap_rate <= 0.0:
        return 0.0
    gross_sale_price = exit_year_noi / exit_cap_rate
    net_proceeds = gross_sale_price * (1.0 - selling_costs_pct)
    return round(net_proceeds, 2)
