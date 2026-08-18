"""
Agent Base — Common interface for all multi-agent system agents
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class AgentState:
    agent_name: str
    status: str  # ACTIVE, IDLE, ERROR
    last_update: datetime
    metrics: Dict[str, float]
    errors: int


class AgentBase(ABC):
    """Base class for all agents in the multi-agent system"""

    def __init__(self, name: str, config: Optional[Dict] = None):
        self.name = name
        self.config = config or {}
        self.state = AgentState(
            agent_name=name,
            status="IDLE",
            last_update=datetime.utcnow(),
            metrics={},
            errors=0
        )
        self._running = False

    @abstractmethod
    async def initialize(self):
        """Initialize agent resources"""
        pass

    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return signal"""
        pass

    @abstractmethod
    async def shutdown(self):
        """Cleanup agent resources"""
        pass

    async def start(self):
        """Start agent"""
        await self.initialize()
        self._running = True
        self.state.status = "ACTIVE"

    async def stop(self):
        """Stop agent"""
        self._running = False
        self.state.status = "IDLE"
        await self.shutdown()

    def get_state(self) -> AgentState:
        """Get current agent state"""
        return self.state

    def update_metrics(self, metrics: Dict[str, float]):
        """Update agent metrics"""
        self.state.metrics.update(metrics)
        self.state.last_update = datetime.utcnow()
