# User Guide — Unified Market Intelligence

Complete guide to operating the AXIOM Core Engine.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Data Sources](#data-sources)
5. [Analytics Engine](#analytics-engine)
6. [SKILL Cognitive Loop](#skill-cognitive-loop)
7. [Multi-Agent System](#multi-agent-system)
8. [Execution Layer](#execution-layer)
9. [Risk Management](#risk-management)
10. [Dashboard](#dashboard)
11. [API Reference](#api-reference)
12. [Troubleshooting](#troubleshooting)

---

## System Overview

Unified Market Intelligence is a real-time market microstructure analysis platform that combines:

- **Databento** institutional-grade market data (MBO/MBP)
- **Quantitative analytics** (GEX, DEX, Vanna/Charm, Greeks)
- **AI-driven regime detection** via Hidden Markov Models
- **Multi-agent coordination** for research, sentiment, and execution
- **Smart order routing** across dark pools, lit exchanges, and crossing networks

The system processes data in four layers:

```
Ingestion → Analytics → Cognitive SKILL → Execution
```

---

## Architecture

### Components

| Component | Purpose |
|-----------|---------|
| **DatabentoClient** | WebSocket/REST connection to Databento feeds |
| **DataManager** | Redis caching, data access abstraction |
| **Analytics Engine** | GEX, DEX, Vanna/Charm, Greeks, Vol Surface |
| **RegimeDetector** | HMM-based market regime classification |
| **SKILLCognitiveLoop** | Synthesizes all data into actionable signals |
| **FordgeAgent** | Quantitative research and backtesting |
| **AtlasAgent** | News sentiment and macro analysis |
| **PhantomAgent** | Execution quality and slippage management |
| **RiskManager** | Portfolio risk monitoring and circuit breakers |
| **SmartOrderRouter** | Algorithmic order routing (VWAP/TWAP/IS/POV) |
| **BrokerManager** | Multi-broker execution (Alpaca/IBKR/Tradier) |

### Data Flow

1. **Databento** streams MBO (L3) and MBP (L2) data via WebSocket
2. **DataManager** caches in Redis and distributes to consumers
3. **Analytics Engine** computes GEX/DEX/Vanna/Charm in real-time
4. **RegimeDetector** classifies market state using HMM
5. **Agents** process data independently and emit signals
6. **SKILLCognitiveLoop** combines all inputs into conviction score
7. **StrategyEngine** generates trading signals
8. **SmartOrderRouter** splits orders across venues
9. **RiskManager** validates orders against limits
10. **BrokerManager** executes through connected brokers

---

## Configuration

### Environment Variables

Create `.env` in the backend directory:

```bash
# Required: Databento API key
DATABENTO_API_KEY=your_api_key_here

# Data source
DATABENTO_DATASET=GLBX.MDP3

# Cache
REDIS_URL=redis://localhost:6379

# Database
DATABASE_URL=postgresql+asyncpg://axiom:axiom@localhost:5432/axiom

# Risk Parameters
MAX_DRAWDOWN_LIMIT=0.15      # 15% max drawdown
MAX_POSITION_SIZE=0.25        # 25% max per position
MAX_LEVERAGE=2.0              # 2x max leverage
AUTO_HALT_ENABLED=true        # Auto-halt on limit breach

# Logging
LOG_LEVEL=INFO
```

### Risk Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_DRAWDOWN_LIMIT` | 0.15 | Maximum portfolio drawdown before halt |
| `MAX_POSITION_SIZE` | 0.25 | Maximum allocation to single position |
| `MAX_LEVERAGE` | 2.0 | Maximum gross exposure |
| `AUTO_HALT_ENABLED` | true | Automatically halt trading on breach |

---

## Data Sources

### Databento Integration

The system uses Databento as the primary data source:

**Supported Datasets:**

| Dataset | Assets | Schema | Use Case |
|---------|--------|--------|----------|
| `GLBX.MDP3` | Futures, Options | MBO, MBP-10 | ES, NQ, RTY |
| `XNAS.ITCH` | Equities | MBO | NASDAQ L3 |
| `XNYS.ITCH` | Equities | MBO | NYSE L3 |
| `OPRA.QT` | Options | MBP-1, Trades | Equity options |

**Data Schemas:**

- **MBO (Market-by-Order):** Full L3 order book with individual order tracking
- **MBP-10 (Market-by-Price):** L2 top 10 price levels
- **MBP-1:** Top of book only
- **Trades:** Individual trade prints
- **OHLCV:** Candlestick bars

**Connection:**

```python
# Live WebSocket
client = DatabentoClient(api_key="YOUR_KEY", dataset="GLBX.MDP3")
await client.connect(
    symbols=["ES.FUT", "NQ.FUT"],
    on_mbo=handle_mbo,
    on_trade=handle_trade
)

# Historical REST
data = await client.get_historical(
    symbol="ES.FUT",
    start="2025-01-01",
    end="2026-01-01",
    schema="mbo"
)
```

### Alternative Data Sources

The system can supplement with:
- **Finnhub:** News sentiment, earnings calendars
- **Polygon.io:** Backup market data feed

---

## Analytics Engine

### Gamma Exposure (GEX)

Measures dealer gamma positioning and hedging obligations.

**Interpretation:**

| GEX Level | Market Impact | Strategy |
|-----------|---------------|----------|
| High Positive | Dealers suppress volatility | Sell premium, range-bound |
| Positive | Mild stabilizing effect | Neutral strategies |
| Negative | Dealers amplify moves | Buy premium, directional |
| High Negative | Volatility spike likely | Vol breakout, protection |

**Gamma Flip Level:**

The price where net GEX changes sign. Above flip = positive gamma (stable). Below flip = negative gamma (volatile).

### Delta Exposure (DEX)

Measures aggregate directional delta bias.

**Interpretation:**

| DEX Bias | Dealer Positioning | Expected Flow |
|----------|-------------------|---------------|
| Strong Bullish | Long delta | Buy dips |
| Bullish | Mild long | Supportive |
| Neutral | Balanced | No bias |
| Bearish | Mild short | Resistance |
| Strong Bearish | Short delta | Sell rallies |

### Vanna/Charm

**Vanna:** Sensitivity of delta to IV changes (∂Δ/∂σ)
- Negative Vanna: IV drops force selling (bearish flow)
- Positive Vanna: IV drops force buying (bullish flow)

**Charm:** Delta decay over time (∂Δ/∂t)
- Positive Charm: Delta decays toward negative (bearish)
- Negative Charm: Delta decays toward positive (bullish)

### Greeks Calculator

Full Black-Scholes Greeks: Delta, Gamma, Vega, Theta, Volga, Vanna, Charm, price.

### Order Book Analytics

- **VPIN:** Volume-synchronized Probability of Informed Trading
- **Toxicity Score:** Estimates order flow toxicity
- **Imbalance:** Bid/ask size ratio
- **Liquidity Score:** Composite of spread, depth, and balance
- **Cancellation Rate:** Order cancel frequency

---

## SKILL Cognitive Loop

The Strategic Knowledge Integration and Logic Layer synthesizes all data streams.

### Inputs

**Quantitative:**
- Real-time price signals (Databento)
- GEX/DEX/Vanna/Charm calculations
- Order book metrics
- Technical indicators

**Qualitative:**
- News sentiment (FinBERT)
- Macro data (Fed, GDP, CPI)
- Agent signals (Fordge, Atlas, Phantom)

### Output

```json
{
  "conviction_score": 8.7,
  "market_regime": "VOLATILE_BREAKOUT",
  "regime_confidence": 0.87,
  "adaptation_strategy": "DYNAMIC_HEDGING_ON",
  "gex": { "total_gex": 1234567, "net_gex": -500000 },
  "dex": { "directional_bias": "BEARISH" },
  "vanna_charm": { "vanna_exposure": "NEGATIVE" },
  "risk_metrics": { "score": 45, "level": "MODERATE" }
}
```

### Regime Classification

| Regime | Description | Strategy |
|--------|-------------|----------|
| LOW_VOL_TREND | Low volatility, trending | Trend following |
| HIGH_VOL_TREND | High volatility, trending | Momentum with hedge |
| LOW_VOL_RANGE | Low volatility, ranging | Mean reversion |
| HIGH_VOL_RANGE | High volatility, ranging | Strangle selling |
| VOLATILE_BREAKOUT | Volatility expansion | Breakout trading |
| CRISIS | Extreme stress | Defensive hedging |

---

## Multi-Agent System

### Fordge — Research & Backtesting

**Role:** Strategy validation using historical Databento data.

**Capabilities:**
- Walk-forward optimization
- Monte Carlo simulation
- Slippage and transaction cost analysis
- Out-of-sample validation

**Output:**
- Sharpe ratio, max drawdown, profit factor
- Win rate, Calmar ratio
- Strategy recommendation

### Atlas — Sentiment & News

**Role:** Ingests and synthesizes qualitative data.

**Capabilities:**
- FinBERT sentiment scoring
- Event impact classification
- Cross-market correlation analysis
- Regime-aware positioning recommendations

**Output:**
- Overall sentiment (-1 to 1)
- Topic-level sentiment trends
- Macro signal assessment

### Phantom — Execution

**Role:** Manages order routing and execution quality.

**Capabilities:**
- Smart Order Routing (SOR)
- VWAP/TWAP/IS/POV algorithms
- Real-time slippage monitoring
- Dark pool vs lit venue selection

**Output:**
- Venue allocation plan
- Expected slippage estimate
- Execution quality score

---

## Execution Layer

### Smart Order Router

Splits orders across venues to minimize impact:

**Strategies:**

| Strategy | Description | Best For |
|----------|-------------|----------|
| VWAP | Follows historical volume profile | Large orders, low urgency |
| TWAP | Equal slices over time | Medium orders |
| IS (Implementation Shortfall) | Front-loads aggressive fills | Urgent orders |
| POV (Percentage of Volume) | Matches market volume | Stealth execution |

**Venues:**

| Venue Type | Fee | Rebate | Info Leakage |
|------------|-----|--------|--------------|
| Dark Pool | 0.01¢/share | 0.03¢/share | Low |
| Lit Exchange | 0.03¢/share | 0.02¢/share | High |
| Crossing Network | 0.005¢/share | 0.04¢/share | Minimal |

### Broker Integrations

**Alpaca:** Zero-commission retail execution, fractional shares
**IBKR:** Professional institutional execution via TWS/Gateway
**Tradier:** Equity & Options APIs, sandbox testing

---

## Risk Management

### Limits

| Limit | Default | Action |
|-------|---------|--------|
| Max Drawdown | 15% | Halt trading |
| Max Position | 25% | Reject order |
| Max Leverage | 2x | Reject order |
| Daily Loss | 5% | Halt trading |
| VaR Limit | 2% | Alert |
| Stop Loss | 3% per position | Auto-close |

### Circuit Breakers

- **Hard Halt:** Breach of max drawdown → all positions closed
- **Soft Halt:** Breach of daily loss → new orders rejected
- **Auto-Stop:** Position-level stop loss triggered

### Monitoring

Risk metrics update every 5 seconds:
- Portfolio value and PnL
- Current and max drawdown
- VaR (95% confidence)
- Sharpe ratio
- Greeks exposure
- Violations list

---

## Dashboard

### Access

- **Frontend:** http://localhost:3000
- **API:** http://localhost:8000
- **Grafana:** http://localhost:3001

### Panels

1. **Market Regime** — Current regime with confidence indicator
2. **Conviction Score** — Circular gauge (0-10)
3. **Gamma Exposure** — GEX bar with call/put breakdown
4. **Delta Exposure** — Directional bias
5. **Vanna/Charm** — Second-order Greek exposures
6. **Risk Status** — Risk score bar and level
7. **Live Order Book** — Real-time bid/ask depth

### WebSocket Streams

Connect to `ws://localhost:8000/ws/{channel}` for real-time updates.

---

## API Reference

### Health Check

```
GET /api/health
Response: { "status": "healthy", "timestamp": "..." }
```

### SKILL State

```
GET /api/skill/state
Response: { "conviction_score": 8.7, "market_regime": "...", ... }
```

### Telemetry

```
GET /api/market/telemetry
Response: Full telemetry snapshot with all metrics
```

### Place Order

```
POST /api/orders
Body: {
  "symbol": "SPY",
  "side": "BUY",
  "quantity": 100,
  "order_type": "MARKET"
}
Response: { "order_id": "...", "status": "SUBMITTED", ... }
```

### Cancel Order

```
DELETE /api/orders/{order_id}
Response: { "status": "cancelled", "order_id": "..." }
```

---

## Troubleshooting

### Common Issues

**Databento connection fails:**
- Verify API key in `.env`
- Check if dataset is available for your plan
- Ensure network allows WebSocket connections

**Redis connection error:**
- System runs without Redis (in-memory cache)
- For production, ensure Redis is running

**Frontend shows "CONNECTING":**
- Backend must be running on port 8000
- Check CORS settings if deploying separately

**No data in dashboard:**
- Without Databento key, system uses demo data
- Add API key for live streaming

### Logs

Backend logs are written to stdout. Set `LOG_LEVEL=DEBUG` for verbose output.

### Performance

- Backend handles ~10,000 MBO messages/second
- Redis provides sub-millisecond cache reads
- WebSocket broadcasts to unlimited subscribers
- HMM regime detection runs every 5 seconds
