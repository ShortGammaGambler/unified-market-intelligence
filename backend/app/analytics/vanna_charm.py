"""
Vanna/Charm Calculator — Second-order Greeks for Volatility and Delta Dynamics
Measures sensitivity of delta to IV changes and delta decay over time
"""
import numpy as np
from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass

from .greeks import GreeksCalculator


@dataclass
class VannaCharmPosition:
    strike: float
    expiry: float
    iv: float
    call_oi: int
    put_oi: int
    underlying_price: float


@dataclass
class VannaCharmResult:
    symbol: str
    ts: datetime
    total_vanna: float
    call_vanna: float
    put_vanna: float
    total_charm: float
    call_charm: float
    put_charm: float
    vanna_exposure: str
    charm_exposure: str
    vanna_by_strike: Dict[float, float]
    charm_by_strike: Dict[float, float]
    vanna_flip_level: float
    charm_flip_level: float


class VannaCharmCalculator:
    """Calculate Vanna and Charm for options positioning analysis"""

    def __init__(self, spot_exposure: bool = True, divisor: float = 100):
        self.spot_exposure = spot_exposure
        self.divisor = divisor

    def calculate_option_vanna(
        self,
        strike: float,
        underlying: float,
        iv: float,
        expiry: float,
        open_interest: int,
        option_type: str = "call",
        r: float = 0.05
    ) -> float:
        """Calculate Vanna for a single option"""
        vanna = GreeksCalculator.vanna(underlying, strike, r, iv, expiry)

        multiplier = underlying if self.spot_exposure else strike
        return vanna * open_interest * multiplier * self.divisor / 100

    def calculate_option_charm(
        self,
        strike: float,
        underlying: float,
        iv: float,
        expiry: float,
        open_interest: int,
        option_type: str = "call",
        r: float = 0.05
    ) -> float:
        """Calculate Charm for a single option"""
        charm = GreeksCalculator.charm(underlying, strike, r, iv, expiry, option_type)

        multiplier = underlying if self.spot_exposure else strike
        return charm * open_interest * multiplier * self.divisor / 100

    def calculate_total(
        self,
        positions: List[VannaCharmPosition],
        symbol: str
    ) -> VannaCharmResult:
        """Calculate total Vanna and Charm across all strikes"""
        call_vanna = 0
        put_vanna = 0
        call_charm = 0
        put_charm = 0
        vanna_by_strike = {}
        charm_by_strike = {}

        for pos in positions:
            underlying = pos.underlying_price

            if pos.call_oi > 0:
                cv = self.calculate_option_vanna(
                    pos.strike, underlying, pos.iv, pos.expiry, pos.call_oi, "call"
                )
                cc = self.calculate_option_charm(
                    pos.strike, underlying, pos.iv, pos.expiry, pos.call_oi, "call"
                )
                call_vanna += cv
                call_charm += cc
                vanna_by_strike[pos.strike] = vanna_by_strike.get(pos.strike, 0) + cv
                charm_by_strike[pos.strike] = charm_by_strike.get(pos.strike, 0) + cc

            if pos.put_oi > 0:
                pv = self.calculate_option_vanna(
                    pos.strike, underlying, pos.iv, pos.expiry, pos.put_oi, "put"
                )
                pc = self.calculate_option_charm(
                    pos.strike, underlying, pos.iv, pos.expiry, pos.put_oi, "put"
                )
                put_vanna += pv
                put_charm += pc
                vanna_by_strike[pos.strike] = vanna_by_strike.get(pos.strike, 0) + pv
                charm_by_strike[pos.strike] = charm_by_strike.get(pos.strike, 0) + pc

        total_vanna = call_vanna + put_vanna
        total_charm = call_charm + put_charm

        vanna_exposure = self._classify_vanna(total_vanna, positions[0].underlying_price if positions else 0)
        charm_exposure = self._classify_charm(total_charm, positions[0].underlying_price if positions else 0)

        vanna_flip = self._find_flip(vanna_by_strike)
        charm_flip = self._find_flip(charm_by_strike)

        return VannaCharmResult(
            symbol=symbol,
            ts=datetime.utcnow(),
            total_vanna=total_vanna,
            call_vanna=call_vanna,
            put_vanna=put_vanna,
            total_charm=total_charm,
            call_charm=call_charm,
            put_charm=put_charm,
            vanna_exposure=vanna_exposure,
            charm_exposure=charm_exposure,
            vanna_by_strike=vanna_by_strike,
            charm_by_strike=charm_by_strike,
            vanna_flip_level=vanna_flip,
            charm_flip_level=charm_flip
        )

    def _classify_vanna(self, total_vanna: float, underlying: float) -> str:
        """Classify vanna exposure"""
        if underlying == 0:
            return "NEUTRAL"

        normalized = total_vanna / (underlying * 1000)

        if normalized > 0.05:
            return "STRONG_NEGATIVE"
        elif normalized > 0.01:
            return "NEGATIVE"
        elif normalized < -0.05:
            return "STRONG_POSITIVE"
        elif normalized < -0.01:
            return "POSITIVE"
        else:
            return "NEUTRAL"

    def _classify_charm(self, total_charm: float, underlying: float) -> str:
        """Classify charm exposure"""
        if underlying == 0:
            return "NEUTRAL"

        normalized = total_charm / (underlying * 1000)

        if normalized > 0.05:
            return "DELTA_DECAY_BEARISH"
        elif normalized > 0.01:
            return "DELTA_DECAY_SLIGHT_BEARISH"
        elif normalized < -0.05:
            return "DELTA_DECAY_BULLISH"
        elif normalized < -0.01:
            return "DELTA_DECAY_SLIGHT_BULLISH"
        else:
            return "NEUTRAL"

    def _find_flip(self, exposure_by_strike: Dict[float, float]) -> float:
        """Find flip level where exposure changes sign"""
        if not exposure_by_strike:
            return 0.0

        strikes = sorted(exposure_by_strike.keys())
        cumulative = 0

        for strike in strikes:
            cumulative += exposure_by_strike[strike]
            if cumulative > 0:
                return strike

        return strikes[-1] if strikes else 0.0

    def get_implications(self, result: VannaCharmResult) -> dict:
        """Interpret Vanna/Charm for market dynamics"""
        vanna_implications = {
            "STRONG_NEGATIVE": "IV drops will force significant delta hedging (bearish flow)",
            "NEGATIVE": "IV drops create mild selling pressure",
            "NEUTRAL": "Minimal IV-delta feedback loop",
            "POSITIVE": "IV drops create mild buying pressure",
            "STRONG_POSITIVE": "IV drops force significant buying (bullish flow)"
        }

        charm_implications = {
            "DELTA_DECAY_BEARISH": "Delta decays toward negative as expiry approaches",
            "DELTA_DECAY_SLIGHT_BEARISH": "Mild bearish delta decay",
            "NEUTRAL": "Balanced delta decay",
            "DELTA_DECAY_SLIGHT_BULLISH": "Mild bullish delta decay",
            "DELTA_DECAY_BULLISH": "Delta decays toward positive as expiry approaches"
        }

        return {
            "vanna_signal": vanna_implications.get(result.vanna_exposure, "Unknown"),
            "charm_signal": charm_implications.get(result.charm_exposure, "Unknown"),
            "hedging_pressure": self._estimate_hedging_pressure(result),
            "expected_flow": self._estimate_flow(result)
        }

    def _estimate_hedging_pressure(self, result: VannaCharmResult) -> str:
        """Estimate dealer hedging pressure"""
        if result.vanna_exposure in ["STRONG_NEGATIVE", "NEGATIVE"]:
            return "HIGH_SELLING_PRESSURE_ON_IV_DECLINE"
        elif result.vanna_exposure in ["STRONG_POSITIVE", "POSITIVE"]:
            return "HIGH_BUYING_PRESSURE_ON_IV_DECLINE"
        return "MODERATE"

    def _estimate_flow(self, result: VannaCharmResult) -> str:
        """Estimate expected order flow"""
        if result.total_vanna < 0 and result.total_charm > 0:
            return "BEARISH_FLOW_EXPECTED"
        elif result.total_vanna > 0 and result.total_charm < 0:
            return "BULLISH_FLOW_EXPECTED"
        return "NEUTRAL_FLOW_EXPECTED"
