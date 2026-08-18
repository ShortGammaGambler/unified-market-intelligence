"""
Smart Order Router — Algorithmic order routing across dark pools, lit exchanges, and crossing networks
Minimizes market impact and slippage using VWAP/TWAP algorithms
"""
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class RoutingStrategy(str, Enum):
    VWAP = "VWAP"
    TWAP = "TWAP"
    IS = "IS"  # Implementation Shortfall
    POV = "POV"  # Percentage of Volume


@dataclass
class VenueConfig:
    name: str
    venue_type: str
    fee_per_share: float
    rebate_per_share: float
    min_size: int
    max_size: int
    latency_ms: float
    fill_rate: float


@dataclass
class OrderSlice:
    venue: str
    quantity: float
    price: float
    time_slot: datetime
    expected_fill: float


class SmartOrderRouter:
    """Algorithmic smart order routing"""

    VENUES = {
        "dark_pool_1": VenueConfig("DarkPool Alpha", "DARK_POOL", 0.0001, 0.0003, 100, 100000, 0.5, 0.85),
        "dark_pool_2": VenueConfig("DarkPool Beta", "DARK_POOL", 0.00015, 0.00025, 100, 50000, 0.6, 0.80),
        "lit_nyse": VenueConfig("NYSE", "LIT_EXCHANGE", 0.0003, 0.0002, 1, 100000, 0.2, 0.95),
        "lit_nasdaq": VenueConfig("NASDAQ", "LIT_EXCHANGE", 0.00028, 0.00022, 1, 100000, 0.2, 0.95),
        "lit_arca": VenueConfig("ARCA", "LIT_EXCHANGE", 0.00025, 0.0002, 1, 50000, 0.3, 0.93),
        "crossing_1": VenueConfig("CrossNet", "CROSSING_NETWORK", 0.00005, 0.0004, 500, 200000, 1.0, 0.70),
    }

    def __init__(self):
        self.pending_orders: Dict[str, dict] = {}
        self.execution_history: List[dict] = []

    def create_routing_plan(
        self,
        symbol: str,
        side: str,
        quantity: float,
        strategy: RoutingStrategy,
        urgency: str,
        market_data: dict,
        order_book: dict
    ) -> List[OrderSlice]:
        """Create optimal routing plan"""
        if strategy == RoutingStrategy.VWAP:
            return self._vwap_routing(symbol, side, quantity, market_data, order_book)
        elif strategy == RoutingStrategy.TWAP:
            return self._twap_routing(symbol, side, quantity, market_data)
        elif strategy == RoutingStrategy.IS:
            return self._is_routing(symbol, side, quantity, market_data, order_book)
        elif strategy == RoutingStrategy.POV:
            return self._pov_routing(symbol, side, quantity, market_data, order_book)
        else:
            return self._default_routing(symbol, side, quantity, market_data)

    def _vwap_routing(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_data: dict,
        order_book: dict
    ) -> List[OrderSlice]:
        """VWAP-based routing following historical volume profile"""
        volume_profile = market_data.get("volume_profile", self._default_volume_profile())
        current_price = order_book.get("mid_price", 100)

        slices = []
        total_volume = sum(volume_profile)
        remaining = quantity

        for i, vol_pct in enumerate(volume_profile):
            slot_qty = quantity * (vol_pct / total_volume)
            if slot_qty > remaining:
                slot_qty = remaining

            if slot_qty <= 0:
                continue

            venue = self._select_venue(slot_qty, order_book, "VWAP")
            price = self._calculate_limit_price(side, current_price, order_book)

            slot_time = datetime.utcnow() + timedelta(minutes=i * 5)

            slices.append(OrderSlice(
                venue=venue,
                quantity=slot_qty,
                price=price,
                time_slot=slot_time,
                expected_fill=slot_qty * self.VENUES[venue].fill_rate
            ))

            remaining -= slot_qty

        return slices

    def _twap_routing(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_data: dict
    ) -> List[OrderSlice]:
        """Time-weighted average price routing"""
        duration_minutes = market_data.get("duration_minutes", 60)
        interval_minutes = market_data.get("interval_minutes", 5)
        current_price = market_data.get("current_price", 100)

        num_slices = duration_minutes // interval_minutes
        qty_per_slice = quantity / num_slices

        slices = []
        for i in range(num_slices):
            slot_time = datetime.utcnow() + timedelta(minutes=i * interval_minutes)
            venue = self._select_venue_simple(qty_per_slice, "TWAP")

            slices.append(OrderSlice(
                venue=venue,
                quantity=qty_per_slice,
                price=current_price,
                time_slot=slot_time,
                expected_fill=qty_per_slice * 0.95
            ))

        return slices

    def _is_routing(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_data: dict,
        order_book: dict
    ) -> List[OrderSlice]:
        """Implementation shortfall routing - front-load aggressive fills"""
        current_price = order_book.get("mid_price", 100)
        urgency_factor = 0.3

        slices = []
        remaining = quantity

        for i in range(10):
            slot_qty = remaining * urgency_factor * (0.9 ** i)
            if slot_qty < 1:
                break

            venue = self._select_venue(slot_qty, order_book, "IS")
            price = self._calculate_aggressive_price(side, current_price, order_book)

            slot_time = datetime.utcnow() + timedelta(minutes=i * 2)

            slices.append(OrderSlice(
                venue=venue,
                quantity=slot_qty,
                price=price,
                time_slot=slot_time,
                expected_fill=slot_qty * 0.98
            ))

            remaining -= slot_qty

        return slices

    def _pov_routing(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_data: dict,
        order_book: dict
    ) -> List[OrderSlice]:
        """Percentage of volume routing"""
        target_pct = market_data.get("target_pov", 0.1)
        avg_daily_volume = market_data.get("adv", 1000000)
        current_price = order_book.get("mid_price", 100)

        expected_volume = avg_daily_volume * target_pct
        duration_minutes = (quantity / expected_volume) * 390 if expected_volume > 0 else 60

        slices = []
        remaining = quantity
        interval = 5

        for i in range(int(duration_minutes / interval)):
            slot_qty = quantity * target_pct * (interval / 390)
            if slot_qty > remaining:
                slot_qty = remaining

            if slot_qty <= 0:
                break

            venue = self._select_venue(slot_qty, order_book, "POV")

            slices.append(OrderSlice(
                venue=venue,
                quantity=slot_qty,
                price=current_price,
                time_slot=datetime.utcnow() + timedelta(minutes=i * interval),
                expected_fill=slot_qty * 0.90
            ))

            remaining -= slot_qty

        return slices

    def _default_routing(
        self,
        symbol: str,
        side: str,
        quantity: float,
        market_data: dict
    ) -> List[OrderSlice]:
        """Default immediate routing"""
        current_price = market_data.get("current_price", 100)
        venue = self._select_venue_simple(quantity, "DEFAULT")

        return [OrderSlice(
            venue=venue,
            quantity=quantity,
            price=current_price,
            time_slot=datetime.utcnow(),
            expected_fill=quantity * 0.95
        )]

    def _select_venue(self, quantity: float, order_book: dict, strategy: str) -> str:
        """Select optimal venue based on order characteristics"""
        if quantity >= 5000 and strategy in ["VWAP", "IS"]:
            dark_pools = [v for v, cfg in self.VENUES.items() if cfg.venue_type == "DARK_POOL"]
            if dark_pools:
                return dark_pools[0]

        spread = order_book.get("spread", 0)
        mid_price = order_book.get("mid_price", 100)
        normalized_spread = spread / mid_price if mid_price > 0 else 0.001

        if normalized_spread > 0.001:
            crossing = [v for v, cfg in self.VENUES.items() if cfg.venue_type == "CROSSING_NETWORK"]
            if crossing:
                return crossing[0]

        lit = [v for v, cfg in self.VENUES.items() if cfg.venue_type == "LIT_EXCHANGE"]
        if lit:
            best_lit = min(lit, key=lambda v: self.VENUES[v].fee_per_share)
            return best_lit

        return "lit_nyse"

    def _select_venue_simple(self, quantity: float, strategy: str) -> str:
        """Simple venue selection"""
        if quantity >= 1000:
            return "dark_pool_1"
        return "lit_nyse"

    def _calculate_limit_price(self, side: str, current_price: float, order_book: dict) -> float:
        """Calculate limit price based on order book"""
        spread = order_book.get("spread", 0)

        if side == "BUY":
            return current_price + spread * 0.3
        else:
            return current_price - spread * 0.3

    def _calculate_aggressive_price(self, side: str, current_price: float, order_book: dict) -> float:
        """Calculate aggressive limit price for IS routing"""
        spread = order_book.get("spread", 0)

        if side == "BUY":
            return current_price + spread * 0.8
        else:
            return current_price - spread * 0.8

    def _default_volume_profile(self) -> List[float]:
        """Default U-shaped volume profile"""
        profile = [
            15, 12, 10, 8, 7, 6, 5, 4, 4, 4,
            5, 6, 7, 8, 10, 12, 15, 18, 20, 22,
            25, 28, 30, 28, 25, 22, 20, 18, 15, 12,
            10, 8, 7, 6, 5, 5, 6, 7, 8, 10,
            12, 15, 18, 22, 28, 35, 40, 45, 50, 55,
            60, 65, 70, 75, 80, 85, 90, 95, 100, 95,
            90, 85, 80, 75, 70, 65, 60, 55, 50, 45,
            40, 35, 30, 25, 20, 15, 12, 10
        ]
        return profile[:78]

    def estimate_total_cost(self, slices: List[OrderSlice], order_book: dict) -> dict:
        """Estimate total execution cost"""
        total_qty = sum(s.quantity for s in slices)
        total_fees = sum(s.quantity * self.VENUES[s.venue].fee_per_share for s in slices)
        total_rebates = sum(s.quantity * self.VENUES[s.venue].rebate_per_share for s in slices)

        mid_price = order_book.get("mid_price", 100)
        expected_avg_price = np.mean([s.price for s in slices]) if slices else mid_price

        estimated_slippage = abs(expected_avg_price - mid_price) / mid_price

        return {
            "total_quantity": total_qty,
            "estimated_avg_price": expected_avg_price,
            "total_fees": total_fees,
            "total_rebates": total_rebates,
            "net_cost": total_fees - total_rebates,
            "estimated_slippage": estimated_slippage,
            "num_slices": len(slices),
            "venues_used": list(set(s.venue for s in slices))
        }
