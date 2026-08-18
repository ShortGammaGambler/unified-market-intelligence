"""
Unified Market Intelligence — Databento L3 MBO Adapter
Level 3 market-by-order data ingestion with sub-microsecond precision
Supports: NASDAQ ITCH, CME MDP 3.0, DBN encoding
"""
import asyncio
import struct
import logging
from typing import Callable, Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp
import json

logger = logging.getLogger(__name__)


@dataclass
class MBORecord:
    """Market-by-Order record"""
    ts_event: int
    ts_recv: int
    ts_in_delta: int
    sequence: int
    price: int
    size: int
    action: str
    side: str
    order_id: int
    flags: int
    ts_delta: int


@dataclass
class OrderBookState:
    """Maintains current order book state"""
    orders: Dict[int, dict] = field(default_factory=dict)
    price_levels: Dict[float, Dict[str, List[int]]] = field(default_factory=dict)
    last_update: int = 0
    sequence: int = 0

    def add_order(self, order_id: int, price: float, size: int, side: str, ts: int):
        self.orders[order_id] = {
            "price": price,
            "size": size,
            "side": side,
            "ts": ts
        }
        self._update_price_levels(order_id, price, side)
        self.last_update = ts

    def cancel_order(self, order_id: int):
        if order_id in self.orders:
            order = self.orders.pop(order_id)
            price = round(order["price"], 4)
            side = order["side"].lower()
            if price in self.price_levels and side in self.price_levels[price]:
                if order_id in self.price_levels[price][side]:
                    self.price_levels[price][side].remove(order_id)

    def _update_price_levels(self, order_id: int, price: float, side: str):
        price = round(price, 4)
        side = side.lower()
        if price not in self.price_levels:
            self.price_levels[price] = {"bid": [], "ask": []}
        if order_id not in self.price_levels[price][side]:
            self.price_levels[price][side].append(order_id)

    def get_best_bid(self) -> Optional[float]:
        bids = [p for p, levels in self.price_levels.items() if levels["bid"]]
        return max(bids) if bids else None

    def get_best_ask(self) -> Optional[float]:
        asks = [p for p, levels in self.price_levels.items() if levels["ask"]]
        return min(asks) if asks else None

    def get_spread(self) -> float:
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask - best_bid
        return 0.0

    def get_mid_price(self) -> Optional[float]:
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid + best_ask) / 2
        return None

    def get_imbalance(self) -> float:
        bid_size = sum(
            self.orders[oid]["size"]
            for price, levels in self.price_levels.items()
            for oid in levels["bid"]
            if oid in self.orders
        )
        ask_size = sum(
            self.orders[oid]["size"]
            for price, levels in self.price_levels.items()
            for oid in levels["ask"]
            if oid in self.orders
        )
        total = bid_size + ask_size
        if total == 0:
            return 0.0
        return (bid_size - ask_size) / total


class DatabentoClient:
    """High-performance L3 MBO data client"""

    API_BASE = "https://hist.databento.com/v0"
    LIVE_BASE = "wss://live.databento.com/v0"

    def __init__(self, api_key: str, dataset: str = "GLBX.MDP3"):
        self.api_key = api_key
        self.dataset = dataset
        self.on_mbo: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.on_snapshot: Optional[Callable] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.order_books: Dict[int, OrderBookState] = {}
        self.stats = {
            "messages_processed": 0,
            "orders_added": 0,
            "orders_cancelled": 0,
            "trades_matched": 0,
            "last_sequence": 0,
            "connected_at": None,
            "errors": 0
        }

    async def connect(self, symbols: List[str], on_mbo: Callable, on_trade: Callable, on_snapshot: Optional[Callable] = None):
        """Connect to Databento live feed"""
        self.on_mbo = on_mbo
        self.on_trade = on_trade
        self.on_snapshot = on_snapshot
        self.running = True

        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"}
        )

        try:
            logger.info(f"Connecting to Databento: {self.dataset}")
            self.ws = await self.session.ws_connect(
                f"{self.LIVE_BASE}/stream",
                heartbeat=30.0
            )

            subscribe_msg = {
                "dataset": self.dataset,
                "schema": "mbo",
                "symbols": symbols,
                "stype_in": "raw_symbol",
                "start": "0"
            }
            await self.ws.send_json(subscribe_msg)

            self.stats["connected_at"] = datetime.utcnow().isoformat()
            logger.info(f"Databento subscribed: {symbols}")
            await self._listen()

        except Exception as e:
            logger.error(f"Databento error: {e}")
            self.stats["errors"] += 1
            raise

    async def _listen(self):
        """Process incoming DBN-encoded messages"""
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.BINARY:
                await self._parse_dbn(msg.data)
            elif msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "error" in data:
                    logger.error(f"Databento error: {data['error']}")
                elif "info" in data:
                    logger.info(f"Databento info: {data['info']}")
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {self.ws.exception()}")
                self.stats["errors"] += 1
                break

    async def _parse_dbn(self, data: bytes):
        """Parse DBN binary format"""
        offset = 0
        while offset < len(data):
            if offset + 16 > len(data):
                break

            record_size, rtype, publisher_id, instrument_id = struct.unpack_from(
                "<HBBQ", data, offset
            )

            if rtype == 0x01:
                record = self._decode_mbo(data, offset + 16)
                await self._process_mbo(record, instrument_id)
            elif rtype == 0x02:
                trade = self._decode_trade(data, offset + 16)
                trade["instrument_id"] = instrument_id
                if self.on_trade:
                    await self.on_trade(trade)
                self.stats["trades_matched"] += 1

            offset += record_size
            self.stats["messages_processed"] += 1

    def _decode_mbo(self, data: bytes, offset: int) -> MBORecord:
        """Decode MBO record from binary"""
        ts_event, ts_recv, ts_in_delta, sequence = struct.unpack_from("<QQII", data, offset)
        price, size, action_byte, side_byte, flags = struct.unpack_from("<IIBBB", data, offset + 20)
        ts_delta = struct.unpack_from("<I", data, offset + 26)[0]
        order_id = struct.unpack_from("<Q", data, offset + 30)[0]

        action_map = {ord('A'): 'ADD', ord('C'): 'CANCEL', ord('M'): 'MODIFY', ord('T'): 'TRADE'}
        side_map = {ord('A'): 'ASK', ord('B'): 'BID', ord('N'): 'NONE'}

        return MBORecord(
            ts_event=ts_event,
            ts_recv=ts_recv,
            ts_in_delta=ts_in_delta,
            sequence=sequence,
            price=price,
            size=size,
            action=action_map.get(action_byte, 'UNKNOWN'),
            side=side_map.get(side_byte, 'UNKNOWN'),
            order_id=order_id,
            flags=flags,
            ts_delta=ts_delta
        )

    def _decode_trade(self, data: bytes, offset: int) -> dict:
        """Decode trade record"""
        ts_event, ts_recv = struct.unpack_from("<QQ", data, offset)
        price, size = struct.unpack_from("<II", data, offset + 16)
        return {
            "ts_event": ts_event,
            "price": price / 1e9,
            "size": size
        }

    async def _process_mbo(self, record: MBORecord, instrument_id: int):
        """Update order book and emit events"""
        price = record.price / 1e9

        if instrument_id not in self.order_books:
            self.order_books[instrument_id] = OrderBookState()

        book = self.order_books[instrument_id]

        if record.action == 'ADD':
            book.add_order(record.order_id, price, record.size, record.side, record.ts_event)
            self.stats["orders_added"] += 1

        elif record.action == 'CANCEL':
            book.cancel_order(record.order_id)
            self.stats["orders_cancelled"] += 1

        elif record.action == 'MODIFY':
            book.cancel_order(record.order_id)
            book.add_order(record.order_id, price, record.size, record.side, record.ts_event)

        book.sequence = record.sequence
        self.stats["last_sequence"] = record.sequence

        mid_price = book.get_mid_price()
        spread = book.get_spread()
        imbalance = book.get_imbalance()

        if self.on_mbo:
            await self.on_mbo({
                "instrument_id": instrument_id,
                "action": record.action,
                "side": record.side,
                "price": price,
                "size": record.size,
                "order_id": record.order_id,
                "ts": record.ts_event,
                "book_depth": len(book.orders),
                "spread": spread,
                "mid_price": mid_price,
                "imbalance": imbalance,
                "sequence": record.sequence
            })

        if self.on_snapshot:
            await self.on_snapshot({
                "instrument_id": instrument_id,
                "ts": record.ts_event,
                "best_bid": book.get_best_bid(),
                "best_ask": book.get_best_ask(),
                "spread": spread,
                "mid_price": mid_price,
                "imbalance": imbalance,
                "depth": len(book.orders)
            })

    async def get_historical(self, symbol: str, start: str, end: str, schema: str = "mbo") -> List[dict]:
        """Fetch historical data from Databento"""
        url = f"{self.API_BASE}/timeseries.get_range"
        params = {
            "dataset": self.dataset,
            "symbols": symbol,
            "schema": schema,
            "start": start,
            "end": end,
            "encoding": "json"
        }

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else [data]
                else:
                    logger.error(f"Historical fetch failed: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Historical fetch error: {e}")
            return []

    async def disconnect(self):
        """Graceful shutdown"""
        self.running = False
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        logger.info(f"Databento stats: {self.stats}")
        logger.info("Databento disconnected")
