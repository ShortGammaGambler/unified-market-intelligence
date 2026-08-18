"""
GEX Calculator — Gamma Exposure and Dealer Hedging Obligations
Implements both Spot GEX and Absolute GEX methodologies
"""
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

from .greeks import GreeksCalculator


@dataclass
class OptionData:
    strike: float
    expiry: float  # Time to expiry in years
    iv: float
    call_oi: int
    put_oi: int
    call_volume: int
    put_volume: int
    underlying_price: float


@dataclass
class GEXResult:
    symbol: str
    ts: datetime
    total_gex: float
    call_gex: float
    put_gex: float
    gamma_flip_level: float
    net_gex: float
    normalized_gex: float  # GEX / underlying price
    gex_by_strike: Dict[float, float]
    flip_point: float


class GEXCalculator:
    """Calculate Gamma Exposure and identify gamma flip levels"""

    def __init__(self, spot_gex: bool = True, divisor: float = 100):
        self.spot_gex = spot_gex
        self.divisor = divisor

    def calculate_option_gex(
        self,
        strike: float,
        underlying: float,
        iv: float,
        expiry: float,
        open_interest: int,
        option_type: str = "call",
        r: float = 0.05
    ) -> float:
        """Calculate GEX for a single option"""
        gamma = GreeksCalculator.gamma(underlying, strike, r, iv, expiry)

        multiplier = underlying if self.spot_gex else strike

        gex = gamma * open_interest * multiplier * self.divisor / 100

        if option_type == "put":
            gex = -gex

        return gex

    def calculate_total_gex(
        self,
        options: List[OptionData],
        symbol: str
    ) -> GEXResult:
        """Calculate total GEX across all strikes"""
        call_gex = 0
        put_gex = 0
        gex_by_strike = {}
        underlying = options[0].underlying_price if options else 0

        for opt in options:
            if opt.call_oi > 0:
                cgex = self.calculate_option_gex(
                    opt.strike, underlying, opt.iv, opt.expiry,
                    opt.call_oi, "call"
                )
                call_gex += cgex
                gex_by_strike[opt.strike] = gex_by_strike.get(opt.strike, 0) + cgex

            if opt.put_oi > 0:
                pgex = self.calculate_option_gex(
                    opt.strike, underlying, opt.iv, opt.expiry,
                    opt.put_oi, "put"
                )
                put_gex += pgex
                gex_by_strike[opt.strike] = gex_by_strike.get(opt.strike, 0) + pgex

        total_gex = call_gex + put_gex
        net_gex = call_gex + put_gex
        gamma_flip_level = self._find_gamma_flip(gex_by_strike, underlying)
        normalized_gex = total_gex / underlying if underlying > 0 else 0

        return GEXResult(
            symbol=symbol,
            ts=datetime.utcnow(),
            total_gex=total_gex,
            call_gex=call_gex,
            put_gex=put_gex,
            gamma_flip_level=gamma_flip_level,
            net_gex=net_gex,
            normalized_gex=normalized_gex,
            gex_by_strike=gex_by_strike,
            flip_point=gamma_flip_level
        )

    def _find_gamma_flip(self, gex_by_strike: Dict[float, float], underlying: float) -> float:
        """Find gamma flip level where net GEX changes sign"""
        strikes = sorted(gex_by_strike.keys())
        if not strikes:
            return underlying

        cumulative_gex = 0
        flip_level = strikes[0]

        for strike in strikes:
            cumulative_gex += gex_by_strike[strike]
            if cumulative_gex > 0:
                flip_level = strike
                break

        return flip_level

    def get_gex_regime(self, result: GEXResult) -> str:
        """Classify market regime based on GEX"""
        if result.net_gex > 0:
            if result.normalized_gex > 0.001:
                return "HIGH_POSITIVE_GEX"
            return "POSITIVE_GEX"
        else:
            if result.normalized_gex < -0.001:
                return "HIGH_NEGATIVE_GEX"
            return "NEGATIVE_GEX"

    def get_hedging_implications(self, result: GEXResult) -> dict:
        """Interpret GEX for dealer hedging behavior"""
        regime = self.get_gex_regime(result)

        implications = {
            "HIGH_POSITIVE_GEX": {
                "dealer_behavior": "Dealers are long gamma, will sell rallies and buy dips",
                "expected_volatility": "LOW",
                "strategy": "Sell premium, range-bound strategies"
            },
            "POSITIVE_GEX": {
                "dealer_behavior": "Mild stabilizing effect",
                "expected_volatility": "MODERATE_LOW",
                "strategy": "Neutral strategies, iron condors"
            },
            "NEGATIVE_GEX": {
                "dealer_behavior": "Dealers are short gamma, will amplify moves",
                "expected_volatility": "MODERATE_HIGH",
                "strategy": "Buy premium, directional plays"
            },
            "HIGH_NEGATIVE_GEX": {
                "dealer_behavior": "Dealers aggressively hedge, amplifying volatility",
                "expected_volatility": "HIGH",
                "strategy": "Vol breakout, straddles, protection"
            }
        }

        return implications.get(regime, {
            "dealer_behavior": "Unknown",
            "expected_volatility": "UNKNOWN",
            "strategy": "Hold"
        })
