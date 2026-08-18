"""
Data Manager — Unified data access layer for Databento
Handles caching, historical data, and real-time state
"""
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
import redis.asyncio as redis

from .databento_client import DatabentoClient, OrderBookState

logger = logging.getLogger(__name__)


class DataManager:
    """Manages all data access and caching"""

    def __init__(self, databento_client: DatabentoClient, redis_url: str = "redis://localhost:6379"):
        self.databento = databento_client
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self.order_books: Dict[int, OrderBookState] = {}
        self.latest_snapshots: Dict[int, dict] = {}
        self.latest_trades: Dict[int, dict] = {}
        self._callbacks: List = []

    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, using in-memory cache")

    async def on_mbo_update(self, data: dict):
        """Handle MBO updates"""
        instrument_id = data["instrument_id"]
        self.latest_snapshots[instrument_id] = data

        if self.redis:
            try:
                key = f"mbo:{instrument_id}"
                await self.redis.setex(key, 60, json.dumps(data, default=str))
                await self.redis.publish("mbo_stream", json.dumps(data, default=str))
            except Exception as e:
                logger.error(f"Redis publish error: {e}")

        for callback in self._callbacks:
            try:
                await callback("mbo", data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def on_trade(self, data: dict):
        """Handle trade updates"""
        instrument_id = data.get("instrument_id")
        if instrument_id:
            self.latest_trades[instrument_id] = data

        if self.redis:
            try:
                await self.redis.publish("trade_stream", json.dumps(data, default=str))
            except Exception as e:
                logger.error(f"Redis publish error: {e}")

        for callback in self._callbacks:
            try:
                await callback("trade", data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def register_callback(self, callback):
        """Register a data callback"""
        self._callbacks.append(callback)

    def get_order_book(self, instrument_id: int) -> Optional[OrderBookState]:
        """Get current order book state"""
        return self.databento.order_books.get(instrument_id)

    def get_latest_snapshot(self, instrument_id: int) -> Optional[dict]:
        """Get latest order book snapshot"""
        return self.latest_snapshots.get(instrument_id)

    def get_latest_trade(self, instrument_id: int) -> Optional[dict]:
        """Get latest trade"""
        return self.latest_trades.get(instrument_id)

    async def get_historical(self, symbol: str, start: str, end: str, schema: str = "mbo") -> List[dict]:
        """Fetch historical data"""
        return await self.databento.get_historical(symbol, start, end, schema)

    async def get_cached_data(self, key: str) -> Optional[dict]:
        """Get data from cache"""
        if self.redis:
            try:
                data = await self.redis.get(key)
                return json.loads(data) if data else None
            except Exception:
                return None
        return None

    async def set_cached_data(self, key: str, data: dict, ttl: int = 300):
        """Set data in cache"""
        if self.redis:
            try:
                await self.redis.setex(key, ttl, json.dumps(data, default=str))
            except Exception as e:
                logger.error(f"Redis set error: {e}")

    def get_stats(self) -> dict:
        """Get data manager statistics"""
        return {
            "databento_stats": self.databento.stats,
            "order_books_count": len(self.order_books),
            "snapshots_count": len(self.latest_snapshots),
            "trades_count": len(self.latest_trades),
            "callbacks_count": len(self._callbacks)
        }

    async def shutdown(self):
        """Cleanup resources"""
        await self.databento.disconnect()
        if self.redis:
            await self.redis.close()
