"""
Volatility Surface — SVI parameterization and interpolation
Supports Sticky-Strike and Sticky-Delta paradigms
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from scipy.optimize import minimize
from scipy.interpolate import griddata


@dataclass
class VolPoint:
    strike: float
    expiry: float
    iv: float
    bid_iv: float
    ask_iv: float
    volume: int
    open_interest: int


@dataclass
class SVIParams:
    """SVI parameterization: w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))"""
    a: float
    b: float
    rho: float
    m: float
    sigma: float
    expiry: float


class VolatilitySurface:
    """Volatility surface construction and analysis"""

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
        self.svi_params: Dict[float, SVIParams] = {}
        self.surface_data: List[VolPoint] = []

    def add_data_point(self, point: VolPoint):
        """Add a data point to the surface"""
        self.surface_data.append(point)

    def fit_svi(self, expiry: float, strikes: List[float], ivs: List[float]) -> SVIParams:
        """Fit SVI parameters to volatility smile"""
        if len(strikes) < 5:
            raise ValueError("Need at least 5 strikes for SVI fit")

        forward = strikes[len(strikes) // 2]
        log_moneyness = [np.log(k / forward) for k in strikes]

        def svi_total_variance(k, a, b, rho, m, sigma):
            return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma ** 2))

        def objective(params):
            a, b, rho, m, sigma = params
            total_var = [svi_total_variance(k, a, b, rho, m, sigma) for k in log_moneyness]
            iv_fitted = [np.sqrt(tv / expiry) if tv > 0 else 0 for tv in total_var]
            return sum((f - o) ** 2 for f, o in zip(iv_fitted, ivs))

        x0 = [0.01, 0.1, 0.0, 0.0, 0.1]
        bounds = [
            (-0.5, 0.5),    # a
            (0.001, 1.0),   # b
            (-0.999, 0.999), # rho
            (-1.0, 1.0),    # m
            (0.001, 2.0)    # sigma
        ]

        result = minimize(objective, x0, method='L-BFGS-B', bounds=bounds)
        a, b, rho, m, sigma = result.x

        svi_params = SVIParams(a=a, b=b, rho=rho, m=m, sigma=sigma, expiry=expiry)
        self.svi_params[expiry] = svi_params
        return svi_params

    def get_iv(self, strike: float, expiry: float, forward: float) -> float:
        """Get interpolated IV from SVI parameters"""
        if expiry not in self.svi_params:
            nearest = min(self.svi_params.keys(), key=lambda x: abs(x - expiry))
            if abs(nearest - expiry) > 30:
                return 0.2
            params = self.svi_params[nearest]
        else:
            params = self.svi_params[expiry]

        log_moneyness = np.log(strike / forward)
        total_var = params.a + params.b * (
            params.rho * (log_moneyness - params.m) +
            np.sqrt((log_moneyness - params.m) ** 2 + params.sigma ** 2)
        )

        if total_var < 0:
            return 0.2

        return np.sqrt(total_var / expiry)

    def get_term_structure(self, strikes: List[float], forward: float) -> Dict[float, float]:
        """Get term structure at a given strike"""
        term_structure = {}
        for expiry, params in sorted(self.svi_params.items()):
            term_structure[expiry] = self.get_iv(strikes[0], expiry, forward)
        return term_structure

    def get_skew(self, expiry: float, forward: float, moneyness_range: float = 0.2) -> Dict[float, float]:
        """Get skew across moneyness"""
        if expiry not in self.svi_params:
            return {}

        params = self.svi_params[expiry]
        skew = {}

        for delta in np.linspace(-moneyness_range, moneyness_range, 21):
            k = forward * np.exp(delta)
            log_m = np.log(k / forward)
            total_var = params.a + params.b * (
                params.rho * (log_m - params.m) +
                np.sqrt((log_m - params.m) ** 2 + params.sigma ** 2)
            )
            iv = np.sqrt(total_var / expiry) if total_var > 0 else 0.2
            skew[round(delta, 4)] = iv

        return skew

    def calculate_surface_metrics(self, forward: float) -> dict:
        """Calculate aggregate surface metrics"""
        if not self.svi_params:
            return {}

        expiries = sorted(self.svi_params.keys())
        atm_ivs = []

        for expiry in expiries:
            atm_iv = self.get_iv(forward, expiry, forward)
            atm_ivs.append((expiry, atm_iv))

        term_slope = 0
        if len(atm_ivs) >= 2:
            term_slope = (atm_ivs[-1][1] - atm_ivs[0][1]) / (atm_ivs[-1][0] - atm_ivs[0][0])

        skew_values = {}
        for expiry in expiries[:5]:
            skew = self.get_skew(expiry, forward, 0.1)
            if skew:
                otm_put = min(skew.values())
                otm_call = max(skew.values())
                skew_values[expiry] = otm_put - otm_call

        return {
            "term_structure": {e: iv for e, iv in atm_ivs},
            "term_slope": term_slope,
            "skew_by_expiry": skew_values,
            "avg_atm_iv": np.mean([iv for _, iv in atm_ivs]) if atm_ivs else 0,
            "min_atm_iv": min([iv for _, iv in atm_ivs]) if atm_ivs else 0,
            "max_atm_iv": max([iv for _, iv in atm_ivs]) if atm_ivs else 0
        }
