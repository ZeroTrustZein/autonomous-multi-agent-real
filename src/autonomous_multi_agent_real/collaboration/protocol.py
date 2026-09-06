"""Agent collaboration protocol, message bus, and shared blackboard memory."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageType(str, Enum):
    """Classification of messages exchanged between swarm agents."""

    PROPOSAL = "proposal"
    CRITIQUE = "critique"
    CHALLENGE = "challenge"
    CONCURRENCE = "concurrence"
    REVISION = "revision"
    QUERY = "query"
    RESPONSE = "response"
    SYSTEM = "system"


class AgentMessage(BaseModel):
    """Typed message exchanged across agent swarm bus."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender: str = Field(..., description="Agent role or system identifier sending message")
    recipient: str = Field(default="*", description="Target agent role or '*' for broadcast")
    message_type: MessageType = Field(MessageType.PROPOSAL)
    topic: str = Field(..., description="Topic namespace (e.g. debt.leverage, rent.growth)")
    content: str = Field(..., description="Human-readable message description")
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageBus:
    """In-memory event and message broker for multi-agent communication."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[AgentMessage], None]]] = {}
        self._history: List[AgentMessage] = []

    def subscribe(self, topic_pattern: str, handler: Callable[[AgentMessage], None]) -> None:
        """Subscribe handler callback to a topic pattern (supports wildcard *)."""
        if topic_pattern not in self._handlers:
            self._handlers[topic_pattern] = []
        if handler not in self._handlers[topic_pattern]:
            self._handlers[topic_pattern].append(handler)

    def unsubscribe(self, topic_pattern: str, handler: Callable[[AgentMessage], None]) -> None:
        """Unsubscribe handler callback from a topic pattern."""
        if topic_pattern in self._handlers and handler in self._handlers[topic_pattern]:
            self._handlers[topic_pattern].remove(handler)

    def publish(self, message: AgentMessage) -> None:
        """Publish a message to all matching subscribers and append to history."""
        self._history.append(message)
        for pattern, handlers in self._handlers.items():
            if self._matches(pattern, message.topic):
                for handler in handlers:
                    handler(message)

    def get_history(
        self,
        topic: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        message_type: Optional[MessageType] = None,
    ) -> List[AgentMessage]:
        """Filter message history by attributes."""
        res = self._history
        if topic is not None:
            res = [m for m in res if self._matches(topic, m.topic)]
        if sender is not None:
            res = [m for m in res if m.sender == sender]
        if recipient is not None:
            res = [m for m in res if m.recipient in (recipient, "*")]
        if message_type is not None:
            res = [m for m in res if m.message_type == message_type]
        return list(res)

    def clear(self) -> None:
        """Clear message history and handlers."""
        self._history.clear()
        self._handlers.clear()

    @staticmethod
    def _matches(pattern: str, topic: str) -> bool:
        if pattern == "*" or pattern == topic:
            return True
        regex_pat = "^" + pattern.replace(".", r"\.").replace("*", ".*") + "$"
        return bool(re.match(regex_pat, topic))


class Blackboard:
    """Shared blackboard memory architecture for agent collaboration and fact verification."""

    def __init__(self) -> None:
        self._facts: Dict[str, Dict[str, Any]] = {}
        self._flags: List[Dict[str, Any]] = []
        self._locks: Dict[str, str] = {}

    def set_fact(self, key: str, value: Any, author: str) -> None:
        """Record a verified fact onto the blackboard."""
        self._facts[key] = {
            "value": value,
            "author": author,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_fact(self, key: str, default: Any = None) -> Any:
        """Retrieve fact value or default."""
        fact = self._facts.get(key)
        return fact["value"] if fact is not None else default

    def get_fact_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve full fact record including author and timestamp."""
        return self._facts.get(key)

    def get_all_facts(self) -> Dict[str, Any]:
        """Return dict of all current facts mapped to values."""
        return {k: v["value"] for k, v in self._facts.items()}

    def post_flag(
        self,
        flag: str,
        author: str,
        severity: str = "warning",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Post a risk flag or concern onto the shared blackboard."""
        self._flags.append(
            {
                "id": str(uuid.uuid4())[:8],
                "flag": flag,
                "author": author,
                "severity": severity,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def get_flags(self, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return posted flags, optionally filtered by severity."""
        if severity:
            return [f for f in self._flags if f["severity"] == severity]
        return list(self._flags)

    def acquire_lock(self, resource_name: str, agent_name: str) -> bool:
        """Acquire exclusive lock on a resource/model parameter."""
        current = self._locks.get(resource_name)
        if current is None or current == agent_name:
            self._locks[resource_name] = agent_name
            return True
        return False

    def release_lock(self, resource_name: str, agent_name: str) -> bool:
        """Release exclusive lock if held by agent."""
        if self._locks.get(resource_name) == agent_name:
            del self._locks[resource_name]
            return True
        return False

    def is_locked(self, resource_name: str) -> bool:
        """Check if resource is locked."""
        return resource_name in self._locks

    def snapshot(self) -> Dict[str, Any]:
        """Generate point-in-time snapshot of blackboard state."""
        return {
            "facts": self.get_all_facts(),
            "flags": list(self._flags),
            "active_locks": dict(self._locks),
        }

    def clear(self) -> None:
        """Reset blackboard state."""
        self._facts.clear()
        self._flags.clear()
        self._locks.clear()
