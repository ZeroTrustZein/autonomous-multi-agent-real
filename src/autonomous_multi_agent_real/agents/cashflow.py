"""Multi-year pro-forma cash flow and return waterfall agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from autonomous_multi_agent_real.agents.base import BaseAgent
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
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
    AnnualCashFlow,
    DealMetrics,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext


class CashFlowAgent(BaseAgent):
    """Models multi-year operating statements, debt payments, terminal disposition, and returns."""

    def __init__(self, hurdle_irr: float = 0.14, hurdle_equity_multiple: float = 1.70):
        super().__init__(
            role=AgentRole.CASH_FLOW,
            name="Pro-Forma Cash Flow Agent",
            description="Simulates multi-year revenue, OpEx, NOI, debt service, terminal disposition, and investor returns.",
        )
        self.hurdle_irr = hurdle_irr
        self.hurdle_equity_multiple = hurdle_equity_multiple

    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport:
        deal = context.deal
        debt = context.debt_sizing
        if debt is None:
            raise ValueError("Debt sizing must be completed before running cash flow simulation.")

        units = deal.total_units
        hold_years = deal.hold_period_years
        fin = deal.financing

        # Amortization schedule
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

        annual_flows: list[AnnualCashFlow] = []
        levered_flows = [-debt.equity_required]
        unlevered_flows = [-deal.total_acquisition_basis]

        total_distributions = 0.0
        coc_yields = []
        dscrs = []

        for yr in range(1, hold_years + 1):
            rent_growth_factor = (1.0 + deal.annual_rent_growth_pct) ** yr
            exp_growth_factor = (1.0 + deal.annual_expense_growth_pct) ** yr

            gpr = base_rent * rent_growth_factor
            vacancy_loss = gpr * (1.0 - deal.market_occupancy_pct)
            egi = gpr - vacancy_loss

            fixed_exp = base_fixed_exp * exp_growth_factor
            var_exp = egi * mgmt_pct
            opex = fixed_exp + var_exp
            noi = max(0.0, egi - opex)

            capex = (deal.expenses.replacement_reserves_per_unit * units) * exp_growth_factor
            debt_service = debt.annual_debt_service
            ending_balance = amort_sched[yr - 1][2] if yr <= len(amort_sched) else 0.0

            dscr = calculate_dscr(noi, debt_service)
            dscrs.append(dscr)

            btcf = noi - capex - debt_service

            exit_proceeds = 0.0
            net_terminal_proceeds = 0.0

            if yr == hold_years:
                # Capitalize Year N+1 NOI
                next_noi = noi * (1.0 + deal.annual_rent_growth_pct)
                gross_terminal_value = calculate_exit_sale_proceeds(
                    exit_year_noi=next_noi,
                    exit_cap_rate=deal.exit_cap_rate,
                    selling_costs_pct=deal.selling_costs_pct,
                )
                exit_proceeds = gross_terminal_value
                net_terminal_proceeds = max(0.0, gross_terminal_value - ending_balance)
                net_cf = btcf + net_terminal_proceeds
                unlevered_net_cf = (noi - capex) + gross_terminal_value
            else:
                net_cf = btcf
                unlevered_net_cf = noi - capex

            annual_flows.append(
                AnnualCashFlow(
                    year=yr,
                    gross_potential_rent=round(gpr, 2),
                    vacancy_loss=round(vacancy_loss, 2),
                    effective_gross_income=round(egi, 2),
                    operating_expenses=round(opex, 2),
                    net_operating_income=round(noi, 2),
                    capital_expenditures=round(capex, 2),
                    debt_service=round(debt_service, 2),
                    before_tax_cash_flow=round(btcf, 2),
                    exit_sale_proceeds=round(exit_proceeds, 2),
                    net_cash_flow=round(net_cf, 2),
                    ending_loan_balance=round(ending_balance, 2),
                    dscr=round(dscr, 3),
                )
            )

            levered_flows.append(round(net_cf, 2))
            unlevered_flows.append(round(unlevered_net_cf, 2))
            total_distributions += max(0.0, net_cf)

            if debt.equity_required > 0:
                coc_yields.append(btcf / debt.equity_required)

        # Compute summary metrics
        lev_irr = calculate_irr(levered_flows)
        unlev_irr = calculate_irr(unlevered_flows)
        em = calculate_equity_multiple(debt.equity_required, total_distributions)
        npv = calculate_npv(0.08, levered_flows)
        avg_coc = (sum(coc_yields) / len(coc_yields)) if coc_yields else 0.0
        y1_noi = annual_flows[0].net_operating_income if annual_flows else 0.0
        entry_cap = calculate_cap_rate(y1_noi, deal.total_acquisition_basis)
        min_dscr = min(dscrs) if dscrs else 0.0
        avg_dscr = (sum(dscrs) / len(dscrs)) if dscrs else 0.0

        deal_metrics = DealMetrics(
            unlevered_irr=round(unlev_irr, 4),
            levered_irr=round(lev_irr, 4),
            equity_multiple=round(em, 3),
            net_present_value=round(npv, 2),
            average_cash_on_cash=round(avg_coc, 4),
            entry_cap_rate=round(entry_cap, 4),
            exit_cap_rate=round(deal.exit_cap_rate, 4),
            min_dscr=round(min_dscr, 3),
            average_dscr=round(avg_dscr, 3),
        )

        context.cash_flows = annual_flows
        context.deal_metrics = deal_metrics

        risk_flags = []
        recommendations = []

        if lev_irr < self.hurdle_irr:
            risk_flags.append(
                f"Modeled Levered IRR ({lev_irr:.1%}) fails hurdle threshold ({self.hurdle_irr:.1%})."
            )
            recommendations.append(
                "Renegotiate acquisition price downward to achieve required return hurdle."
            )

        if em < self.hurdle_equity_multiple:
            risk_flags.append(
                f"Equity multiple ({em:.2f}x) falls short of {self.hurdle_equity_multiple:.2f}x benchmark."
            )

        if min_dscr < 1.15:
            risk_flags.append(f"Minimum DSCR drops to {min_dscr:.2f}x during hold period.")

        if not risk_flags:
            status = AgentDecisionStatus.APPROVED
            recommendations.append(
                "Pro-forma returns meet investment hurdles; proceed with Monte Carlo stress testing."
            )
        elif len(risk_flags) == 1:
            status = AgentDecisionStatus.CONDITIONAL
        else:
            status = AgentDecisionStatus.FLAGGED

        confidence_score = 0.92

        metrics = {
            "levered_irr": round(lev_irr, 4),
            "unlevered_irr": round(unlev_irr, 4),
            "equity_multiple": round(em, 3),
            "net_present_value_8pct": round(npv, 2),
            "average_cash_on_cash": round(avg_coc, 4),
            "entry_cap_rate": round(entry_cap, 4),
            "exit_cap_rate": round(deal.exit_cap_rate, 4),
            "min_dscr": round(min_dscr, 3),
            "total_distributions": round(total_distributions, 2),
        }

        summary = (
            f"Modeled {hold_years}-year cash flow yields {lev_irr:.1%} Levered IRR ({unlev_irr:.1%} Unlevered), "
            f"{em:.2f}x Equity Multiple, and {avg_coc:.1%} Avg CoC. Status: {status.value.upper()}."
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
