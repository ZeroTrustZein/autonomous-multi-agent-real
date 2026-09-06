"""Abstract base class for underwriting swarm agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from autonomous_multi_agent_real.types import AgentAnalysisReport, AgentRole

if TYPE_CHECKING:
    from autonomous_multi_agent_real.engine.state import DealWorkflowContext


class BaseAgent(ABC):
    """Base class providing interface and helpers for all swarm agents."""

    def __init__(self, role: AgentRole, name: str, description: str):
        self.role = role
        self.name = name
        self.description = description

    @abstractmethod
    def analyze(self, context: DealWorkflowContext) -> AgentAnalysisReport:
        """Execute agent analysis on deal context and return report."""
        pass
