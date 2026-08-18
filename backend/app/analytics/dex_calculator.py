"""
DEX Calculator — Delta Exposure and Dealer Directional Positioning
Measures aggregate directional delta bias from options positioning
"""
import numpy as np
from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass

from .greeks import GreeksCalculator


@dataclass
class OptionPosition:
    strike: float
    expiry: float
    iv: float
    call_oi: int
    put_oi: int
    call_volume: int
    put_volume: int
    underlying_price: float
    call_delta: float = 0.0
    put_delta: float = 0.0


@dataclass
class DEXResult:
    symbol: str
    ts: datetime
    total_dex: float
    call_dex: float
    put_dex: float
    net_dex: float
    directional_bias: str
    delta_by_strike: Dict[float, float]
    weighted_delta: float
    exposure_intensity: float


class DEXCalculator:
    """Calculate Delta Exposure and identify dealer directional positioning"""

    def __init__(self, spot_dex: bool = True, divisor: float = 100):
        self.spot_dex = spot_dex
        self.divisor = divisor

    def calculate_option_dex(
        self,
        strike: float,
        underlying: float,
        iv: float,
        expiry: float,
        open_interest: int,
        option_type: str = "call",
        r: float = 0.05
    ) -> float:
        """Calculate DEX for a single option"""
        delta = GreeksCalculator.delta(underlying, strike, r, iv, expiry, option_type)

        multiplier = underlying if self.spot_dex else strike

        dex = delta * open_interest * multiplier * self.divisor / 100

        return dex

    def calculate_total_dex(
        self,
        options: List[OptionPosition],
        symbol: str
    ) -> DEXResult:
        """Calculate total DEX across all strikes"""
        call_dex = 0
        put_dex = 0
        delta_by_strike = {}
        underlying = options[0].underlying_price if options else 0

        for opt in options:
            if opt.call_oi > 0:
                cdex = self.calculate_option_dex(
                    opt.strike, underlying, opt.iv, opt.expiry,
                    opt.call_oi, "call"
                )
                call_dex += cdex
                delta_by_strike[opt.strike] = delta_by_strike.get(opt.strike, 0) + cdex

            if opt.put_oi > 0:
                pdex = self.calculate_option_dex(
                    opt.strike, underlying, opt.iv, opt.expiry,
                    opt.put_oi, "put"
                )
                put_dex += pdex
                delta_by_strike[opt.strike] = delta_by_strike.get(opt.strike, 0) + pdex

        total_dex = call_dex + put_dex
        net_dex = call_dex + put_dex
        directional_bias = self._classify_bias(net_dex, underlying)

        weighted_delta = self._calculate_weighted_delta(options, underlying)
        exposure_intensity = self._calculate_intensity(options, underlying)

        return DEXResult(
            symbol=symbol,
            ts=datetime.utcnow(),
            total_dex=total_dex,
            call_dex=call_dex,
            put_dex=put_dex,
            net_dex=net_dex,
            directional_bias=directional_bias,
            delta_by_strike=delta_by_strike,
            weighted_delta=weighted_delta,
            exposure_intensity=exposure_intensity
        )

    def _classify_bias(self, net_dex: float, underlying: float) -> str:
        """Classify directional bias from DEX"""
        if underlying == 0:
            return "NEUTRAL"

        normalized = net_dex / (underlying * 1000)

        if normalized > 0.1:
            return "STRONG_BULLISH"
        elif normalized > 0.02:
            return "BULLISH"
        elif normalized < -0.1:
            return "STRONG_BEARISH"
        elif normalized < -0.02:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def _calculate_weighted_delta(self, options: List[OptionPosition], underlying: float) -> float:
        """Calculate volume-weighted delta"""
        total_volume = 0
        weighted_sum = 0

        for opt in options:
            if opt.call_volume > 0 or opt.put_volume > 0:
                call_delta = GreeksCalculator.delta(
                    underlying, opt.strike, 0.05, opt.iv, opt.expiry, "call"
                )
                put_delta = GreeksCalculator.delta(
                    underlying, opt.strike, 0.05, opt.iv, opt.expiry, "put"
                )

                call_contrib = call_delta * opt.call_volume
                put_contrib = put_delta * opt.put_volume

                weighted_sum += call_contrib + put_contrib
                total_volume += opt.call_volume + opt.put_volume

        return weighted_sum / total_volume if total_volume > 0 else 0

    def _calculate_intensity(self, options: List[OptionPosition], underlying: float) -> float:
        """Calculate DEX intensity (concentration of delta exposure)"""
        delta_by_strike = {}
        total_dex = 0

        for opt in options:
            if opt.call_oi > 0:
                cdex = self.calculate_option_dex(
                    opt.strike, underlying, opt.iv, opt.expiry, opt.call_oi, "call"
                )
                delta_by_strike[opt.strike] = delta_by_strike.get(opt.strike, 0) + abs(cdex)
                total_dex += abs(cdex)

            if opt.put_oi > 0:
                pdex = self.calculate_option_dex(
                    opt.strike, underlying, opt.iv, opt.expiry, opt.put_oi, "put"
                )
                delta_by_strike[opt.strike] = delta_by_strike.get(opt.strike, 0) + abs(pdex)
                total_dex += abs(pdex)

        if total_dex == 0:
            return 0

        max_strike_dex = max(delta_by_strike.values()) if delta_by_strike else 0
        return max_strike_dex / total_dex

    def get_hedging_implications(self, result: DEXResult) -> dict:
        """Interpret DEX for dealer hedging behavior"""
        implications = {
            "STRONG_BULLISH": {
                "dealer_bias": "Dealers net long delta, will buy dips",
                "expected_flow": "Supportive on pullbacks",
                "risk_level": "MODERATE"
            },
            "BULLISH": {
                "dealer_bias": "Mild bullish positioning",
                "expected_flow": "Neutral to supportive",
                "risk_level": "LOW"
            },
            "NEUTRAL": {
                "dealer_bias": "Balanced delta exposure",
                "expected_flow": "Neutral",
                "risk_level": "LOW"
            },
            "BEARISH": {
                "dealer_bias": "Mild bearish positioning",
                "expected_flow": "Neutral to resistance",
                "risk_level": "MODERATE"
            },
            "STRONG_BEARISH": {
                "dealer_bias": "Dealers net short delta, will sell rallies",
                "expected_flow": "Resistant on bounces",
                "risk_level": "HIGH"
            }
        }

        return implications.get(result.directional_bias, {
            "dealer_bias": "Unknown",
            "expected_flow": "Unknown",
            "risk_level": "UNKNOWN"
        })
