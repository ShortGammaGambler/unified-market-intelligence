"""
SKILL Cognitive Loop — Strategic Knowledge Integration and Logic Layer
Synthesizes quantitative and qualitative data into actionable signals
"""
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .regime_detector import RegimeDetector, MarketRegime, RegimeState
from ..analytics.gex_calculator import GEXCalculator, GEXResult
from ..analytics.dex_calculator import DEXCalculator, DEXResult
from ..analytics.vanna_charm import VannaCharmCalculator, VannaCharmResult


@dataclass
class SKILLConfig:
    conviction_threshold: float = 7.0
    regime_update_interval: int = 300  # seconds
    agent_weight: Dict[str, float] = None

    def __post_init__(self):
        if self.agent_weight is None:
            self.agent_weight = {
                "fordge": 0.4,
                "atlas": 0.3,
                "phantom": 0.3
            }


class SKILLCognitiveLoop:
    """Main cognitive engine that synthesizes all data streams"""

    def __init__(self, config: Optional[SKILLConfig] = None):
        self.config = config or SKILLConfig()
        self.regime_detector = RegimeDetector()
        self.gex_calc = GEXCalculator()
        self.dex_calc = DEXCalculator()
        self.vanna_charm_calc = VannaCharmCalculator()
        self.state: Dict[str, Any] = {}
        self.history: List[dict] = []
        self.agent_signals: Dict[str, dict] = {}

    async def process(
        self,
        market_data: dict,
        options_data: dict,
        agent_signals: Dict[str, dict],
        sentiment_data: Optional[dict] = None
    ) -> dict:
        """Main processing loop - synthesize all inputs"""
        self.agent_signals = agent_signals

        returns = self._extract_returns(market_data)
        regime_state = self.regime_detector.detect(returns)

        gex_result = None
        dex_result = None
        vc_result = None

        if options_data:
            gex_result = self._calculate_gex(options_data, market_data.get("underlying", 5000))
            dex_result = self._calculate_dex(options_data, market_data.get("underlying", 5000))
            vc_result = self._calculate_vanna_charm(options_data, market_data.get("underlying", 5000))

        conviction = self._calculate_conviction(
            regime_state, gex_result, dex_result, vc_result, agent_signals, sentiment_data
        )

        strategy = self._determine_strategy(
            regime_state, gex_result, dex_result, vc_result, conviction
        )

        risk_metrics = self._assess_risk(
            regime_state, gex_result, dex_result, market_data
        )

        output = {
            "ts": datetime.utcnow().isoformat(),
            "conviction_score": conviction,
            "market_regime": regime_state.current_regime.value,
            "regime_confidence": regime_state.confidence,
            "regime_duration": regime_state.duration,
            "adaptation_strategy": strategy,
            "gex": self._gex_to_dict(gex_result) if gex_result else None,
            "dex": self._dex_to_dict(dex_result) if dex_result else None,
            "vanna_charm": self._vc_to_dict(vc_result) if vc_result else None,
            "risk_metrics": risk_metrics,
            "agent_signals": agent_signals,
            "regime_features": regime_state.features,
            "transition_probs": {k.value: v for k, v in regime_state.transition_probs.items()}
        }

        self.state = output
        self.history.append(output)

        if len(self.history) > 1000:
            self.history = self.history[-500:]

        return output

    def _extract_returns(self, market_data: dict) -> np.ndarray:
        """Extract returns from market data"""
        prices = market_data.get("prices", [])
        if not prices:
            return np.random.normal(0, 0.01, 252)

        prices = np.array(prices)
        returns = np.diff(np.log(prices[-253:])) if len(prices) > 1 else np.array([0])
        return returns

    def _calculate_gex(self, options_data: dict, underlying: float) -> GEXResult:
        """Calculate Gamma Exposure"""
        from ..analytics.gex_calculator import OptionData

        options = []
        for strike_data in options_data.get("strikes", []):
            options.append(OptionData(
                strike=strike_data["strike"],
                expiry=strike_data.get("expiry", 0.02),
                iv=strike_data.get("iv", 0.2),
                call_oi=strike_data.get("call_oi", 0),
                put_oi=strike_data.get("put_oi", 0),
                call_volume=strike_data.get("call_volume", 0),
                put_volume=strike_data.get("put_volume", 0),
                underlying_price=underlying
            ))

        return self.gex_calc.calculate_total_gex(options, market_data.get("symbol", "SPX"))

    def _calculate_dex(self, options_data: dict, underlying: float) -> DEXResult:
        """Calculate Delta Exposure"""
        from ..analytics.dex_calculator import OptionPosition

        options = []
        for strike_data in options_data.get("strikes", []):
            options.append(OptionPosition(
                strike=strike_data["strike"],
                expiry=strike_data.get("expiry", 0.02),
                iv=strike_data.get("iv", 0.2),
                call_oi=strike_data.get("call_oi", 0),
                put_oi=strike_data.get("put_oi", 0),
                call_volume=strike_data.get("call_volume", 0),
                put_volume=strike_data.get("put_volume", 0),
                underlying_price=underlying
            ))

        return self.dex_calc.calculate_total_dex(options, market_data.get("symbol", "SPX"))

    def _calculate_vanna_charm(self, options_data: dict, underlying: float) -> VannaCharmResult:
        """Calculate Vanna and Charm"""
        from ..analytics.vanna_charm import VannaCharmPosition

        positions = []
        for strike_data in options_data.get("strikes", []):
            positions.append(VannaCharmPosition(
                strike=strike_data["strike"],
                expiry=strike_data.get("expiry", 0.02),
                iv=strike_data.get("iv", 0.2),
                call_oi=strike_data.get("call_oi", 0),
                put_oi=strike_data.get("put_oi", 0),
                underlying_price=underlying
            ))

        return self.vanna_charm_calc.calculate_total(positions, market_data.get("symbol", "SPX"))

    def _calculate_conviction(
        self,
        regime: RegimeState,
        gex: Optional[GEXResult],
        dex: Optional[DEXResult],
        vc: Optional[VannaCharmResult],
        agents: Dict[str, dict],
        sentiment: Optional[dict]
    ) -> float:
        """Calculate overall conviction score (0-10)"""
        score = 5.0  # Base

        if regime.confidence > 0.8:
            score += 1.5
        elif regime.confidence > 0.6:
            score += 0.5

        if gex:
            gex_regime = self.gex_calc.get_gex_regime(gex)
            if "HIGH" in gex_regime:
                score += 1.0
            elif "POSITIVE" in gex_regime or "NEGATIVE" in gex_regime:
                score += 0.5

        if dex:
            if dex.directional_bias in ["STRONG_BULLISH", "STRONG_BEARISH"]:
                score += 1.0
            elif dex.directional_bias in ["BULLISH", "BEARISH"]:
                score += 0.5

        agent_alignment = self._check_agent_alignment(agents)
        score += agent_alignment * 1.5

        if sentiment:
            sent_score = sentiment.get("score", 0)
            score += sent_score * 0.5

        return max(0, min(10, score))

    def _check_agent_alignment(self, agents: Dict[str, dict]) -> float:
        """Check if agents are aligned (-1 to 1)"""
        if not agents:
            return 0

        signals = []
        for agent_name, signal in agents.items():
            weight = self.config.agent_weight.get(agent_name, 0.33)
            conv = signal.get("conviction", 0)
            signals.append(conv * weight)

        if not signals:
            return 0

        avg = np.mean(signals)
        std = np.std(signals) if len(signals) > 1 else 0

        alignment = 1 - std if avg > 0 else -(1 - std)
        return alignment * abs(avg) / 5

    def _determine_strategy(
        self,
        regime: RegimeState,
        gex: Optional[GEXResult],
        dex: Optional[DEXResult],
        vc: Optional[VannaCharmResult],
        conviction: float
    ) -> str:
        """Determine adaptation strategy based on all inputs"""
        if conviction < self.config.conviction_threshold:
            return "REDUCE_EXPOSURE"

        regime_strategies = {
            MarketRegime.LOW_VOL_TREND: "TREND_FOLLOWING",
            MarketRegime.HIGH_VOL_TREND: "MOMENTUM_WITH_HEDGE",
            MarketRegime.LOW_VOL_RANGE: "MEAN_REVERSION",
            MarketRegime.HIGH_VOL_RANGE: "STRANGLE_SELLING",
            MarketRegime.VOLATILE_BREAKOUT: "BREAKOUT_TRADING",
            MarketRegime.CRISIS: "DEFENSIVE_HEDGING"
        }

        base_strategy = regime_strategies.get(regime.current_regime, "NEUTRAL")

        if gex:
            gex_regime = self.gex_calc.get_gex_regime(gex)
            if "HIGH_NEGATIVE" in gex_regime and base_strategy in ["TREND_FOLLOWING", "MOMENTUM_WITH_HEDGE"]:
                base_strategy = "DYNAMIC_HEDGING_ON"

        if vc and vc.vanna_exposure in ["STRONG_NEGATIVE", "NEGATIVE"]:
            if base_strategy in ["MEAN_REVERSION", "STRANGLE_SELLING"]:
                base_strategy = "VANNA_AWARE_TRADING"

        return base_strategy

    def _assess_risk(
        self,
        regime: RegimeState,
        gex: Optional[GEXResult],
        dex: Optional[DEXResult],
        market_data: dict
    ) -> dict:
        """Assess current risk environment"""
        risk_score = 50  # Base

        if regime.current_regime in [MarketRegime.CRISIS, MarketRegime.VOLATILE_BREAKOUT]:
            risk_score += 30
        elif regime.current_regime in [MarketRegime.HIGH_VOL_TREND, MarketRegime.HIGH_VOL_RANGE]:
            risk_score += 15

        if gex and gex.net_gex < 0:
            risk_score += 10

        if dex and "BEARISH" in dex.directional_bias:
            risk_score += 5

        returns = market_data.get("prices", [])
        if len(returns) > 20:
            recent_vol = np.std(np.diff(np.log(returns[-20:])))
            hist_vol = np.std(np.diff(np.log(returns[-252:]))) if len(returns) > 252 else recent_vol
            if recent_vol > hist_vol * 1.5:
                risk_score += 10

        risk_score = min(100, max(0, risk_score))

        return {
            "score": risk_score,
            "level": "CRITICAL" if risk_score >= 80 else "HIGH" if risk_score >= 60 else "MODERATE" if risk_score >= 40 else "LOW",
            "regime_risk": regime.current_regime.value,
            "hedging_recommended": risk_score > 60,
            "position_reduction_recommended": risk_score > 70
        }

    def _gex_to_dict(self, gex: GEXResult) -> dict:
        return {
            "total_gex": gex.total_gex,
            "call_gex": gex.call_gex,
            "put_gex": gex.put_gex,
            "gamma_flip_level": gex.gamma_flip_level,
            "net_gex": gex.net_gex,
            "normalized_gex": gex.normalized_gex,
            "regime": self.gex_calc.get_gex_regime(gex)
        }

    def _dex_to_dict(self, dex: DEXResult) -> dict:
        return {
            "total_dex": dex.total_dex,
            "call_dex": dex.call_dex,
            "put_dex": dex.put_dex,
            "net_dex": dex.net_dex,
            "directional_bias": dex.directional_bias,
            "weighted_delta": dex.weighted_delta
        }

    def _vc_to_dict(self, vc: VannaCharmResult) -> dict:
        return {
            "total_vanna": vc.total_vanna,
            "call_vanna": vc.call_vanna,
            "put_vanna": vc.put_vanna,
            "total_charm": vc.total_charm,
            "call_charm": vc.call_charm,
            "put_charm": vc.put_charm,
            "vanna_exposure": vc.vanna_exposure,
            "charm_exposure": vc.charm_exposure
        }

    def get_current_state(self) -> dict:
        """Get current SKILL state"""
        return self.state

    def get_history(self, limit: int = 100) -> List[dict]:
        """Get SKILL history"""
        return self.history[-limit:]
