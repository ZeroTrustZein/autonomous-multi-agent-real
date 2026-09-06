"""Institutional credit policy validation and underwriting compliance rule engine."""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from autonomous_multi_agent_real.rules.models import (
    ComplianceReport,
    RuleCategory,
    RuleDefinition,
    RuleEvaluationResult,
    RuleSeverity,
)

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext
    from autonomous_multi_agent_real.types import PropertyDeal

OPERATOR_MAP: Dict[str, Callable[[Any, Any], bool]] = {
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "==": operator.eq,
    "!=": operator.ne,
}


def get_default_institutional_rules() -> List[RuleDefinition]:
    """Provide standard commercial real estate institutional credit policy rules."""
    return [
        RuleDefinition(
            id="POL-LEV-01",
            name="Maximum Senior LTV Covenant",
            category=RuleCategory.LEVERAGE,
            severity=RuleSeverity.ERROR,
            description="Senior loan-to-value must not exceed 80.0% of purchase price.",
            threshold=0.80,
            operator="<=",
            remediation="Downsize debt commitment and increase sponsor/LP equity capitalization.",
        ),
        RuleDefinition(
            id="POL-LEV-02",
            name="Target Senior LTV Guideline",
            category=RuleCategory.LEVERAGE,
            severity=RuleSeverity.WARNING,
            description="Recommended senior loan-to-value should not exceed 75.0%.",
            threshold=0.75,
            operator="<=",
            remediation="Consider moderate deleveraging to widen debt service safety margin.",
        ),
        RuleDefinition(
            id="POL-DSCR-01",
            name="Minimum DSCR Covenant Floor",
            category=RuleCategory.DEBT_SERVICE,
            severity=RuleSeverity.ERROR,
            description="Year 1 Debt Service Coverage Ratio must be at least 1.15x.",
            threshold=1.15,
            operator=">=",
            remediation="Increase equity down payment or request an interest-only amortization period.",
        ),
        RuleDefinition(
            id="POL-DSCR-02",
            name="Target DSCR Hurdle",
            category=RuleCategory.DEBT_SERVICE,
            severity=RuleSeverity.WARNING,
            description="Target Year 1 DSCR should equal or exceed 1.25x for institutional financing.",
            threshold=1.25,
            operator=">=",
            remediation="Negotiate favorable interest rate spread or size debt to 1.25x constraint.",
        ),
        RuleDefinition(
            id="POL-DY-01",
            name="Minimum Debt Yield Floor",
            category=RuleCategory.DEBT_SERVICE,
            severity=RuleSeverity.ERROR,
            description="Year 1 Debt Yield (NOI / Loan) must be at least 7.0%.",
            threshold=0.07,
            operator=">=",
            remediation="Reduce loan balance until Debt Yield meets minimum lender requirement.",
        ),
        RuleDefinition(
            id="POL-DY-02",
            name="Target Debt Yield Hurdle",
            category=RuleCategory.DEBT_SERVICE,
            severity=RuleSeverity.WARNING,
            description="Target Debt Yield should equal or exceed 8.0%.",
            threshold=0.08,
            operator=">=",
            remediation="Structure debt with debt yield sizing gate.",
        ),
        RuleDefinition(
            id="POL-RES-01",
            name="Minimum Replacement Reserves",
            category=RuleCategory.RESERVE_ADEQUACY,
            severity=RuleSeverity.WARNING,
            description="Replacement reserve escrow must be at least $250/unit/year.",
            threshold=250.0,
            operator=">=",
            remediation="Increase annual replacement reserve line item in pro-forma operating expenses.",
        ),
        RuleDefinition(
            id="POL-REHAB-01",
            name="Maximum Rehab to Basis Concentration",
            category=RuleCategory.VALUATION_BASIS,
            severity=RuleSeverity.WARNING,
            description="Rehab budget should not exceed 25.0% of purchase price.",
            threshold=0.25,
            operator="<=",
            remediation="Require GMP contractor contract, phase capital improvements, and escrow contingency.",
        ),
        RuleDefinition(
            id="POL-RET-01",
            name="Minimum Levered IRR Hurdle",
            category=RuleCategory.RETURN_HURDLE,
            severity=RuleSeverity.ERROR,
            description="Modeled Levered IRR must exceed 10.0% capital hurdle.",
            threshold=0.10,
            operator=">=",
            remediation="Renegotiate acquisition price or model higher operational efficiencies.",
        ),
        RuleDefinition(
            id="POL-RISK-01",
            name="Maximum Covenant Default Probability",
            category=RuleCategory.OPERATIONAL_SAFETY,
            severity=RuleSeverity.WARNING,
            description="Monte Carlo DSCR default breach probability should be under 5.0%.",
            threshold=0.05,
            operator="<=",
            remediation="Increase cash operating deficit escrow to protect against occupancy stress.",
        ),
    ]


class RuleEngine:
    """Evaluates institutional underwriting policies against deal contexts and parameters."""

    def __init__(self, rules: Optional[List[RuleDefinition]] = None):
        self.rules: Dict[str, RuleDefinition] = {}
        for r in rules or get_default_institutional_rules():
            self.rules[r.id] = r
        self._custom_extractors: Dict[str, Callable[[DealWorkflowContext], Optional[float]]] = {}

    def register_rule(
        self,
        rule: RuleDefinition,
        extractor: Optional[Callable[[DealWorkflowContext], Optional[float]]] = None,
    ) -> None:
        """Add or overwrite a rule definition with an optional custom value extractor."""
        self.rules[rule.id] = rule
        if extractor is not None:
            self._custom_extractors[rule.id] = extractor

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self._custom_extractors.pop(rule_id, None)
            return True
        return False

    def extract_metric(self, rule_id: str, context: DealWorkflowContext) -> Optional[float]:
        """Extract the numeric metric corresponding to a rule from the workflow context."""
        if rule_id in self._custom_extractors:
            return self._custom_extractors[rule_id](context)

        deal = context.deal
        debt = context.debt_sizing
        metrics = context.deal_metrics
        sim = context.monte_carlo

        if rule_id in ("POL-LEV-01", "POL-LEV-02"):
            if debt:
                return debt.ltv_ratio
            return 1.0 - deal.financing.down_payment_pct

        elif rule_id in ("POL-DSCR-01", "POL-DSCR-02"):
            if debt:
                return debt.dscr_year1
            return None

        elif rule_id in ("POL-DY-01", "POL-DY-02"):
            if debt:
                return debt.debt_yield_pct
            return None

        elif rule_id == "POL-RES-01":
            return deal.expenses.replacement_reserves_per_unit

        elif rule_id == "POL-REHAB-01":
            return deal.rehab_budget / deal.purchase_price if deal.purchase_price > 0 else 0.0

        elif rule_id == "POL-RET-01":
            if metrics:
                return metrics.levered_irr
            return None

        elif rule_id == "POL-RISK-01":
            if sim:
                return sim.probability_dscr_breach
            return None

        return None

    def evaluate(self, context: DealWorkflowContext) -> ComplianceReport:
        """Evaluate all active rules against the provided deal workflow context."""
        results: List[RuleEvaluationResult] = []
        passed_count = 0
        warning_count = 0
        error_count = 0

        for rule in self.rules.values():
            actual = self.extract_metric(rule.id, context)
            if actual is None:
                # Metric not yet calculated in context; skip or treat as inconclusive
                continue

            cmp_fn = OPERATOR_MAP.get(rule.operator, operator.eq)
            passed = bool(cmp_fn(actual, rule.threshold))

            if passed:
                passed_count += 1
                msg = f"{rule.name} PASSED: Actual {actual:.3f} {rule.operator} Threshold {rule.threshold:.3f}"
                remediation = None
            else:
                msg = f"{rule.name} VIOLATED: Actual {actual:.3f} failed {rule.operator} Threshold {rule.threshold:.3f}"
                remediation = rule.remediation
                if rule.severity == RuleSeverity.ERROR:
                    error_count += 1
                elif rule.severity == RuleSeverity.WARNING:
                    warning_count += 1

            results.append(
                RuleEvaluationResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    passed=passed,
                    actual_value=round(actual, 4),
                    threshold_value=rule.threshold,
                    operator=rule.operator,
                    message=msg,
                    remediation=remediation,
                )
            )

        is_compliant = error_count == 0

        return ComplianceReport(
            deal_id=context.deal.id,
            is_compliant=is_compliant,
            rules_checked=len(results),
            passed_count=passed_count,
            warning_count=warning_count,
            error_count=error_count,
            results=results,
        )

    def evaluate_deal(self, deal: PropertyDeal) -> ComplianceReport:
        """Pre-underwriting screening of deal parameters against basic structural rules."""
        from autonomous_multi_agent_real.engine.state import DealWorkflowContext

        ctx = DealWorkflowContext(deal=deal)
        return self.evaluate(ctx)
