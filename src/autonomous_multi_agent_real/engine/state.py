"""State and workflow context tracking deal evaluation progression."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AnnualCashFlow,
    BreakevenMetrics,
    DealMetrics,
    DebtSizingResult,
    MonteCarloSimulationResult,
    PricingOptimizationResult,
    PropertyDeal,
    SensitivityMatrix,
    TaxAnalysisResult,
    WaterfallResult,
    WorkflowStage,
)


class DealWorkflowContext(BaseModel):
    """Execution context passing through the agent underwriting pipeline."""

    deal: PropertyDeal
    current_stage: WorkflowStage = WorkflowStage.INTAKE
    agent_reports: Dict[str, AgentAnalysisReport] = Field(default_factory=dict)
    debt_sizing: Optional[DebtSizingResult] = None
    cash_flows: List[AnnualCashFlow] = Field(default_factory=list)
    deal_metrics: Optional[DealMetrics] = None
    monte_carlo: Optional[MonteCarloSimulationResult] = None
    waterfall: Optional[WaterfallResult] = None
    sensitivity: Optional[SensitivityMatrix] = None
    breakeven: Optional[BreakevenMetrics] = None
    tax_analysis: Optional[TaxAnalysisResult] = None
    pricing_optimization: Optional[PricingOptimizationResult] = None
    audit_events: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    def record_event(
        self, event_type: str, message: str, payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """Append an audit trail event."""
        self.audit_events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": self.current_stage.value,
                "event_type": event_type,
                "message": message,
                "payload": payload or {},
            }
        )

    def add_agent_report(self, report: AgentAnalysisReport) -> None:
        """Register an agent's finished report in context."""
        self.agent_reports[report.agent_role.value] = report
        self.record_event(
            event_type="agent_completed",
            message=f"{report.agent_name} completed with status {report.status.value}",
            payload={"confidence": report.confidence_score, "flags": len(report.risk_flags)},
        )
