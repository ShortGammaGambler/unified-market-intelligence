"""
Broker Manager — Multi-broker execution interface
Supports Alpaca, Interactive Brokers, and Tradier
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BrokerType(str, Enum):
    ALPACA = "ALPACA"
    IBKR = "IBKR"
    TRADIER = "TRADIER"


@dataclass
class BrokerConfig:
    broker_type: BrokerType
    api_key: str
    api_secret: str
    base_url: str
    paper_trading: bool = True


@dataclass
class BrokerOrder:
    order_id: str
    broker: BrokerType
    symbol: str
    side: str
    quantity: float
    order_type: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    status: str
    filled_quantity: float
    avg_fill_price: float
    created_at: datetime
    updated_at: datetime


class BrokerManager:
    """Manages connections to multiple brokers"""

    def __init__(self):
        self.brokers: Dict[BrokerType, Any] = {}
        self.orders: Dict[str, BrokerOrder] = {}
        self.positions: Dict[str, Dict] = {}

    async def connect_broker(self, config: BrokerConfig) -> bool:
        """Connect to a broker"""
        try:
            if config.broker_type == BrokerType.ALPACA:
                self.brokers[config.broker_type] = await self._connect_alpaca(config)
            elif config.broker_type == BrokerType.IBKR:
                self.brokers[config.broker_type] = await self._connect_ibkr(config)
            elif config.broker_type == BrokerType.TRADIER:
                self.brokers[config.broker_type] = await self._connect_tradier(config)

            logger.info(f"Connected to {config.broker_type.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {config.broker_type.value}: {e}")
            return False

    async def _connect_alpaca(self, config: BrokerConfig):
        """Connect to Alpaca"""
        try:
            from alpaca.trading.client import TradingClient
            client = TradingClient(config.api_key, config.api_secret, paper=config.paper_trading)
            return {"client": client, "config": config}
        except ImportError:
            logger.warning("Alpaca SDK not installed")
            return None

    async def _connect_ibkr(self, config: BrokerConfig):
        """Connect to Interactive Brokers"""
        try:
            from ib_insync import IB
            ib = IB()
            await ib.connectAsync(config.base_url, 7497, clientId=1)
            return {"client": ib, "config": config}
        except ImportError:
            logger.warning("ib_insync not installed")
            return None

    async def _connect_tradier(self, config: BrokerConfig):
        """Connect to Tradier"""
        import aiohttp
        session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {config.api_key}"}
        )
        return {"client": session, "config": config}

    async def place_order(
        self,
        broker_type: BrokerType,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Optional[BrokerOrder]:
        """Place order through specified broker"""
        broker = self.brokers.get(broker_type)
        if not broker:
            logger.error(f"Broker {broker_type.value} not connected")
            return None

        try:
            if broker_type == BrokerType.ALPACA:
                return await self._place_alpaca_order(
                    broker, symbol, side, quantity, order_type, limit_price, stop_price
                )
            elif broker_type == BrokerType.IBKR:
                return await self._place_ibkr_order(
                    broker, symbol, side, quantity, order_type, limit_price, stop_price
                )
            elif broker_type == BrokerType.TRADIER:
                return await self._place_tradier_order(
                    broker, symbol, side, quantity, order_type, limit_price, stop_price
                )
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return None

    async def _place_alpaca_order(
        self, broker: dict, symbol: str, side: str,
        quantity: float, order_type: str, limit_price: Optional[float], stop_price: Optional[float]
    ) -> BrokerOrder:
        """Place order through Alpaca"""
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest

        client = broker["client"]

        if order_type == "MARKET":
            request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side.lower(),
                time_in_force="day"
            )
        elif order_type == "LIMIT":
            request = LimitOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side.lower(),
                limit_price=limit_price,
                time_in_force="day"
            )
        elif order_type == "STOP":
            request = StopOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side.lower(),
                stop_price=stop_price,
                time_in_force="day"
            )
        else:
            request = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side.lower(),
                time_in_force="day"
            )

        order = await client.submit_order_async(request)

        broker_order = BrokerOrder(
            order_id=str(order.id),
            broker=BrokerType.ALPACA,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            status=order.status.value,
            filled_quantity=float(order.filled_qty) if order.filled_qty else 0,
            avg_fill_price=float(order.filled_avg_price) if order.filled_avg_price else 0,
            created_at=order.created_at,
            updated_at=order.updated_at
        )

        self.orders[broker_order.order_id] = broker_order
        return broker_order

    async def _place_ibkr_order(
        self, broker: dict, symbol: str, side: str,
        quantity: float, order_type: str, limit_price: Optional[float], stop_price: Optional[float]
    ) -> BrokerOrder:
        """Place order through Interactive Brokers"""
        from ib_insync import Stock, MarketOrder, LimitOrder, StopOrder

        ib = broker["client"]
        contract = Stock(symbol, "SMART", "USD")

        if order_type == "MARKET":
            order = MarketOrder(side, quantity)
        elif order_type == "LIMIT":
            order = LimitOrder(side, quantity, limit_price)
        elif order_type == "STOP":
            order = StopOrder(side, quantity, stop_price)
        else:
            order = MarketOrder(side, quantity)

        trade = ib.placeOrder(contract, order)

        broker_order = BrokerOrder(
            order_id=str(trade.order.orderId),
            broker=BrokerType.IBKR,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            status="SUBMITTED",
            filled_quantity=0,
            avg_fill_price=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.orders[broker_order.order_id] = broker_order
        return broker_order

    async def _place_tradier_order(
        self, broker: dict, symbol: str, side: str,
        quantity: float, order_type: str, limit_price: Optional[float], stop_price: Optional[float]
    ) -> BrokerOrder:
        """Place order through Tradier"""
        session = broker["client"]
        config = broker["config"]

        url = f"{config.base_url}/v1/accounts/{config.api_key}/orders"

        data = {
            "symbol": symbol,
            "side": side.lower(),
            "quantity": quantity,
            "type": order_type.lower(),
            "duration": "day"
        }

        if limit_price:
            data["price"] = limit_price
        if stop_price:
            data["stop"] = stop_price

        async with session.post(url, json=data) as resp:
            result = await resp.json()

        broker_order = BrokerOrder(
            order_id=str(result.get("order", {}).get("id", "")),
            broker=BrokerType.TRADIER,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            status="SUBMITTED",
            filled_quantity=0,
            avg_fill_price=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.orders[broker_order.order_id] = broker_order
        return broker_order

    async def cancel_order(self, broker_type: BrokerType, order_id: str) -> bool:
        """Cancel an order"""
        broker = self.brokers.get(broker_type)
        if not broker:
            return False

        try:
            if broker_type == BrokerType.ALPACA:
                client = broker["client"]
                await client.cancel_order_async(order_id)
            elif broker_type == BrokerType.IBKR:
                ib = broker["client"]
                for trade in ib.openTrades():
                    if str(trade.order.orderId) == order_id:
                        ib.cancelOrder(trade.order)
                        break

            if order_id in self.orders:
                self.orders[order_id].status = "CANCELLED"

            return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False

    async def get_positions(self, broker_type: BrokerType) -> Dict[str, Any]:
        """Get current positions"""
        broker = self.brokers.get(broker_type)
        if not broker:
            return {}

        try:
            if broker_type == BrokerType.ALPACA:
                client = broker["client"]
                positions = await client.get_all_positions_async()
                return {p.symbol: {
                    "quantity": float(p.qty),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl)
                } for p in positions}
            elif broker_type == BrokerType.IBKR:
                ib = broker["client"]
                positions = ib.positions()
                return {p.contract.symbol: {
                    "quantity": p.position,
                    "market_value": p.position * p.avgCost,
                    "unrealized_pl": p.unrealizedPnL
                } for p in positions}
        except Exception as e:
            logger.error(f"Position fetch failed: {e}")
            return {}

    def get_all_orders(self) -> List[BrokerOrder]:
        """Get all orders"""
        return list(self.orders.values())

    def get_order(self, order_id: str) -> Optional[BrokerOrder]:
        """Get specific order"""
        return self.orders.get(order_id)
