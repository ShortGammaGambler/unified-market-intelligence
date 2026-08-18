"""
Unified Market Intelligence — AXIOM Core Engine
Main application entry point
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.router import router, set_system
from .api.ws import WebSocketManager
from .data.databento_client import DatabentoClient
from .data.data_manager import DataManager
from .core.skill_loop import SKILLCognitiveLoop
from .core.regime_detector import RegimeDetector
from .core.risk_manager import RiskManager, RiskLimits
from .core.strategy_engine import StrategyEngine
from .analytics.gex_calculator import GEXCalculator
from .analytics.dex_calculator import DEXCalculator
from .analytics.vanna_charm import VannaCharmCalculator
from .analytics.order_book_analytics import OrderBookAnalytics
from .agents.fordge import FordgeAgent
from .agents.atlas import AtlasAgent
from .agents.phantom import PhantomAgent
from .execution.smart_order_router import SmartOrderRouter
from .execution.broker_manager import BrokerManager

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


class UnifiedSystem:
    """Main system orchestrating all components"""

    def __init__(self):
        self.databento: Optional[DatabentoClient] = None
        self.data_manager: Optional[DataManager] = None
        self.skill: Optional[SKILLCognitiveLoop] = None
        self.risk_manager: Optional[RiskManager] = None
        self.strategy_engine: Optional[StrategyEngine] = None
        self.sor: Optional[SmartOrderRouter] = None
        self.broker_manager: Optional[BrokerManager] = None
        self.ws_manager: Optional[WebSocketManager] = None

        self.agents: Dict[str, Any] = {}
        self.analytics: Dict[str, Any] = {}
        self.order_book_analytics: Optional[OrderBookAnalytics] = None

        self.market_data: Dict[str, Any] = {}
        self.order_book: Dict[str, Any] = {}
        self.positions: Dict[str, Any] = {}
        self.portfolio_value: float = 100000
        self.risk_metrics: Dict[str, Any] = {}

        self._running = False
        self._tasks: list = []

    async def initialize(self):
        """Initialize all system components"""
        logger.info("Initializing Unified Market Intelligence...")

        self.ws_manager = WebSocketManager()

        self.databento = DatabentoClient(
            api_key=settings.DATABENTO_API_KEY,
            dataset=settings.DATABENTO_DATASET
        )

        self.data_manager = DataManager(self.databento, settings.REDIS_URL)
        await self.data_manager.initialize()
        self.data_manager.register_callback(self._on_data_update)

        self.skill = SKILLCognitiveLoop()

        self.risk_manager = RiskManager(RiskLimits(
            max_drawdown=settings.MAX_DRAWDOWN_LIMIT,
            max_position_size=settings.MAX_POSITION_SIZE,
            max_leverage=settings.MAX_LEVERAGE
        ))

        self.strategy_engine = StrategyEngine(self.skill, self.risk_manager)

        self.sor = SmartOrderRouter()
        self.broker_manager = BrokerManager()

        self.agents = {
            "fordge": FordgeAgent(),
            "atlas": AtlasAgent(),
            "phantom": PhantomAgent()
        }

        for agent in self.agents.values():
            await agent.start()

        self.order_book_analytics = OrderBookAnalytics()
        self.analytics = {
            "gex": GEXCalculator(),
            "dex": DEXCalculator(),
            "vanna_charm": VannaCharmCalculator()
        }

        set_system(self)

        logger.info("System initialized successfully")

    async def start(self):
        """Start the system"""
        self._running = True

        if settings.DATABENTO_API_KEY:
            self._tasks.append(
                asyncio.create_task(self._run_databento_stream())
            )

        self._tasks.append(
            asyncio.create_task(self._run_analytics_loop())
        )
        self._tasks.append(
            asyncio.create_task(self._run_risk_monitoring())
        )

        logger.info("System started")

    async def _run_databento_stream(self):
        """Run Databento WebSocket stream"""
        try:
            symbols = ["ES.FUT", "NQ.FUT"]
            await self.databento.connect(
                symbols=symbols,
                on_mbo=self.data_manager.on_mbo_update,
                on_trade=self.data_manager.on_trade
            )
        except Exception as e:
            logger.error(f"Databento stream error: {e}")

    async def _run_analytics_loop(self):
        """Run analytics computation loop"""
        while self._running:
            try:
                if self.order_book:
                    for name, agent in self.agents.items():
                        if agent.state.status == "ACTIVE":
                            signal = await agent.process({
                                "market_data": self.market_data,
                                "order_book": self.order_book,
                                "positions": self.positions
                            })
                            await self.ws_manager.broadcast_agent(name, signal)

                skill_output = await self.skill.process(
                    market_data=self.market_data,
                    options_data={},
                    agent_signals={
                        name: {"conviction": 5}
                        for name in self.agents
                    }
                )

                await self.ws_manager.broadcast_skill(skill_output)

                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Analytics loop error: {e}")
                await asyncio.sleep(5)

    async def _run_risk_monitoring(self):
        """Run risk monitoring loop"""
        while self._running:
            try:
                risk = self.risk_manager.update_portfolio(
                    self.portfolio_value,
                    self.positions,
                    {}
                )
                self.risk_metrics = risk.__dict__
                await self.ws_manager.broadcast_risk(self.risk_metrics)

                should_halt, reason = self.risk_manager.should_halt()
                if should_halt:
                    logger.warning(f"Trading halted: {reason}")
                    await self.ws_manager.broadcast("alerts", {
                        "type": "HALT",
                        "reason": reason,
                        "ts": datetime.utcnow().isoformat()
                    })

                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Risk monitoring error: {e}")
                await asyncio.sleep(10)

    async def _on_data_update(self, event_type: str, data: dict):
        """Handle data updates"""
        if event_type == "mbo":
            await self.ws_manager.broadcast_mbo(data)
            self.order_book = data
        elif event_type == "trade":
            await self.ws_manager.broadcast_trade(data)

    async def shutdown(self):
        """Shutdown the system"""
        self._running = False

        for task in self._tasks:
            task.cancel()

        for agent in self.agents.values():
            await agent.stop()

        if self.data_manager:
            await self.data_manager.shutdown()

        logger.info("System shutdown complete")


system = UnifiedSystem()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await system.initialize()
    await system.start()
    yield
    await system.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    await system.ws_manager.connect(websocket, channel)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "health": "/api/health",
            "skill": "/api/skill/state",
            "telemetry": "/api/market/telemetry",
            "websocket": "/ws/{channel}"
        }
    }
