"""
Regime Detector — HMM-based market regime classification
Detects volatility regimes, trend states, and structural breaks
"""
import numpy as np
from typing import List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import warnings

warnings.filterwarnings("ignore")


class MarketRegime(str, Enum):
    LOW_VOL_TREND = "LOW_VOL_TREND"
    HIGH_VOL_TREND = "HIGH_VOL_TREND"
    LOW_VOL_RANGE = "LOW_VOL_RANGE"
    HIGH_VOL_RANGE = "HIGH_VOL_RANGE"
    VOLATILE_BREAKOUT = "VOLATILE_BREAKOUT"
    CRISIS = "CRISIS"


@dataclass
class RegimeState:
    current_regime: MarketRegime
    confidence: float
    duration: int  # Days in current regime
    transition_probs: dict
    features: dict
    ts: datetime


class RegimeDetector:
    """Hidden Markov Model based regime detection"""

    def __init__(self, n_regimes: int = 6, lookback: int = 252):
        self.n_regimes = n_regimes
        self.lookback = lookback
        self.regime_history: List[MarketRegime] = []
        self.transition_matrix: Optional[np.ndarray] = None
        self.regime_means: Optional[np.ndarray] = None
        self.regime_covars: Optional[np.ndarray] = None
        self._fitted = False

    def fit(self, returns: np.ndarray):
        """Fit HMM to historical returns"""
        from hmmlearn.hmm import GaussianHMM

        if len(returns) < self.lookback:
            returns = returns[-self.lookback:]

        vol = self._calculate_volatility(returns)
        momentum = self._calculate_momentum(returns)
        features = np.column_stack([returns, vol, momentum])

        model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=200,
            random_state=42
        )

        model.fit(features)

        self.transition_matrix = model.transmat_
        self.regime_means = model.means_
        self.regime_covars = model.covars_
        self.model = model
        self._fitted = True

        self._classify_regimes(features)

    def detect(self, returns: np.ndarray) -> RegimeState:
        """Detect current regime"""
        if not self._fitted:
            return self._fallback_detection(returns)

        vol = self._calculate_volatility(returns)
        momentum = self._calculate_momentum(returns)
        features = np.column_stack([returns[-self.lookback:], vol[-self.lookback:], momentum[-self.lookback:]])

        try:
            regime_idx = self.model.predict(features)[-1]
            regime = self._map_regime(regime_idx)
            confidence = self._calculate_confidence(features[-1:], regime_idx)
            transition_probs = self._get_transition_probs(regime_idx)
            duration = self._get_regime_duration(regime)

            return RegimeState(
                current_regime=regime,
                confidence=confidence,
                duration=duration,
                transition_probs=transition_probs,
                features={
                    "returns_mean": np.mean(returns[-20:]),
                    "volatility": np.std(returns[-20:]),
                    "momentum": momentum[-1] if len(momentum) > 0 else 0
                },
                ts=datetime.utcnow()
            )
        except Exception as e:
            return self._fallback_detection(returns)

    def _fallback_detection(self, returns: np.ndarray) -> RegimeState:
        """Simple rule-based regime detection as fallback"""
        if len(returns) < 20:
            return RegimeState(
                current_regime=MarketRegime.LOW_VOL_RANGE,
                confidence=0.5,
                duration=0,
                transition_probs={},
                features={},
                ts=datetime.utcnow()
            )

        recent_vol = np.std(returns[-20:])
        hist_vol = np.std(returns[-252:]) if len(returns) >= 252 else np.std(returns)
        momentum = np.mean(returns[-20:])

        vol_ratio = recent_vol / hist_vol if hist_vol > 0 else 1.0

        if vol_ratio > 2.0:
            if abs(momentum) > recent_vol * 2:
                regime = MarketRegime.CRISIS
            else:
                regime = MarketRegime.VOLATILE_BREAKOUT
        elif vol_ratio > 1.2:
            if momentum > 0:
                regime = MarketRegime.HIGH_VOL_TREND
            else:
                regime = MarketRegime.HIGH_VOL_TREND
        else:
            if abs(momentum) < recent_vol * 0.5:
                regime = MarketRegime.LOW_VOL_RANGE
            else:
                regime = MarketRegime.LOW_VOL_TREND

        confidence = min(0.9, 0.5 + (vol_ratio - 1) * 0.2) if vol_ratio > 1 else 0.6

        return RegimeState(
            current_regime=regime,
            confidence=confidence,
            duration=1,
            transition_probs={},
            features={
                "returns_mean": momentum,
                "volatility": recent_vol,
                "vol_ratio": vol_ratio
            },
            ts=datetime.utcnow()
        )

    def _calculate_volatility(self, returns: np.ndarray) -> np.ndarray:
        """Rolling volatility"""
        vol = np.zeros_like(returns)
        for i in range(20, len(returns)):
            vol[i] = np.std(returns[i-20:i])
        return vol

    def _calculate_momentum(self, returns: np.ndarray) -> np.ndarray:
        """Rolling momentum"""
        momentum = np.zeros_like(returns)
        for i in range(20, len(returns)):
            momentum[i] = np.sum(returns[i-20:i])
        return momentum

    def _classify_regimes(self, features: np.ndarray):
        """Classify fitted regimes into named categories"""
        if self.regime_means is None:
            return

        vol_means = np.std(features, axis=0)
        self.regime_names = []

        for i in range(self.n_regimes):
            mean_vol = self.regime_means[i, 1] if self.regime_means.shape[1] > 1 else 0
            mean_momentum = self.regime_means[i, 2] if self.regime_means.shape[1] > 2 else 0

            if mean_vol > vol_means[1] * 1.5:
                if abs(mean_momentum) > vol_means[2] * 2:
                    self.regime_names.append(MarketRegime.CRISIS)
                else:
                    self.regime_names.append(MarketRegime.VOLATILE_BREAKOUT)
            elif mean_vol > vol_means[1]:
                self.regime_names.append(MarketRegime.HIGH_VOL_TREND)
            else:
                if abs(mean_momentum) < vol_means[2] * 0.5:
                    self.regime_names.append(MarketRegime.LOW_VOL_RANGE)
                else:
                    self.regime_names.append(MarketRegime.LOW_VOL_TREND)

        while len(self.regime_names) < self.n_regimes:
            self.regime_names.append(MarketRegime.LOW_VOL_RANGE)

    def _map_regime(self, idx: int) -> MarketRegime:
        """Map HMM state to regime name"""
        if hasattr(self, 'regime_names') and idx < len(self.regime_names):
            return self.regime_names[idx]
        return list(MarketRegime)[idx % len(MarketRegime)]

    def _calculate_confidence(self, features: np.ndarray, regime_idx: int) -> float:
        """Calculate confidence in regime classification"""
        try:
            posteriors = self.model.predict_proba(features)
            return float(np.max(posteriors))
        except Exception:
            return 0.7

    def _get_transition_probs(self, regime_idx: int) -> dict:
        """Get transition probabilities from current regime"""
        if self.transition_matrix is None:
            return {}

        probs = self.transition_matrix[regime_idx]
        return {self._map_regime(i): float(p) for i, p in enumerate(probs)}

    def _get_regime_duration(self, regime: MarketRegime) -> int:
        """Get how long we've been in current regime"""
        if not self.regime_history:
            return 1

        count = 0
        for r in reversed(self.regime_history):
            if r == regime:
                count += 1
            else:
                break

        return max(count, 1)
