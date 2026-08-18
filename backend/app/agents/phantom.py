"""
Phantom Agent — High-Frequency Execution & Slippage Management Agent
Manages order routing and execution quality using Databento MBO data
"""
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .agent_base import AgentBase


class VenueType(str, Enum):
    DARK_POOL = "DARK_POOL"
    LIT_EXCHANGE = "LIT_EXCHANGE"
    CROSSING_NETWORK = "CROSSING_NETWORK"


@dataclass
class ExecutionPlan:
    order_id: str
    symbol: str
    side: str
    quantity: float
    venue_allocation: Dict[VenueType, float]
    expected_slippage: float
    urgency: str
    timestamp: datetime


@dataclass
class ExecutionResult:
    order_id: str
    symbol: str
    side: str
    filled_quantity: float
    avg_price: float
    expected_price: float
    slippage: float
    venue: VenueType
    fill_time_ms: float
    timestamp: datetime


class PhantomAgent(AgentBase):
    """High-Frequency Execution & Slippage Management Agent"""

    VENUE_COSTS = {
        VenueType.DARK_POOL: {"fee": 0.0001, "rebate": 0.0003, "info_leakage": 0.1},
        VenueType.LIT_EXCHANGE: {"fee": 0.0003, "rebate": 0.0002, "info_leakage": 0.5},
        VenueType.CROSSING_NETWORK: {"fee": 0.00005, "rebate": 0.0004, "info_leakage": 0.05}
    }

    def __init__(self, config: Optional[Dict] = None):
        super().__init__("Phantom", config)
        self.execution_history: List[ExecutionResult] = []
        self.order_book_data: Dict[int, dict] = {}
        self.slippage_targets: Dict[str, float] = {}

    async def initialize(self):
        """Initialize Phantom agent"""
        self.state.metrics = {
            "orders_routed": 0,
            "avg_slippage": 0,
            "dark_pool_fill_rate": 0,
            "execution_quality_score": 0
        }

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process order and generate execution plan"""
        order = data.get("order", {})
        market_data = data.get("market_data", {})
        order_book = data.get("order_book", {})

        if not order:
            return self._empty_signal("No order provided")

        plan = self._create_execution_plan(order, market_data, order_book)

        signal = {
            "agent": self.name,
            "conviction": 8.0,
            "signal_type": "EXECUTION",
            "execution_plan": {
                "order_id": plan.order_id,
                "symbol": plan.symbol,
                "side": plan.side,
                "quantity": plan.quantity,
                "venue_allocation": {k.value: v for k, v in plan.venue_allocation.items()},
                "expected_slippage": plan.expected_slippage,
                "urgency": plan.urgency
            },
            "routing_recommendation": self._get_routing_recommendation(plan),
            "timestamp": datetime.utcnow().isoformat()
        }

        self.update_metrics({
            "orders_routed": self.state.metrics.get("orders_routed", 0) + 1
        })

        return signal

    async def shutdown(self):
        """Cleanup Phantom resources"""
        pass

    def _create_execution_plan(
        self,
        order: Dict,
        market_data: Dict,
        order_book: Dict
    ) -> ExecutionPlan:
        """Create optimal execution plan"""
        symbol = order.get("symbol", "")
        side = order.get("side", "BUY")
        quantity = order.get("quantity", 0)
        urgency = order.get("urgency", "MEDIUM")

        venue_allocation = self._optimize_venue_allocation(
            symbol, side, quantity, order_book, urgency
        )

        expected_slippage = self._estimate_slippage(
            side, quantity, order_book, venue_allocation
        )

        return ExecutionPlan(
            order_id=f"PHANTOM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            venue_allocation=venue_allocation,
            expected_slippage=expected_slippage,
            urgency=urgency,
            timestamp=datetime.utcnow()
        )

    def _optimize_venue_allocation(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_book: Dict,
        urgency: str
    ) -> Dict[VenueType, float]:
        """Optimize venue allocation for minimal impact"""
        book_imbalance = order_book.get("imbalance", 0)
        spread = order_book.get("spread", 0)
        mid_price = order_book.get("mid_price", 100)

        normalized_spread = spread / mid_price if mid_price > 0 else 0.001

        if urgency == "HIGH":
            return {
                VenueType.LIT_EXCHANGE: 0.7,
                VenueType.DARK_POOL: 0.2,
                VenueType.CROSSING_NETWORK: 0.1
            }

        if urgency == "LOW":
            dark_pool_weight = 0.5 if normalized_spread > 0.0005 else 0.3
            crossing_weight = 0.3 if normalized_spread > 0.0005 else 0.2
            lit_weight = 1 - dark_pool_weight - crossing_weight
            return {
                VenueType.DARK_POOL: dark_pool_weight,
                VenueType.CROSSING_NETWORK: crossing_weight,
                VenueType.LIT_EXCHANGE: lit_weight
            }

        if side == "BUY":
            if book_imbalance > 0.2:
                return {
                    VenueType.DARK_POOL: 0.4,
                    VenueType.LIT_EXCHANGE: 0.4,
                    VenueType.CROSSING_NETWORK: 0.2
                }
            else:
                return {
                    VenueType.LIT_EXCHANGE: 0.5,
                    VenueType.DARK_POOL: 0.3,
                    VenueType.CROSSING_NETWORK: 0.2
                }
        else:
            if book_imbalance < -0.2:
                return {
                    VenueType.DARK_POOL: 0.4,
                    VenueType.LIT_EXCHANGE: 0.4,
                    VenueType.CROSSING_NETWORK: 0.2
                }
            else:
                return {
                    VenueType.LIT_EXCHANGE: 0.5,
                    VenueType.DARK_POOL: 0.3,
                    VenueType.CROSSING_NETWORK: 0.2
                }

    def _estimate_slippage(
        self,
        side: str,
        quantity: float,
        order_book: Dict,
        venue_allocation: Dict[VenueType, float]
    ) -> float:
        """Estimate expected slippage"""
        mid_price = order_book.get("mid_price", 100)
        spread = order_book.get("spread", 0)
        bid_depth = order_book.get("bid_depth", 1000)
        ask_depth = order_book.get("ask_depth", 1000)

        depth = bid_depth if side == "BUY" else ask_depth
        participation_rate = quantity / depth if depth > 0 else 1

        base_slippage = spread / 2

        impact = participation_rate * 0.1

        venue_adjustment = 0
        for venue, weight in venue_allocation.items():
            venue_adjustment += weight * self.VENUE_COSTS[venue]["fee"]

        total_slippage = (base_slippage + impact + venue_adjustment) / mid_price
        return total_slippage

    def _get_routing_recommendation(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Get detailed routing recommendation"""
        recommendations = []

        if plan.venue_allocation.get(VenueType.DARK_POOL, 0) > 0.3:
            recommendations.append({
                "venue": "DARK_POOL",
                "action": "Route large block orders to minimize information leakage",
                "timing": "Use VWAP execution over 30-60 minutes"
            })

        if plan.venue_allocation.get(VenueType.LIT_EXCHANGE, 0) > 0.3:
            recommendations.append({
                "venue": "LIT_EXCHANGE",
                "action": "Use limit orders at NBB/NBO to capture spread",
                "timing": "Execute during high-volume periods (10:00-11:30 ET, 14:00-15:30 ET)"
            })

        if plan.venue_allocation.get(VenueType.CROSSING_NETWORK, 0) > 0.2:
            recommendations.append({
                "venue": "CROSSING_NETWORK",
                "action": "Submit to crossing networks for zero-market-impact execution",
                "timing": "Continuous matching available"
            })

        return {
            "total_estimated_slippage": plan.expected_slippage,
            "target_slippage": self.slippage_targets.get(plan.symbol, 0.0005),
            "within_target": plan.expected_slippage <= self.slippage_targets.get(plan.symbol, 0.0005),
            "recommendations": recommendations,
            "split_orders": plan.quantity > 1000
        }

    def record_execution(self, result: ExecutionResult):
        """Record execution result for analysis"""
        self.execution_history.append(result)

        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-500:]

        self._update_slippage_metrics()

    def _update_slippage_metrics(self):
        """Update slippage tracking metrics"""
        if not self.execution_history:
            return

        recent = self.execution_history[-100:]
        slippages = [r.slippage for r in recent]
        avg_slippage = np.mean(slippages)

        dark_pool_fills = [r for r in recent if r.venue == VenueType.DARK_POOL]
        dark_pool_rate = len(dark_pool_fills) / len(recent) if recent else 0

        self.update_metrics({
            "avg_slippage": avg_slippage,
            "dark_pool_fill_rate": dark_pool_rate,
            "execution_quality_score": max(0, 100 - avg_slippage * 10000)
        })

    def get_execution_analytics(self) -> Dict[str, Any]:
        """Get execution analytics"""
        if not self.execution_history:
            return {}

        recent = self.execution_history[-100:]
        slippages = [r.slippage for r in recent]

        by_venue = {}
        for venue in VenueType:
            venue_trades = [r for r in recent if r.venue == venue]
            if venue_trades:
                by_venue[venue.value] = {
                    "count": len(venue_trades),
                    "avg_slippage": np.mean([r.slippage for r in venue_trades]),
                    "avg_fill_time_ms": np.mean([r.fill_time_ms for r in venue_trades])
                }

        return {
            "total_executions": len(self.execution_history),
            "recent_executions": len(recent),
            "avg_slippage": np.mean(slippages),
            "max_slippage": max(slippages),
            "min_slippage": min(slippages),
            "by_venue": by_venue,
            "slippage_trend": "IMPROVING" if len(slippages) > 10 and np.mean(slippages[:5]) > np.mean(slippages[-5:]) else "STABLE"
        }

    def _empty_signal(self, reason: str) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "conviction": 0,
            "signal_type": "EXECUTION",
            "error": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
