"""
WebSocket Manager — Real-time streaming of market data and SKILL output
"""
import asyncio
import json
from typing import Dict, Set, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time streaming"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def connect(self, websocket: WebSocket, channel: str):
        """Accept and register WebSocket connection"""
        await websocket.accept()

        if channel not in self.active_connections:
            self.active_connections[channel] = set()

        self.active_connections[channel].add(websocket)
        logger.info(f"Client connected to {channel}")

        try:
            while True:
                data = await websocket.receive_text()
                await self._handle_message(websocket, channel, data)
        except WebSocketDisconnect:
            self.active_connections[channel].discard(websocket)
            logger.info(f"Client disconnected from {channel}")

    async def _handle_message(self, websocket: WebSocket, channel: str, data: str):
        """Handle incoming WebSocket message"""
        try:
            message = json.loads(data)
            msg_type = message.get("type", "")

            if msg_type == "subscribe":
                new_channel = message.get("channel", "")
                if new_channel and new_channel != channel:
                    self.active_connections[channel].discard(websocket)
                    if new_channel not in self.active_connections:
                        self.active_connections[new_channel] = set()
                    self.active_connections[new_channel].add(websocket)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.utcnow().isoformat()})

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {data}")

    async def broadcast(self, channel: str, data: Dict[str, Any]):
        """Broadcast message to all connections on a channel"""
        if channel not in self.active_connections:
            return

        disconnected = set()
        message = json.dumps(data, default=str)

        for connection in self.active_connections[channel]:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)

        for conn in disconnected:
            self.active_connections[channel].discard(conn)

    async def broadcast_mbo(self, data: Dict[str, Any]):
        """Broadcast MBO updates"""
        await self.broadcast("mbo", data)
        await self.broadcast("all", {"type": "mbo", "data": data})

    async def broadcast_trade(self, data: Dict[str, Any]):
        """Broadcast trade updates"""
        await self.broadcast("trades", data)
        await self.broadcast("all", {"type": "trade", "data": data})

    async def broadcast_skill(self, data: Dict[str, Any]):
        """Broadcast SKILL output"""
        await self.broadcast("skill", data)
        await self.broadcast("all", {"type": "skill", "data": data})

    async def broadcast_regime(self, data: Dict[str, Any]):
        """Broadcast regime changes"""
        await self.broadcast("regime", data)
        await self.broadcast("all", {"type": "regime", "data": data})

    async def broadcast_risk(self, data: Dict[str, Any]):
        """Broadcast risk updates"""
        await self.broadcast("risk", data)
        await self.broadcast("all", {"type": "risk", "data": data})

    async def broadcast_agent(self, agent_name: str, data: Dict[str, Any]):
        """Broadcast agent signal"""
        await self.broadcast("agents", {"agent": agent_name, **data})
        await self.broadcast("all", {"type": "agent", "agent": agent_name, "data": data})

    def get_connections(self) -> Dict[str, int]:
        """Get connection counts by channel"""
        return {ch: len(conns) for ch, conns in self.active_connections.items()}

    def get_total_connections(self) -> int:
        """Get total connection count"""
        return sum(len(conns) for conns in self.active_connections.values())
