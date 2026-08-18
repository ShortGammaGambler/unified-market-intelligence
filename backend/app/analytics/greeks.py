"""
Greeks Calculator — Black-Scholes and analytical Greeks
Supports European-style options on futures and equities
"""
import numpy as np
from scipy.stats import norm
from typing import Optional, Tuple
from datetime import datetime


class GreeksCalculator:
    """Black-Scholes Greeks calculator"""

    @staticmethod
    def _d1(S: float, K: float, r: float, sigma: float, T: float) -> float:
        return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def _d2(S: float, K: float, r: float, sigma: float, T: float) -> float:
        return GreeksCalculator._d1(S, K, r, sigma, T) - sigma * np.sqrt(T)

    @staticmethod
    def delta(S: float, K: float, r: float, sigma: float, T: float, option_type: str = "call") -> float:
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        if option_type == "call":
            return np.exp(-r * T) * norm.cdf(d1)
        else:
            return -np.exp(-r * T) * norm.cdf(-d1)

    @staticmethod
    def gamma(S: float, K: float, r: float, sigma: float, T: float) -> float:
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        return np.exp(-r * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))

    @staticmethod
    def vega(S: float, K: float, r: float, sigma: float, T: float) -> float:
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        return S * np.exp(-r * T) * norm.pdf(d1) * np.sqrt(T) / 100

    @staticmethod
    def theta(S: float, K: float, r: float, sigma: float, T: float, option_type: str = "call") -> float:
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        d2 = GreeksCalculator._d2(S, K, r, sigma, T)

        term1 = -S * np.exp(-r * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))

        if option_type == "call":
            term2 = r * K * np.exp(-r * T) * norm.cdf(d2)
            term3 = -r * S * np.exp(-r * T) * norm.cdf(d1)
        else:
            term2 = -r * K * np.exp(-r * T) * norm.cdf(-d2)
            term3 = r * S * np.exp(-r * T) * norm.cdf(-d1)

        return (term1 + term2 + term3) / 365

    @staticmethod
    def volga(S: float, K: float, r: float, sigma: float, T: float) -> float:
        """Second-order Greek: d(Vega)/d(Sigma)"""
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        d2 = GreeksCalculator._d2(S, K, r, sigma, T)
        return GreeksCalculator.vega(S, K, r, sigma, T) * (d1 * d2) / sigma

    @staticmethod
    def vomma(S: float, K: float, r: float, sigma: float, T: float) -> float:
        """Second-order Greek: d²V/dσ²"""
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        vega = GreeksCalculator.vega(S, K, r, sigma, T)
        return vega * ((d1 * d2) / sigma)

    @staticmethod
    def charm(S: float, K: float, r: float, sigma: float, T: float, option_type: str = "call") -> float:
        """Delta decay over time: d(Delta)/d(t)"""
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        d2 = GreeksCalculator._d2(S, K, r, sigma, T)

        if option_type == "call":
            charm = -np.exp(-r * T) * (
                norm.pdf(d1) * (r / (sigma * np.sqrt(T)) - 0.5 * d1 / T) +
                r * norm.cdf(d1)
            )
        else:
            charm = np.exp(-r * T) * (
                norm.pdf(d1) * (r / (sigma * np.sqrt(T)) - 0.5 * d1 / T) +
                r * norm.cdf(-d1)
            )

        return charm

    @staticmethod
    def vanna(S: float, K: float, r: float, sigma: float, T: float) -> float:
        """d(Delta)/d(Sigma)"""
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        d2 = GreeksCalculator._d2(S, K, r, sigma, T)
        return -np.exp(-r * T) * norm.pdf(d1) * d2 / sigma

    @staticmethod
    def price(S: float, K: float, r: float, sigma: float, T: float, option_type: str = "call") -> float:
        """Black-Scholes price"""
        d1 = GreeksCalculator._d1(S, K, r, sigma, T)
        d2 = GreeksCalculator._d2(S, K, r, sigma, T)

        if option_type == "call":
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    @classmethod
    def compute_all(cls, S: float, K: float, r: float, sigma: float, T: float, option_type: str = "call") -> dict:
        """Compute all Greeks for an option"""
        return {
            "price": cls.price(S, K, r, sigma, T, option_type),
            "delta": cls.delta(S, K, r, sigma, T, option_type),
            "gamma": cls.gamma(S, K, r, sigma, T),
            "vega": cls.vega(S, K, r, sigma, T),
            "theta": cls.theta(S, K, r, sigma, T, option_type),
            "volga": cls.volga(S, K, r, sigma, T),
            "charm": cls.charm(S, K, r, sigma, T, option_type),
            "vanna": cls.vanna(S, K, r, sigma, T),
            "d1": cls._d1(S, K, r, sigma, T),
            "d2": cls._d2(S, K, r, sigma, T)
        }
