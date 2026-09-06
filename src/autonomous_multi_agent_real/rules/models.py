"""Domain models for institutional credit policy and deal compliance rules."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuleSeverity(str, Enum):
    """Severity classification for rule deviations."""

    ERROR = "error"  # Hard stop / covenant breach
    WARNING = "warning"  # Soft guideline deviation requiring justification
    INFO = "info"  # Informational advisory metric


class RuleCategory(str, Enum):
    """Credit policy domain category."""

    LEVERAGE = "leverage"
    DEBT_SERVICE = "debt_service"
    RETURN_HURDLE = "return_hurdle"
    RESERVE_ADEQUACY = "reserve_adequacy"
    VALUATION_BASIS = "valuation_basis"
    OPERATIONAL_SAFETY = "operational_safety"


class RuleDefinition(BaseModel):
    """Specification of an institutional underwriting compliance rule."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique rule identifier (e.g. POL-LEV-01)")
    name: str = Field(..., description="Human-readable rule title")
    category: RuleCategory
    severity: RuleSeverity
    description: str
    threshold: float
    operator: str = Field(..., description="'<=', '>=', '<', '>', '=='")
    remediation: str


class RuleEvaluationResult(BaseModel):
    """Outcome of evaluating an individual policy rule against a deal."""

    model_config = ConfigDict(extra="ignore")

    rule_id: str
    rule_name: str
    category: RuleCategory
    severity: RuleSeverity
    passed: bool
    actual_value: float
    threshold_value: float
    operator: str
    message: str
    remediation: Optional[str] = None


class ComplianceReport(BaseModel):
    """Consolidated policy audit results for a deal."""

    model_config = ConfigDict(extra="ignore")

    deal_id: str
    is_compliant: bool = Field(..., description="True if no ERROR severity violations exist")
    rules_checked: int = 0
    passed_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    results: List[RuleEvaluationResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0

    @property
    def compliance_score(self) -> float:
        """Percentage of rules passed cleanly (0.0 to 100.0)."""
        if self.rules_checked == 0:
            return 100.0
        return round((self.passed_count / self.rules_checked) * 100.0, 1)
