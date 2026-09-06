"""Data export subsystem for cash flows, waterfalls, portfolios, and underwriting results."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from autonomous_multi_agent_real.types import UnderwritingResult

if TYPE_CHECKING:
    from autonomous_multi_agent_real.portfolio.models import PortfolioRollup


class DataExporter:
    """Exports structured underwriting data to CSV and JSON formats."""

    @staticmethod
    def export_cashflows_csv(result: UnderwritingResult) -> str:
        """Export multi-year pro-forma cash flow schedule to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Year",
                "Gross Potential Rent",
                "Vacancy Loss",
                "Effective Gross Income",
                "Operating Expenses",
                "Net Operating Income",
                "Capital Expenditures",
                "Debt Service",
                "Before Tax Cash Flow",
                "Exit Sale Proceeds",
                "Net Cash Flow",
                "Ending Loan Balance",
                "DSCR",
            ]
        )

        for cf in result.cash_flows:
            writer.writerow(
                [
                    cf.year,
                    f"{cf.gross_potential_rent:.2f}",
                    f"{cf.vacancy_loss:.2f}",
                    f"{cf.effective_gross_income:.2f}",
                    f"{cf.operating_expenses:.2f}",
                    f"{cf.net_operating_income:.2f}",
                    f"{cf.capital_expenditures:.2f}",
                    f"{cf.debt_service:.2f}",
                    f"{cf.before_tax_cash_flow:.2f}",
                    f"{cf.exit_sale_proceeds:.2f}",
                    f"{cf.net_cash_flow:.2f}",
                    f"{cf.ending_loan_balance:.2f}",
                    f"{cf.dscr:.3f}",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_waterfall_csv(result: UnderwritingResult) -> str:
        """Export GP/LP equity distribution waterfall ledger to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        if not result.waterfall:
            return ""

        writer.writerow(
            [
                "Year",
                "Total Distributable Cash",
                "LP Distribution",
                "GP Distribution",
                "GP Promote",
                "LP Unreturned Capital",
                "GP Unreturned Capital",
            ]
        )

        for dist in result.waterfall.annual_distributions:
            writer.writerow(
                [
                    dist.year,
                    f"{dist.total_distributable_cash:.2f}",
                    f"{dist.lp_distribution:.2f}",
                    f"{dist.gp_distribution:.2f}",
                    f"{dist.gp_promote:.2f}",
                    f"{dist.lp_unreturned_capital:.2f}",
                    f"{dist.gp_unreturned_capital:.2f}",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_sensitivity_csv(result: UnderwritingResult) -> str:
        """Export sensitivity matrix (Rent Growth vs Exit Cap Rate) to CSV."""
        if not result.sensitivity:
            return ""

        output = io.StringIO()
        writer = csv.writer(output)
        sens = result.sensitivity

        header = ["Rent Growth / Exit Cap"] + [f"{c:.4f}" for c in sens.col_values]
        writer.writerow(header)

        for i, r_val in enumerate(sens.row_values):
            row = [f"{r_val:.4f}"] + [f"{v:.4f}" for v in sens.irr_matrix[i]]
            writer.writerow(row)

        return output.getvalue()

    @staticmethod
    def export_portfolio_csv(rollup: PortfolioRollup) -> str:
        """Export portfolio asset roster and metrics to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "Deal ID",
                "Deal Title",
                "Property Type",
                "Purchase Price",
                "Equity Allocated",
                "Loan Amount",
                "Levered IRR",
                "Equity Multiple",
                "Weight By Equity",
            ]
        )

        for alloc in rollup.allocations:
            writer.writerow(
                [
                    alloc.deal_id,
                    alloc.deal_title,
                    alloc.property_type,
                    f"{alloc.purchase_price:.2f}",
                    f"{alloc.equity_allocated:.2f}",
                    f"{alloc.loan_amount:.2f}",
                    f"{alloc.levered_irr:.4f}",
                    f"{alloc.equity_multiple:.3f}",
                    f"{alloc.weight_by_equity:.4f}",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_underwriting_json(result: UnderwritingResult, indent: int = 2) -> str:
        """Export full underwriting dossier as clean JSON."""
        return result.model_dump_json(indent=indent)
