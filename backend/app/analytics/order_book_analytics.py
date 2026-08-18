"""
Order Book Analytics — Imbalance detection, liquidity analysis, and toxicity scoring
Works with Databento MBO/MBP data
"""
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque


@dataclass
class OrderBookMetrics:
    instrument_id: int
    ts: datetime
    spread: float
    mid_price: float
    imbalance: float
    bid_depth: float
    ask_depth: float
    vpin: float
    toxicity: float
    liquidity_score: float
    large_order_ratio: float
    cancellation_rate: float
    trade_intensity: float


class OrderBookAnalytics:
    """Real-time order book analytics from Databento MBO feed"""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.trade_history: Dict[int, deque] = {}
        self.cancel_history: Dict[int, deque] = {}
        self.order_history: Dict[int, deque] = {}
        self.vpin_buckets: Dict[int, List] = {}

    def update(
        self,
        instrument_id: int,
        event_type: str,
        data: dict,
        order_book: dict
    ) -> Optional[OrderBookMetrics]:
        """Update analytics with new MBO event"""
        if instrument_id not in self.trade_history:
            self.trade_history[instrument_id] = deque(maxlen=self.window_size)
            self.cancel_history[instrument_id] = deque(maxlen=self.window_size)
            self.order_history[instrument_id] = deque(maxlen=self.window_size)

        if event_type == "TRADE":
            self.trade_history[instrument_id].append(data)
            self._update_vpin(instrument_id, data)
        elif event_type == "CANCEL":
            self.cancel_history[instrument_id].append(data)
        elif event_type == "ADD":
            self.order_history[instrument_id].append(data)

        return self._calculate_metrics(instrument_id, order_book)

    def _calculate_metrics(self, instrument_id: int, order_book: dict) -> OrderBookMetrics:
        """Calculate comprehensive order book metrics"""
        trades = list(self.trade_history.get(instrument_id, []))
        cancels = list(self.cancel_history.get(instrument_id, []))
        orders = list(self.order_history.get(instrument_id, []))

        spread = order_book.get("spread", 0)
        mid_price = order_book.get("mid_price", 0)
        imbalance = order_book.get("imbalance", 0)

        bid_depth = sum(
            level.get("size", 0)
            for level in order_book.get("bids", [])
        )
        ask_depth = sum(
            level.get("size", 0)
            for level in order_book.get("asks", [])
        )

        vpin = self._calculate_vpin(instrument_id)
        toxicity = self._calculate_toxicity(trades, order_book)
        liquidity_score = self._calculate_liquidity_score(spread, bid_depth, ask_depth, mid_price)
        large_order_ratio = self._calculate_large_order_ratio(trades)
        cancellation_rate = self._calculate_cancellation_rate(cancels, orders)
        trade_intensity = self._calculate_trade_intensity(trades)

        return OrderBookMetrics(
            instrument_id=instrument_id,
            ts=datetime.utcnow(),
            spread=spread,
            mid_price=mid_price,
            imbalance=imbalance,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            vpin=vpin,
            toxicity=toxicity,
            liquidity_score=liquidity_score,
            large_order_ratio=large_order_ratio,
            cancellation_rate=cancellation_rate,
            trade_intensity=trade_intensity
        )

    def _calculate_vpin(self, instrument_id: int) -> float:
        """Volume-synchronized Probability of Informed Trading"""
        trades = list(self.trade_history.get(instrument_id, []))
        if len(trades) < 10:
            return 0.0

        volume_buckets = []
        current_bucket = []
        bucket_size = np.mean([t.get("size", 0) for t in trades]) * 10

        for trade in trades:
            current_bucket.append(trade)
            bucket_volume = sum(t.get("size", 0) for t in current_bucket)
            if bucket_volume >= bucket_size:
                volume_buckets.append(current_bucket)
                current_bucket = []

        if len(volume_buckets) < 2:
            return 0.0

        buy_volume = 0
        sell_volume = 0
        for bucket in volume_buckets:
            for trade in bucket:
                if trade.get("side") == "BUY":
                    buy_volume += trade.get("size", 0)
                else:
                    sell_volume += trade.get("size", 0)

        total_volume = buy_volume + sell_volume
        if total_volume == 0:
            return 0.0

        return abs(buy_volume - sell_volume) / total_volume

    def _calculate_toxicity(self, trades: List[dict], order_book: dict) -> float:
        """Estimate order toxicity using VPIN and cancellation patterns"""
        vpin = self._calculate_vpin(0)

        trade_sizes = [t.get("size", 0) for t in trades]
        avg_size = np.mean(trade_sizes) if trade_sizes else 0
        large_trades = sum(1 for s in trade_sizes if s > avg_size * 2)
        large_ratio = large_trades / len(trade_sizes) if trade_sizes else 0

        toxicity = (vpin * 0.5 + large_ratio * 0.3 + abs(order_book.get("imbalance", 0)) * 0.2)
        return min(toxicity, 1.0)

    def _calculate_liquidity_score(self, spread: float, bid_depth: float, ask_depth: float, mid_price: float) -> float:
        """Calculate liquidity score (0-1, higher is more liquid)"""
        if mid_price == 0:
            return 0.0

        spread_score = max(0, 1 - (spread / mid_price) * 1000)
        depth_score = min(1.0, (bid_depth + ask_depth) / 10000)
        balance_score = 1 - abs(bid_depth - ask_depth) / (bid_depth + ask_depth + 1)

        return (spread_score * 0.4 + depth_score * 0.4 + balance_score * 0.2)

    def _calculate_large_order_ratio(self, trades: List[dict]) -> float:
        """Calculate ratio of large orders to total"""
        if not trades:
            return 0.0

        sizes = [t.get("size", 0) for t in trades]
        avg_size = np.mean(sizes)
        threshold = avg_size * 2

        large_orders = sum(1 for s in sizes if s > threshold)
        return large_orders / len(sizes)

    def _calculate_cancellation_rate(self, cancels: List[dict], orders: List[dict]) -> float:
        """Calculate order cancellation rate"""
        total_orders = len(orders) + len(cancels)
        if total_orders == 0:
            return 0.0
        return len(cancels) / total_orders

    def _calculate_trade_intensity(self, trades: List[dict]) -> float:
        """Calculate trade intensity (trades per second)"""
        if len(trades) < 2:
            return 0.0

        timestamps = [t.get("ts_event", 0) for t in trades]
        time_span = (max(timestamps) - min(timestamps)) / 1e9  # Convert ns to seconds

        if time_span == 0:
            return 0.0

        return len(trades) / time_span

    def _update_vpin(self, instrument_id: int, trade: dict):
        """Update VPIN buckets for real-time calculation"""
        if instrument_id not in self.vpin_buckets:
            self.vpin_buckets[instrument_id] = []

        self.vpin_buckets[instrument_id].append(trade)

        if len(self.vpin_buckets[instrument_id]) > 100:
            self.vpin_buckets[instrument_id].pop(0)

    def get_market_quality_score(self, metrics: OrderBookMetrics) -> dict:
        """Assess overall market quality"""
        score = 0
        factors = {}

        if metrics.spread < metrics.mid_price * 0.0001:
            score += 25
            factors["spread"] = "EXCELLENT"
        elif metrics.spread < metrics.mid_price * 0.0005:
            score += 20
            factors["spread"] = "GOOD"
        elif metrics.spread < metrics.mid_price * 0.001:
            score += 15
            factors["spread"] = "FAIR"
        else:
            score += 5
            factors["spread"] = "POOR"

        if metrics.liquidity_score > 0.8:
            score += 25
            factors["liquidity"] = "HIGH"
        elif metrics.liquidity_score > 0.5:
            score += 15
            factors["liquidity"] = "MODERATE"
        else:
            score += 5
            factors["liquidity"] = "LOW"

        if metrics.toxicity < 0.2:
            score += 25
            factors["toxicity"] = "LOW"
        elif metrics.toxicity < 0.5:
            score += 15
            factors["toxicity"] = "MODERATE"
        else:
            score += 5
            factors["toxicity"] = "HIGH"

        if metrics.cancellation_rate < 0.3:
            score += 25
            factors["cancellation"] = "STABLE"
        elif metrics.cancellation_rate < 0.6:
            score += 15
            factors["cancellation"] = "MODERATE"
        else:
            score += 5
            factors["cancellation"] = "UNSTABLE"

        return {
            "overall_score": score,
            "rating": "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D",
            "factors": factors
        }
