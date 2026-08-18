from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MarketRegime(str, Enum):
    LOW_VOL_TREND = "LOW_VOL_TREND"
    HIGH_VOL_TREND = "HIGH_VOL_TREND"
    LOW_VOL_RANGE = "LOW_VOL_RANGE"
    HIGH_VOL_RANGE = "HIGH_VOL_RANGE"
    VOLATILE_BREAKOUT = "VOLATILE_BREAKOUT"
    CRISIS = "CRISIS"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderAction(str, Enum):
    ADD = "ADD"
    CANCEL = "CANCEL"
    MODIFY = "MODIFY"
    TRADE = "TRADE"


class MBPRecord(BaseModel):
    ts_event: int
    ts_recv: int
    price: float
    size: int
    side: str
    action: str
    sequence: int
    instrument_id: int


class MBORecord(BaseModel):
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


class TradeRecord(BaseModel):
    ts_event: int
    price: float
    size: int
    instrument_id: int


class OrderBookSnapshot(BaseModel):
    instrument_id: int
    ts_event: int
    bids: List[Dict[str, float]]
    asks: List[Dict[str, float]]
    spread: float
    mid_price: float
    imbalance: float


class GEXResult(BaseModel):
    symbol: str
    ts: datetime
    total_gex: float
    call_gex: float
    put_gex: float
    gamma_flip_level: float
    net_gex: float
    normalized_gex: float


class DEXResult(BaseModel):
    symbol: str
    ts: datetime
    total_dex: float
    call_dex: float
    put_dex: float
    net_dex: float
    directional_bias: str


class VannaCharmResult(BaseModel):
    symbol: str
    ts: datetime
    vanna: float
    charm: float
    vanna_exposure: str
    charm_exposure: str


class GreeksSnapshot(BaseModel):
    symbol: str
    ts: datetime
    delta: float
    gamma: float
    vega: float
    theta: float
    volga: float


class SKILLOutput(BaseModel):
    ts: datetime
    conviction_score: float = Field(ge=0, le=10)
    market_regime: MarketRegime
    regime_confidence: float = Field(ge=0, le=1)
    adaptation_strategy: str
    gex: GEXResult
    dex: DEXResult
    vanna_charm: VannaCharmResult
    risk_metrics: Dict[str, float]
    agent_signals: Dict[str, Any]


class AgentSignal(BaseModel):
    agent_name: str
    ts: datetime
    signal_type: str
    conviction: float
    metadata: Dict[str, Any]


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: float
    order_type: str = "MARKET"
    limit_price: Optional[float] = None
    time_in_force: str = "DAY"


class ExecutionResult(BaseModel):
    order_id: str
    symbol: str
    side: OrderSide
    filled_quantity: float
    avg_price: float
    slippage: float
    venue: str
    ts: datetime
    status: str


class RiskMetrics(BaseModel):
    ts: datetime
    portfolio_value: float
    daily_pnl: float
    unrealized_pnl: float
    max_drawdown: float
    var_95: float
    sharpe_ratio: float
    exposure_by_asset: Dict[str, float]
    greeks_exposure: Dict[str, float]
