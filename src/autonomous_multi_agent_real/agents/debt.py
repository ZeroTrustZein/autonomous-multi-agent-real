"""Debt capital markets and financing underwriting agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autonomous_multi_agent_real.agents.base import BaseAgent
from autonomous_multi_agent_real.engine.financial import (
    calculate_debt_yield,
    calculate_dscr,
    calculate_monthly_mortgage_payment,
)
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
    DebtSizingResult,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext


class DebtAgent(BaseAgent):
    """Underwrites senior debt sizing across LTV, DSCR, and Debt Yield constraints."""

    def __init__(self, target_min_dscr: float = 1.25, target_min_debt_yield: float = 0.08):
        super().__init__(
            role=AgentRole.DEBT_FINANCING,
            name="Debt Capital Markets Agent",
            description="Underwrites senior loan parameters, debt service schedules, and sizing constraints.",
        )
        self.target_min_dscr = target_min_dscr
        self.target_min_debt_yield = target_min_debt_yield

    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport:
        deal = context.deal
        fin = deal.financing
        price = deal.purchase_price
        units = deal.total_units

        # Approximate Year 1 NOI for sizing
        gpr_y1 = deal.total_market_annual_rent * (1.0 + deal.annual_rent_growth_pct)
        egi_y1 = gpr_y1 * deal.market_occupancy_pct
        fixed_exp = deal.expenses.fixed_annual_expenses(units) * (
            1.0 + deal.annual_expense_growth_pct
        )
        var_exp = egi_y1 * deal.expenses.property_management_pct
        noi_y1 = max(1000.0, egi_y1 - fixed_exp - var_exp)

        # 1. Sizing by Maximum LTV (e.g. 75%)
        max_ltv = 1.0 - fin.down_payment_pct
        loan_by_ltv = price * max_ltv

        # 2. Sizing by Minimum DSCR (e.g. 1.25x)
        unit_monthly_payment = calculate_monthly_mortgage_payment(
            1.0, fin.interest_rate, fin.amortization_years
        )
        unit_annual_debt_service = unit_monthly_payment * 12.0
        max_loan_by_dscr = (
            (noi_y1 / (self.target_min_dscr * unit_annual_debt_service))
            if unit_annual_debt_service > 0
            else loan_by_ltv
        )

        # 3. Sizing by Minimum Debt Yield (e.g. 8.0%)
        max_loan_by_dy = (
            (noi_y1 / self.target_min_debt_yield) if self.target_min_debt_yield > 0 else loan_by_ltv
        )

        # Determine binding constraint
        candidates = [
            ("LTV", loan_by_ltv),
            ("DSCR", max_loan_by_dscr),
            ("Debt Yield", max_loan_by_dy),
        ]
        binding_constraint, sized_loan = min(candidates, key=lambda x: x[1])
        sized_loan = round(max(0.0, sized_loan), 2)

        # Compute debt service and metrics
        monthly_pmt = calculate_monthly_mortgage_payment(
            sized_loan, fin.interest_rate, fin.amortization_years
        )
        annual_debt_service = monthly_pmt * 12.0
        ltv_actual = sized_loan / price if price > 0 else 0.0
        dscr_actual = calculate_dscr(noi_y1, annual_debt_service)
        dy_actual = calculate_debt_yield(noi_y1, sized_loan)

        total_basis = deal.total_acquisition_basis
        equity_required = round(max(0.0, total_basis - sized_loan), 2)

        debt_result = DebtSizingResult(
            loan_amount=sized_loan,
            equity_required=equity_required,
            monthly_payment=monthly_pmt,
            annual_debt_service=annual_debt_service,
            ltv_ratio=round(ltv_actual, 4),
            dscr_year1=round(dscr_actual, 3),
            debt_yield_pct=round(dy_actual, 4),
            binding_constraint=binding_constraint,
        )
        context.debt_sizing = debt_result

        risk_flags = []
        recommendations = []

        if dscr_actual < self.target_min_dscr:
            risk_flags.append(
                f"Year 1 DSCR of {dscr_actual:.2f}x is tighter than target hurdle ({self.target_min_dscr:.2f}x)."
            )
            recommendations.append(
                "Increase equity commitment or negotiate an interest-only period."
            )

        if dy_actual < self.target_min_debt_yield:
            risk_flags.append(
                f"Year 1 Debt Yield of {dy_actual:.1%} is below lender threshold ({self.target_min_debt_yield:.1%})."
            )

        if ltv_actual > 0.80:
            risk_flags.append(f"Elevated leverage with LTV at {ltv_actual:.1%}.")

        if not risk_flags:
            status = AgentDecisionStatus.APPROVED
            recommendations.append(
                "Debt sizing is conservative; proceed with cash flow waterfall simulation."
            )
        elif len(risk_flags) == 1:
            status = AgentDecisionStatus.CONDITIONAL
        else:
            status = AgentDecisionStatus.FLAGGED

        confidence_score = 0.94

        metrics = {
            "sized_loan_amount": sized_loan,
            "equity_required": equity_required,
            "monthly_debt_service": monthly_pmt,
            "annual_debt_service": annual_debt_service,
            "ltv_ratio": round(ltv_actual, 4),
            "dscr_year_1": round(dscr_actual, 3),
            "debt_yield_pct": round(dy_actual, 4),
            "binding_constraint": binding_constraint,
        }

        summary = (
            f"Sized loan to ${sized_loan:,.0f} ({ltv_actual:.1%} LTV, {binding_constraint} constrained). "
            f"Year 1 DSCR: {dscr_actual:.2f}x, Debt Yield: {dy_actual:.1%}. Equity required: ${equity_required:,.0f}."
        )

        return AgentAnalysisReport(
            agent_role=self.role,
            agent_name=self.name,
            status=status,
            summary=summary,
            confidence_score=confidence_score,
            key_metrics=metrics,
            risk_flags=risk_flags,
            recommendations=recommendations,
        )
