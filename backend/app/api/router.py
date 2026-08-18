"""
API Router — FastAPI endpoints for Unified Market Intelligence
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models import (
    OrderRequest, ExecutionResult, SKILLOutput,
    MarketRegime, OrderSide
)

router = APIRouter()

_system = None


def set_system(system):
    global _system
    _system = system


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@router.get("/skill/state")
async def get_skill_state():
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.skill.get_current_state()


@router.get("/skill/history")
async def get_skill_history(limit: int = 100):
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.skill.get_history(limit)


@router.get("/agents")
async def get_agents():
    if not _system:
        raise HTTPException(503, "System not initialized")
    return {
        name: agent.get_state().__dict__
        for name, agent in _system.agents.items()
    }


@router.get("/agents/{agent_name}")
async def get_agent(agent_name: str):
    if not _system:
        raise HTTPException(503, "System not initialized")
    agent = _system.agents.get(agent_name)
    if not agent:
        raise HTTPException(404, f"Agent {agent_name} not found")
    return agent.get_state().__dict__


@router.get("/analytics/gex")
async def get_gex(symbol: str = "SPX"):
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.analytics.get("gex", {})


@router.get("/analytics/dex")
async def get_dex(symbol: str = "SPX"):
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.analytics.get("dex", {})


@router.get("/analytics/vanna-charm")
async def get_vanna_charm(symbol: str = "SPX"):
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.analytics.get("vanna_charm", {})


@router.get("/risk")
async def get_risk_metrics():
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.risk_metrics


@router.get("/risk/check")
async def check_risk(order: OrderRequest):
    if not _system:
        raise HTTPException(503, "System not initialized")
    is_valid, violations = _system.risk_manager.check_order(
        order.dict(),
        _system.positions,
        _system.portfolio_value
    )
    return {"valid": is_valid, "violations": violations}


@router.get("/execution/plan")
async def get_execution_plan(symbol: str, side: str, quantity: float):
    if not _system:
        raise HTTPException(503, "System not initialized")
    plan = _system.sor.create_routing_plan(
        symbol=symbol,
        side=side,
        quantity=quantity,
        strategy="VWAP",
        urgency="MEDIUM",
        market_data=_system.market_data,
        order_book=_system.order_book
    )
    return {
        "slices": [
            {
                "venue": s.venue,
                "quantity": s.quantity,
                "price": s.price,
                "time_slot": s.time_slot.isoformat()
            }
            for s in plan
        ],
        "cost_estimate": _system.sor.estimate_total_cost(plan, _system.order_book)
    }


@router.get("/orders")
async def get_orders():
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.broker_manager.get_all_orders()


@router.post("/orders")
async def place_order(order: OrderRequest):
    if not _system:
        raise HTTPException(503, "System not initialized")

    is_valid, violations = _system.risk_manager.check_order(
        order.dict(),
        _system.positions,
        _system.portfolio_value
    )

    if not is_valid:
        raise HTTPException(400, {"message": "Risk check failed", "violations": violations})

    result = await _system.broker_manager.place_order(
        broker_type="ALPACA",
        symbol=order.symbol,
        side=order.side.value,
        quantity=order.quantity,
        order_type=order.order_type,
        limit_price=order.limit_price
    )

    if not result:
        raise HTTPException(500, "Order placement failed")

    return result.__dict__


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    if not _system:
        raise HTTPException(503, "System not initialized")
    success = await _system.broker_manager.cancel_order("ALPACA", order_id)
    if not success:
        raise HTTPException(500, "Cancel failed")
    return {"status": "cancelled", "order_id": order_id}


@router.get("/positions")
async def get_positions():
    if not _system:
        raise HTTPException(503, "System not initialized")
    return _system.positions


@router.get("/market/regime")
async def get_regime():
    if not _system:
        raise HTTPException(503, "System not initialized")
    state = _system.skill.get_current_state()
    return {
        "regime": state.get("market_regime"),
        "confidence": state.get("regime_confidence"),
        "duration": state.get("regime_duration")
    }


@router.get("/market/telemetry")
async def get_telemetry():
    if not _system:
        raise HTTPException(503, "System not initialized")
    state = _system.skill.get_current_state()
    return {
        "regime": state.get("market_regime"),
        "conviction": state.get("conviction_score"),
        "strategy": state.get("adaptation_strategy"),
        "gex": state.get("gex"),
        "dex": state.get("dex"),
        "vanna_charm": state.get("vanna_charm"),
        "risk": state.get("risk_metrics"),
        "agents": state.get("agent_signals")
    }
