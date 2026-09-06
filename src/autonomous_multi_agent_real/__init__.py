"""Autonomous multi-agent real estate deal underwriting and cash flow simulation workflow engine."""

__version__ = "0.1.0"

from autonomous_multi_agent_real.agents import (
    AcquisitionAgent,
    BaseAgent,
    CashFlowAgent,
    DebtAgent,
    InvestmentCommitteeAgent,
    MarketCompsAgent,
    RiskMonteCarloAgent,
)
from autonomous_multi_agent_real.engine import (
    DealPipeline,
    DealWorkflowContext,
    MonteCarloEngine,
)
from autonomous_multi_agent_real.storage import (
    DealRepository,
    get_benchmark_deals,
)
from autonomous_multi_agent_real.types import (
    AgentAnalysisReport,
    AgentDecisionStatus,
    AgentRole,
    AnnualCashFlow,
    DealMetrics,
    DebtSizingResult,
    FinancingTerms,
    InvestmentDecision,
    MonteCarloSimulationResult,
    OperatingExpenses,
    PropertyDeal,
    PropertyType,
    UnderwritingResult,
    UnitMixItem,
    WorkflowStage,
)

__all__ = [
    "__version__",
    "AcquisitionAgent",
    "BaseAgent",
    "CashFlowAgent",
    "InvestmentCommitteeAgent",
    "DebtAgent",
    "MarketCompsAgent",
    "RiskMonteCarloAgent",
    "DealPipeline",
    "DealWorkflowContext",
    "MonteCarloEngine",
    "DealRepository",
    "get_benchmark_deals",
    "AgentAnalysisReport",
    "AgentDecisionStatus",
    "AgentRole",
    "AnnualCashFlow",
    "DealMetrics",
    "DebtSizingResult",
    "FinancingTerms",
    "InvestmentDecision",
    "MonteCarloSimulationResult",
    "OperatingExpenses",
    "PropertyDeal",
    "PropertyType",
    "UnderwritingResult",
    "UnitMixItem",
    "WorkflowStage",
]
