"""Storage and repository layer for deals, revisions, and simulation runs."""

from __future__ import annotations

from autonomous_multi_agent_real.storage.repository import (
    DealRepository,
    DealRevision,
    get_benchmark_deals,
)

__all__ = ["DealRepository", "DealRevision", "get_benchmark_deals"]
