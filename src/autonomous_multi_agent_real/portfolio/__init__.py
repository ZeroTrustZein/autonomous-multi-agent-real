"""Portfolio management, multi-deal aggregation, and stress testing subsystem."""

from __future__ import annotations

from autonomous_multi_agent_real.portfolio.engine import PortfolioManager
from autonomous_multi_agent_real.portfolio.models import (
    PortfolioDealAllocation,
    PortfolioRiskProfile,
    PortfolioRollup,
    PortfolioStressResult,
    PortfolioStressScenario,
)

__all__ = [
    "PortfolioDealAllocation",
    "PortfolioRollup",
    "PortfolioStressScenario",
    "PortfolioStressResult",
    "PortfolioRiskProfile",
    "PortfolioManager",
]
