# Quickstart Guide — Unified Market Intelligence

Get the system running in under 5 minutes.

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- Databento API key ([sign up free](https://databento.com) for $125 credits)

---

## Option 1: Docker (Recommended)

```bash
cd workspace/unified-market-intelligence

# Add your Databento API key
echo "DATABENTO_API_KEY=your_key_here" > .env

# Start everything
docker-compose up
```

- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:3000
- **Grafana:** http://localhost:3001 (admin/admin)

---

## Option 2: Manual Setup

### Backend

```bash
cd workspace/unified-market-intelligence/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure
copy .env.example .env
# Edit .env and add your DATABENTO_API_KEY

# Run
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd workspace/unified-market-intelligence/frontend

npm install
npm run dev
```

---

## First Look

Open http://localhost:3000 — you should see:

1. **Market Regime** — Current HMM-detected regime with confidence
2. **Conviction Score** — Gauge showing SKILL conviction (0-10)
3. **Gamma Exposure** — GEX bar chart with call/put breakdown
4. **Delta Exposure** — Directional bias indicator
5. **Vanna/Charm** — Second-order Greek exposures
6. **Risk Status** — Portfolio risk score and limits
7. **Live Order Book** — Real-time bid/ask depth (when connected)

---

## Without Databento (Demo Mode)

The system runs in demo mode without an API key:

- Uses synthetic market data for analytics
- All calculations work with sample data
- Dashboard shows real-time computed metrics
- No live streaming — static telemetry updates

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | System health check |
| `GET /api/skill/state` | Current SKILL output |
| `GET /api/market/telemetry` | Full telemetry snapshot |
| `GET /api/market/regime` | Current market regime |
| `GET /api/risk` | Risk metrics |
| `GET /api/agents` | Agent status |
| `GET /api/analytics/gex` | Gamma exposure data |
| `GET /api/analytics/dex` | Delta exposure data |
| `GET /api/analytics/vanna-charm` | Vanna/Charm data |
| `POST /api/orders` | Place order |
| `WS /ws/{channel}` | WebSocket stream |

---

## WebSocket Channels

Connect to `ws://localhost:8000/ws/{channel}`:

| Channel | Updates |
|---------|---------|
| `all` | Everything |
| `mbo` | Order book changes |
| `trades` | Trade prints |
| `skill` | SKILL cognitive output |
| `regime` | Regime changes |
| `risk` | Risk metric updates |
| `agents` | Agent signals |

---

## Next Steps

- Read the [full User Guide](USER_GUIDE.md) for detailed configuration
- Set up broker connections in `.env` for live trading
- Configure Grafana dashboards for monitoring
