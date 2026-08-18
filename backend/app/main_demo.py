"""
Unified Market Intelligence — Demo Server
Simplified version for preview without Databento connection
"""
import asyncio
import json
import logging
import numpy as np
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.analytics.greeks import GreeksCalculator
from app.analytics.gex_calculator import GEXCalculator, OptionData
from app.analytics.dex_calculator import DEXCalculator, OptionPosition
from app.analytics.vanna_charm import VannaCharmCalculator, VannaCharmPosition

ws_clients = set()
demo_state = {}


def generate_demo_data():
    """Generate realistic demo market data"""
    base_price = 5450
    strikes = np.arange(base_price - 200, base_price + 201, 5)

    options = []
    for strike in strikes:
        dist = abs(strike - base_price)
        iv = 0.15 + (dist / base_price) * 0.5 + np.random.normal(0, 0.02)
        call_oi = int(np.random.lognormal(8, 1) * max(0.5, 1 - dist / 400))
        put_oi = int(np.random.lognormal(8, 1) * max(0.5, 1 - dist / 400))

        options.append(OptionData(
            strike=float(strike),
            expiry=0.02,
            iv=max(0.1, iv),
            call_oi=call_oi,
            put_oi=put_oi,
            call_volume=int(call_oi * np.random.uniform(0.1, 0.3)),
            put_volume=int(put_oi * np.random.uniform(0.1, 0.3)),
            underlying_price=float(base_price)
        ))

    gex_calc = GEXCalculator()
    dex_calc = DEXCalculator()
    vc_calc = VannaCharmCalculator()

    gex = gex_calc.calculate_total_gex(options, "SPX")
    dex = dex_calc.calculate_total_dex(
        [OptionPosition(
            strike=o.strike, expiry=o.expiry, iv=o.iv,
            call_oi=o.call_oi, put_oi=o.put_oi,
            call_volume=o.call_volume, put_volume=o.put_volume,
            underlying_price=o.underlying_price
        ) for o in options],
        "SPX"
    )
    vc = vc_calc.calculate_total(
        [VannaCharmPosition(
            strike=o.strike, expiry=o.expiry, iv=o.iv,
            call_oi=o.call_oi, put_oi=o.put_oi,
            underlying_price=o.underlying_price
        ) for o in options],
        "SPX"
    )

    regimes = ["LOW_VOL_TREND", "LOW_VOL_RANGE", "HIGH_VOL_TREND", "VOLATILE_BREAKOUT"]
    regime = np.random.choice(regimes, p=[0.4, 0.3, 0.2, 0.1])
    conviction = np.random.uniform(5.5, 9.2)

    strategies = {
        "LOW_VOL_TREND": "TREND_FOLLOWING",
        "LOW_VOL_RANGE": "MEAN_REVERSION",
        "HIGH_VOL_TREND": "MOMENTUM_WITH_HEDGE",
        "VOLATILE_BREAKOUT": "DYNAMIC_HEDGING_ON"
    }

    risk_score = np.random.uniform(25, 65)

    return {
        "ts": datetime.utcnow().isoformat(),
        "conviction_score": round(conviction, 1),
        "market_regime": regime,
        "regime_confidence": round(np.random.uniform(0.7, 0.95), 2),
        "regime_duration": int(np.random.randint(1, 8)),
        "adaptation_strategy": strategies.get(regime, "NEUTRAL"),
        "gex": {
            "total_gex": round(gex.total_gex, 2),
            "call_gex": round(gex.call_gex, 2),
            "put_gex": round(gex.put_gex, 2),
            "gamma_flip_level": round(gex.gamma_flip_level, 2),
            "net_gex": round(gex.net_gex, 2),
            "normalized_gex": round(gex.normalized_gex, 6),
            "regime": gex_calc.get_gex_regime(gex)
        },
        "dex": {
            "total_dex": round(dex.total_dex, 2),
            "call_dex": round(dex.call_dex, 2),
            "put_dex": round(dex.put_dex, 2),
            "net_dex": round(dex.net_dex, 2),
            "directional_bias": dex.directional_bias,
            "weighted_delta": round(dex.weighted_delta, 4)
        },
        "vanna_charm": {
            "total_vanna": round(vc.total_vanna, 2),
            "call_vanna": round(vc.call_vanna, 2),
            "put_vanna": round(vc.put_vanna, 2),
            "total_charm": round(vc.total_charm, 2),
            "call_charm": round(vc.call_charm, 2),
            "put_charm": round(vc.put_charm, 2),
            "vanna_exposure": vc.vanna_exposure,
            "charm_exposure": vc.charm_exposure
        },
        "risk_metrics": {
            "score": round(risk_score, 1),
            "level": "CRITICAL" if risk_score >= 80 else "HIGH" if risk_score >= 60 else "MODERATE" if risk_score >= 40 else "LOW",
            "hedging_recommended": risk_score > 55,
            "position_reduction_recommended": risk_score > 70
        },
        "order_book": {
            "best_bid": base_price - 0.5,
            "best_ask": base_price + 0.5,
            "spread": 1.0,
            "mid_price": base_price,
            "imbalance": round(np.random.uniform(-0.3, 0.3), 3),
            "bid_depth": int(np.random.uniform(500, 2000)),
            "ask_depth": int(np.random.uniform(500, 2000))
        },
        "agents": {
            "fordge": {
                "name": "Fordge",
                "role": "Research & Backtesting",
                "status": "ACTIVE",
                "conviction": round(np.random.uniform(5, 9), 1),
                "signal": "STRONG_BUY" if conviction > 7 else "BUY" if conviction > 5 else "HOLD"
            },
            "atlas": {
                "name": "Atlas",
                "role": "Sentiment & News",
                "status": "ACTIVE",
                "conviction": round(np.random.uniform(4, 8), 1),
                "sentiment": round(np.random.uniform(-0.3, 0.5), 2)
            },
            "phantom": {
                "name": "Phantom",
                "role": "Execution",
                "status": "ACTIVE",
                "execution_quality": round(np.random.uniform(85, 98), 1),
                "avg_slippage": round(np.random.uniform(0.0001, 0.0005), 6)
            }
        }
    }


async def broadcast_loop():
    """Broadcast demo data every 2 seconds"""
    while True:
        try:
            demo_state.update(generate_demo_data())
            message = json.dumps({"type": "skill", "data": demo_state}, default=str)

            disconnected = set()
            for client in ws_clients:
                try:
                    await client.send_text(message)
                except Exception:
                    disconnected.add(client)

            ws_clients.difference_update(disconnected)
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(broadcast_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Unified Market Intelligence",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "Unified Market Intelligence",
        "version": "1.0.0",
        "status": "running (demo mode)",
        "endpoints": {
            "health": "/api/health",
            "skill": "/api/skill/state",
            "telemetry": "/api/market/telemetry",
            "websocket": "/ws/all"
        }
    }


@app.get("/api/health")
async def health():
    return {"status": "healthy", "mode": "demo", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/skill/state")
async def skill_state():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return demo_state


@app.get("/api/market/telemetry")
async def telemetry():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return demo_state


@app.get("/api/market/regime")
async def regime():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return {
        "regime": demo_state.get("market_regime"),
        "confidence": demo_state.get("regime_confidence"),
        "duration": demo_state.get("regime_duration")
    }


@app.get("/api/risk")
async def risk():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return demo_state.get("risk_metrics", {})


@app.get("/api/agents")
async def agents():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return demo_state.get("agents", {})


@app.get("/api/analytics/gex")
async def gex():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return demo_state.get("gex", {})


@app.get("/api/analytics/dex")
async def dex():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return demo_state.get("dex", {})


@app.get("/api/analytics/vanna-charm")
async def vanna_charm():
    if not demo_state:
        demo_state.update(generate_demo_data())
    return demo_state.get("vanna_charm", {})


@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    await websocket.accept()
    ws_clients.add(websocket)
    logger.info(f"Client connected to ws/{channel}")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_clients.discard(websocket)
    except Exception:
        ws_clients.discard(websocket)
