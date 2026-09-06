"""Institutional Investment Committee Underwriting Memorandum generator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from autonomous_multi_agent_real.types import PropertyDeal, UnderwritingResult

if TYPE_CHECKING:
    from autonomous_multi_agent_real.rules.models import ComplianceReport


class InvestmentMemoGenerator:
    """Generates comprehensive, publication-ready Investment Committee Memoranda in Markdown."""

    def generate_memo(
        self,
        deal: PropertyDeal,
        result: UnderwritingResult,
        compliance_report: Optional[ComplianceReport] = None,
    ) -> str:
        """Render complete underwriting memorandum."""
        m = result.deal_metrics
        d = result.debt_sizing
        mc = result.monte_carlo

        status_badge = (
            "🟢 APPROVED"
            if result.decision.value == "approved"
            else "🟡 CONDITIONAL"
            if result.decision.value == "conditional"
            else "🔴 REJECTED"
        )

        lines: list[str] = [
            "# INVESTMENT COMMITTEE UNDERWRITING MEMORANDUM",
            f"**Deal Title:** {deal.title}  ",
            f"**Address:** {deal.address}  ",
            f"**Asset Class:** {deal.property_type.value.replace('_', ' ').title()}  ",
            f"**Units:** {deal.total_units} | **Gross SqFt:** {deal.gross_square_feet:,.0f}  ",
            f"**Date:** {result.timestamp.strftime('%B %d, %Y')}  ",
            f"**Recommendation Status:** {status_badge} (Score: {result.committee_score:.1f}/100)",
            "",
            "---",
            "",
            "## 1. Executive Summary & Investment Thesis",
            result.executive_summary,
            "",
            "### Core Investment Merits",
        ]

        for point in result.investment_thesis:
            lines.append(f"- {point}")

        lines.extend(
            [
                "",
                "## 2. Sources & Uses of Capital",
                "",
                "| Uses of Funds | Amount ($) | % of Total | Sources of Funds | Amount ($) | % of Total |",
                "| :--- | :---: | :---: | :--- | :---: | :---: |",
            ]
        )

        total_basis = deal.total_acquisition_basis
        purchase_pct = (deal.purchase_price / total_basis * 100.0) if total_basis > 0 else 0.0
        rehab_pct = (deal.rehab_budget / total_basis * 100.0) if total_basis > 0 else 0.0
        closing_cost = deal.purchase_price * deal.financing.closing_costs_pct
        closing_pct = (closing_cost / total_basis * 100.0) if total_basis > 0 else 0.0

        loan_pct = (d.loan_amount / total_basis * 100.0) if total_basis > 0 else 0.0
        equity_pct = (d.equity_required / total_basis * 100.0) if total_basis > 0 else 0.0

        lines.append(
            f"| Purchase Price | ${deal.purchase_price:,.0f} | {purchase_pct:.1f}% | Sized Senior Debt | ${d.loan_amount:,.0f} | {loan_pct:.1f}% |"
        )
        lines.append(
            f"| Upfront Rehab Budget | ${deal.rehab_budget:,.0f} | {rehab_pct:.1f}% | Sponsor & LP Equity | ${d.equity_required:,.0f} | {equity_pct:.1f}% |"
        )
        lines.append(
            f"| Closing & Financing Costs | ${closing_cost:,.0f} | {closing_pct:.1f}% | | | |"
        )
        lines.append(
            f"| **Total Acquisition Basis** | **${total_basis:,.0f}** | **100.0%** | **Total Capitalization** | **${total_basis:,.0f}** | **100.0%** |"
        )

        lines.extend(
            [
                "",
                "## 3. Financial Metrics & Returns Summary",
                "",
                "| Return Indicator | Modeled Baseline | Senior Debt Indicator | Sized Value |",
                "| :--- | :---: | :--- | :---: |",
                f"| **Levered IRR** | **{m.levered_irr:.2%}** | Loan-to-Value (LTV) | {d.ltv_ratio:.1%} |",
                f"| Unlevered IRR | {m.unlevered_irr:.2%} | Year 1 DSCR | {d.dscr_year1:.2f}x |",
                f"| **Equity Multiple** | **{m.equity_multiple:.2f}x** | Year 1 Debt Yield | {d.debt_yield_pct:.2%} |",
                f"| Net Present Value (@ 8.0%) | ${m.net_present_value:,.0f} | Annual Debt Service | ${d.annual_debt_service:,.0f} |",
                f"| Average Cash-on-Cash | {m.average_cash_on_cash:.2%} | Binding Constraint | {d.binding_constraint} |",
                f"| Entry Cap Rate | {m.entry_cap_rate:.2%} | Exit Cap Rate | {m.exit_cap_rate:.2%} |",
            ]
        )

        # Pro-Forma Cash Flow Schedule
        lines.extend(
            [
                "",
                "## 4. Multi-Year Operating Pro-Forma Schedule",
                "",
                "| Yr | Effective Gross Income | Operating Expenses | Net Operating Income | Debt Service | Before-Tax Cash Flow | Exit Proceeds | Net Distributable | DSCR |",
                "| :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |",
            ]
        )

        for cf in result.cash_flows:
            exit_str = f"${cf.exit_sale_proceeds:,.0f}" if cf.exit_sale_proceeds > 0 else "-"
            lines.append(
                f"| {cf.year} | ${cf.effective_gross_income:,.0f} | ${cf.operating_expenses:,.0f} | "
                f"${cf.net_operating_income:,.0f} | ${cf.debt_service:,.0f} | ${cf.before_tax_cash_flow:,.0f} | "
                f"{exit_str} | **${cf.net_cash_flow:,.0f}** | {cf.dscr:.2f}x |"
            )

        # Waterfall returns if available
        if result.waterfall:
            wf = result.waterfall
            lines.extend(
                [
                    "",
                    "## 5. GP / LP Equity Waterfall Structuring",
                    "",
                    f"- **LP Equity Invested:** ${wf.lp_equity_invested:,.0f} | **LP Levered IRR:** **{wf.lp_irr:.2%}** | **LP Multiple:** **{wf.lp_equity_multiple:.2f}x**",
                    f"- **GP Equity Invested:** ${wf.gp_equity_invested:,.0f} | **GP Levered IRR:** **{wf.gp_irr:.2%}** | **GP Multiple:** **{wf.gp_equity_multiple:.2f}x**",
                    f"- **Total GP Carried Interest (Promote):** ${wf.gp_total_promote:,.0f}",
                ]
            )

        # Sensitivity Matrix if available
        if result.sensitivity:
            sens = result.sensitivity
            lines.extend(
                [
                    "",
                    "## 6. Sensitivity Stress Matrix (Exit Cap Rate vs. Rent Growth -> Levered IRR)",
                    "",
                ]
            )
            header = (
                "| Rent Growth \\ Exit Cap | "
                + " | ".join(f"{c:.2%}" for c in sens.col_values)
                + " |"
            )
            divider = "| :-: | " + " | ".join([":-:"] * len(sens.col_values)) + " |"
            lines.append(header)
            lines.append(divider)
            for i, r_val in enumerate(sens.row_values):
                row_str = (
                    f"| **{r_val:.2%}** | "
                    + " | ".join(f"{v:.2%}" for v in sens.irr_matrix[i])
                    + " |"
                )
                lines.append(row_str)

        # Monte Carlo Risk Modeling
        lines.extend(
            [
                "",
                "## 7. Stochastic Monte Carlo Risk Analysis",
                "",
                f"Simulated **{mc.iterations:,}** stochastic iterations across rent growth, vacancy, OpEx, and exit cap rate distributions:",
                "",
                "| Statistic | Value | Risk Interpretation |",
                "| :--- | :---: | :--- |",
                f"| **Median Levered IRR (P50)** | **{mc.p50_irr:.2%}** | Base expected stochastic central tendency |",
                f"| Downside Case (P10 IRR) | {mc.p10_irr:.2%} | Conservative 90% confidence downside floor |",
                f"| Upside Case (P90 IRR) | {mc.p90_irr:.2%} | Bullish execution top-decile return |",
                f"| Mean Equity Multiple | {mc.mean_equity_multiple:.2f}x | Average capital return multiplier |",
                f"| **Prob(Covenant Breach < 1.0x DSCR)** | **{mc.probability_dscr_breach:.2%}** | Structural debt default vulnerability |",
                f"| Prob(Negative Return) | {mc.probability_negative_irr:.2%} | Total principal loss probability |",
            ]
        )

        if mc.var_95_irr is not None and mc.cvar_95_irr is not None:
            lines.extend(
                [
                    f"| Value-at-Risk (VaR 95%) | {mc.var_95_irr:.2%} | 95% worst-case return threshold |",
                    f"| Conditional VaR (CVaR 95%) | {mc.cvar_95_irr:.2%} | Expected return in worst 5% tail |",
                ]
            )

        # Compliance Report if present
        if compliance_report:
            lines.extend(
                [
                    "",
                    "## 8. Institutional Credit Policy & Compliance Audit",
                    "",
                    f"- **Overall Compliance:** {'✅ PASSED (All Covenants Satisfied)' if compliance_report.is_compliant else '❌ FAILED (Covenant Breaches Detected)'}",
                    f"- **Policy Score:** {compliance_report.compliance_score:.1f}% ({compliance_report.passed_count}/{compliance_report.rules_checked} rules satisfied)",
                    f"- **Errors:** {compliance_report.error_count} | **Warnings:** {compliance_report.warning_count}",
                    "",
                    "| Rule | Status | Actual Value | Threshold | Remediation |",
                    "| :--- | :---: | :---: | :---: | :--- |",
                ]
            )
            for r in compliance_report.results:
                badge = "PASS" if r.passed else f"**{r.severity.value.upper()}**"
                remed = r.remediation or "None required"
                lines.append(
                    f"| {r.rule_name} | {badge} | {r.actual_value:.3f} | {r.operator} {r.threshold_value:.3f} | {remed} |"
                )

        # Autonomous Swarm Agents Deliberation
        lines.extend(
            [
                "",
                "## 9. Autonomous Swarm Agent Findings & Recommendations",
                "",
            ]
        )
        for _, rep in result.agent_reports.items():
            lines.append(f"### {rep.agent_name} ({rep.agent_role.value.upper()})")
            lines.append(
                f"**Verdict:** `{rep.status.value.upper()}` | **Confidence:** {rep.confidence_score:.0%}"
            )
            lines.append(f"> {rep.summary}")
            if rep.risk_flags:
                lines.append("**Identified Risk Flags:**")
                for rf in rep.risk_flags:
                    lines.append(f"- ⚠️ {rf}")
            if rep.recommendations:
                lines.append("**Recommendations:**")
                for rec in rep.recommendations:
                    lines.append(f"- 💡 {rec}")
            lines.append("")

        # Key Risks & Mitigants
        lines.extend(
            [
                "## 10. Key Underwriting Risks & Structuring Mitigants",
                "",
                "| Identified Risk Factor | Mandatory Mitigant / Structuring Requirement |",
                "| :--- | :--- |",
            ]
        )
        for rm in result.key_risks_and_mitigants:
            lines.append(f"| {rm['risk']} | {rm['mitigant']} |")

        # Committee Signatures
        lines.extend(
            [
                "",
                "## 11. Investment Committee Action & Sign-Off",
                "",
                f"**Final Committee Verdict:** **{result.decision.value.upper()}**  ",
                f"**Composite Deal Score:** **{result.committee_score:.1f} / 100**  ",
                "",
                "| Committee Member Role | Vote / Attestation | Signature | Date |",
                "| :--- | :---: | :---: | :---: |",
                f"| Managing Director, Acquisitions | {result.decision.value.upper()} | ____________________ | {result.timestamp.strftime('%Y-%m-%d')} |",
                f"| Head of Credit & Capital Markets | {result.decision.value.upper()} | ____________________ | {result.timestamp.strftime('%Y-%m-%d')} |",
                f"| Chief Risk Officer (CRO) | {result.decision.value.upper()} | ____________________ | {result.timestamp.strftime('%Y-%m-%d')} |",
                "",
                "---",
                "*Generated by Autonomous Multi-Agent Real Estate Deal Underwriting Workflow Engine*",
            ]
        )

        return "\n".join(lines)
