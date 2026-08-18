"""
Strategy Engine — Generates trading signals based on SKILL output
Coordinates multi-agent decisions and risk management
"""
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .skill_loop import SKILLCognitiveLoop
from .risk_manager import RiskManager


@dataclass
class TradingSignal:
    symbol: str
    direction: str  # BUY, SELL, HOLD
    conviction: float
    strategy: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    size: float
    urgency: str  # LOW, MEDIUM, HIGH
    reasoning: str
    ts: datetime


class StrategyEngine:
    """Generates actionable trading signals from SKILL output"""

    def __init__(self, skill_loop: SKILLCognitiveLoop, risk_manager: RiskManager):
        self.skill = skill_loop
        self.risk = risk_manager
        self.signal_history: List[TradingSignal] = []
        self.active_signals: Dict[str, TradingSignal] = {}

    async def generate_signals(
        self,
        market_data: dict,
        options_data: dict,
        agent_signals: Dict[str, dict],
        current_positions: dict,
        portfolio_value: float,
        sentiment_data: Optional[dict] = None
    ) -> List[TradingSignal]:
        """Generate trading signals from SKILL output"""
        skill_output = await self.skill.process(
            market_data, options_data, agent_signals, sentiment_data
        )

        signals = []

        symbols = market_data.get("symbols", ["SPY"])
        for symbol in symbols:
            signal = self._generate_symbol_signal(
                symbol, skill_output, market_data, options_data,
                current_positions, portfolio_value
            )

            if signal:
                is_valid, violations = self.risk.check_order(
                    {
                        "symbol": signal.symbol,
                        "side": signal.direction,
                        "quantity": signal.size,
                        "price": signal.entry_price,
                        "stop_loss": signal.stop_loss
                    },
                    current_positions,
                    portfolio_value
                )

                if is_valid:
                    signals.append(signal)
                    self.active_signals[symbol] = signal
                else:
                    signal.reasoning = f"Risk violations: {', '.join(violations)}"
                    signal.conviction *= 0.3

        self.signal_history.extend(signals)
        return signals

    def _generate_symbol_signal(
        self,
        symbol: str,
        skill_output: dict,
        market_data: dict,
        options_data: dict,
        positions: dict,
        portfolio_value: float
    ) -> Optional[TradingSignal]:
        """Generate signal for a specific symbol"""
        conviction = skill_output.get("conviction_score", 5)
        regime = skill_output.get("market_regime", "LOW_VOL_RANGE")
        strategy = skill_output.get("adaptation_strategy", "NEUTRAL")

        if conviction < 5:
            return TradingSignal(
                symbol=symbol,
                direction="HOLD",
                conviction=conviction,
                strategy=strategy,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                size=0,
                urgency="LOW",
                reasoning="Low conviction - no action",
                ts=datetime.utcnow()
            )

        gex_data = skill_output.get("gex")
        dex_data = skill_output.get("dex")
        vc_data = skill_output.get("vanna_charm")

        direction = self._determine_direction(
            regime, strategy, gex_data, dex_data, vc_data
        )

        current_price = market_data.get("current_price", {}).get(symbol, 100)

        entry, stop, target = self._calculate_levels(
            direction, current_price, regime, gex_data
        )

        size = self._calculate_position_size(
            conviction, portfolio_value, regime, current_price
        )

        urgency = self._determine_urgency(regime, conviction)

        reasoning = self._build_reasoning(
            direction, regime, strategy, gex_data, dex_data, vc_data, conviction
        )

        return TradingSignal(
            symbol=symbol,
            direction=direction,
            conviction=conviction,
            strategy=strategy,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            size=size,
            urgency=urgency,
            reasoning=reasoning,
            ts=datetime.utcnow()
        )

    def _determine_direction(
        self,
        regime: str,
        strategy: str,
        gex: Optional[dict],
        dex: Optional[dict],
        vc: Optional[dict]
    ) -> str:
        """Determine trade direction"""
        if strategy == "REDUCE_EXPOSURE":
            return "HOLD"

        if strategy in ["TREND_FOLLOWING", "MOMENTUM_WITH_HEDGE"]:
            if dex:
                if "BULLISH" in dex.get("directional_bias", ""):
                    return "BUY"
                elif "BEARISH" in dex.get("directional_bias", ""):
                    return "SELL"
            return "BUY" if regime in ["LOW_VOL_TREND", "HIGH_VOL_TREND"] else "SELL"

        if strategy in ["MEAN_REVERSION", "STRANGLE_SELLING"]:
            return "HOLD"

        if strategy in ["BREAKOUT_TRADING", "DYNAMIC_HEDGING_ON"]:
            if gex and gex.get("net_gex", 0) < 0:
                return "BUY" if regime == "VOLATILE_BREAKOUT" else "SELL"
            return "BUY"

        if strategy == "DEFENSIVE_HEDGING":
            return "SELL"

        return "HOLD"

    def _calculate_levels(
        self,
        direction: str,
        current_price: float,
        regime: str,
        gex: Optional[dict]
    ) -> tuple:
        """Calculate entry, stop loss, and take profit levels"""
        if direction == "HOLD":
            return None, None, None

        if direction == "BUY":
            entry = current_price
            if gex and gex.get("gamma_flip_level"):
                stop = min(current_price * 0.97, gex["gamma_flip_level"] * 0.99)
            else:
                stop = current_price * 0.97

            if "HIGH_VOL" in regime or "CRISIS" in regime:
                target = current_price * 1.05
            else:
                target = current_price * 1.08

        else:  # SELL
            entry = current_price
            if gex and gex.get("gamma_flip_level"):
                stop = max(current_price * 1.03, gex["gamma_flip_level"] * 1.01)
            else:
                stop = current_price * 1.03

            if "HIGH_VOL" in regime or "CRISIS" in regime:
                target = current_price * 0.95
            else:
                target = current_price * 0.92

        return entry, stop, target

    def _calculate_position_size(
        self,
        conviction: float,
        portfolio_value: float,
        regime: str,
        price: float
    ) -> float:
        """Calculate position size based on Kelly-like criterion"""
        base_pct = conviction / 10

        regime_multiplier = {
            "LOW_VOL_TREND": 1.0,
            "LOW_VOL_RANGE": 0.8,
            "HIGH_VOL_TREND": 0.6,
            "HIGH_VOL_RANGE": 0.5,
            "VOLATILE_BREAKOUT": 0.4,
            "CRISIS": 0.2
        }

        multiplier = regime_multiplier.get(regime, 0.5)
        size_pct = base_pct * multiplier * 0.25

        size_pct = min(size_pct, 0.25)

        position_value = portfolio_value * size_pct
        shares = position_value / price if price > 0 else 0

        return round(shares, 0)

    def _determine_urgency(self, regime: str, conviction: float) -> str:
        """Determine order urgency"""
        if regime in ["CRISIS", "VOLATILE_BREAKOUT"]:
            return "HIGH"
        elif conviction > 8:
            return "HIGH"
        elif conviction > 6:
            return "MEDIUM"
        return "LOW"

    def _build_reasoning(
        self,
        direction: str,
        regime: str,
        strategy: str,
        gex: Optional[dict],
        dex: Optional[dict],
        vc: Optional[dict],
        conviction: float
    ) -> str:
        """Build human-readable reasoning"""
        parts = []

        parts.append(f"Regime: {regime}")
        parts.append(f"Strategy: {strategy}")
        parts.append(f"Conviction: {conviction:.1f}/10")

        if gex:
            gex_regime = gex.get("regime", "UNKNOWN")
            parts.append(f"GEX: {gex_regime}")

        if dex:
            bias = dex.get("directional_bias", "NEUTRAL")
            parts.append(f"DEX: {bias}")

        if vc:
            vanna = vc.get("vanna_exposure", "NEUTRAL")
            parts.append(f"Vanna: {vanna}")

        return " | ".join(parts)

    def get_active_signals(self) -> Dict[str, TradingSignal]:
        return self.active_signals

    def get_signal_history(self, limit: int = 100) -> List[TradingSignal]:
        return self.signal_history[-limit:]
