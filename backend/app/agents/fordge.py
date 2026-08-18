"""
Fordge Agent — Quantitative Research & Backtesting Agent
Validates strategies using historical Databento data
"""
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .agent_base import AgentBase


@dataclass
class BacktestResult:
    strategy: str
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float
    win_rate: float
    total_trades: int
    avg_trade_return: float
    volatility: float
    calmar_ratio: float
    timestamp: datetime


class FordgeAgent(AgentBase):
    """Quantitative Research & Backtesting Agent"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__("Fordge", config)
        self.data_manager = None
        self.backtest_history: List[BacktestResult] = []

    async def initialize(self):
        """Initialize Fordge agent"""
        self.state.metrics = {
            "strategies_tested": 0,
            "avg_sharpe": 0,
            "best_strategy": None,
            "backtests_completed": 0
        }

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process market data and generate research signals"""
        prices = data.get("prices", [])
        strategy = data.get("strategy", "default")
        params = data.get("params", {})

        if len(prices) < 100:
            return self._empty_signal("Insufficient data for backtesting")

        result = self._backtest_strategy(prices, strategy, params)
        self.backtest_history.append(result)

        signal = self._generate_signal(result, data)

        self.update_metrics({
            "strategies_tested": self.state.metrics.get("strategies_tested", 0) + 1,
            "avg_sharpe": np.mean([r.sharpe_ratio for r in self.backtest_history[-20:]]),
            "backtests_completed": self.state.metrics.get("backtests_completed", 0) + 1
        })

        return signal

    async def shutdown(self):
        """Cleanup Fordge resources"""
        pass

    def _backtest_strategy(
        self,
        prices: List[float],
        strategy: str,
        params: Dict
    ) -> BacktestResult:
        """Run backtest on historical data"""
        prices = np.array(prices)
        returns = np.diff(np.log(prices))

        if strategy == "momentum":
            signals = self._momentum_signals(prices, params)
        elif strategy == "mean_reversion":
            signals = self._mean_reversion_signals(prices, params)
        elif strategy == "breakout":
            signals = self._breakout_signals(prices, params)
        else:
            signals = self._default_signals(prices)

        strategy_returns = returns * signals[:-1]

        sharpe = self._calculate_sharpe(strategy_returns)
        max_dd = self._calculate_max_drawdown(strategy_returns)
        profit_factor = self._calculate_profit_factor(strategy_returns)
        win_rate = self._calculate_win_rate(strategy_returns)
        calmar = abs(np.mean(strategy_returns) * 252) / max_dd if max_dd > 0 else 0

        return BacktestResult(
            strategy=strategy,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            profit_factor=profit_factor,
            win_rate=win_rate,
            total_trades=int(np.sum(np.abs(np.diff(signals)))),
            avg_trade_return=np.mean(strategy_returns[strategy_returns != 0]) if np.any(strategy_returns != 0) else 0,
            volatility=np.std(returns),
            calmar_ratio=calmar,
            timestamp=datetime.utcnow()
        )

    def _momentum_signals(self, prices: np.ndarray, params: Dict) -> np.ndarray:
        """Generate momentum signals"""
        lookback = params.get("lookback", 20)
        threshold = params.get("threshold", 0.02)

        signals = np.zeros(len(prices))
        for i in range(lookback, len(prices)):
            ret = (prices[i] - prices[i - lookback]) / prices[i - lookback]
            if ret > threshold:
                signals[i] = 1
            elif ret < -threshold:
                signals[i] = -1
        return signals

    def _mean_reversion_signals(self, prices: np.ndarray, params: Dict) -> np.ndarray:
        """Generate mean reversion signals"""
        lookback = params.get("lookback", 50)
        std_mult = params.get("std_mult", 2)

        signals = np.zeros(len(prices))
        for i in range(lookback, len(prices)):
            mean = np.mean(prices[i - lookback:i])
            std = np.std(prices[i - lookback:i])
            z_score = (prices[i] - mean) / std if std > 0 else 0

            if z_score < -std_mult:
                signals[i] = 1
            elif z_score > std_mult:
                signals[i] = -1
        return signals

    def _breakout_signals(self, prices: np.ndarray, params: Dict) -> np.ndarray:
        """Generate breakout signals"""
        lookback = params.get("lookback", 20)
        atr_mult = params.get("atr_mult", 1.5)

        signals = np.zeros(len(prices))
        for i in range(lookback, len(prices)):
            high = np.max(prices[i - lookback:i])
            low = np.min(prices[i - lookback:i])
            atr = high - low

            if prices[i] > high - atr * 0.5:
                signals[i] = 1
            elif prices[i] < low + atr * 0.5:
                signals[i] = -1
        return signals

    def _default_signals(self, prices: np.ndarray) -> np.ndarray:
        """Generate default trend signals"""
        return np.sign(np.diff(np.log(prices), prepend=np.log(prices[0])))

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        if len(returns) < 20 or np.std(returns) == 0:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        return float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    def _calculate_profit_factor(self, returns: np.ndarray) -> float:
        gains = np.sum(returns[returns > 0])
        losses = abs(np.sum(returns[returns < 0]))
        return float(gains / losses) if losses > 0 else float('inf')

    def _calculate_win_rate(self, returns: np.ndarray) -> float:
        winning = np.sum(returns > 0)
        total = np.sum(returns != 0)
        return float(winning / total) if total > 0 else 0.0

    def _generate_signal(self, result: BacktestResult, data: Dict) -> Dict[str, Any]:
        """Generate trading signal from backtest result"""
        conviction = 5.0

        if result.sharpe_ratio > 1.5:
            conviction += 2
        elif result.sharpe_ratio > 1.0:
            conviction += 1
        elif result.sharpe_ratio < 0:
            conviction -= 2

        if result.max_drawdown < 0.05:
            conviction += 1
        elif result.max_drawdown > 0.15:
            conviction -= 1

        if result.profit_factor > 1.5:
            conviction += 1

        conviction = max(0, min(10, conviction))

        return {
            "agent": self.name,
            "conviction": conviction,
            "signal_type": "RESEARCH",
            "strategy": result.strategy,
            "backtest_metrics": {
                "sharpe": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "profit_factor": result.profit_factor,
                "win_rate": result.win_rate,
                "calmar": result.calmar_ratio
            },
            "recommendation": self._get_recommendation(result),
            "timestamp": datetime.utcnow().isoformat()
        }

    def _get_recommendation(self, result: BacktestResult) -> str:
        if result.sharpe_ratio > 1.5 and result.max_drawdown < 0.1:
            return "STRONG_BUY"
        elif result.sharpe_ratio > 1.0 and result.profit_factor > 1.3:
            return "BUY"
        elif result.sharpe_ratio < 0 or result.max_drawdown > 0.2:
            return "AVOID"
        return "NEUTRAL"

    def _empty_signal(self, reason: str) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "conviction": 0,
            "signal_type": "RESEARCH",
            "error": reason,
            "timestamp": datetime.utcnow().isoformat()
        }

    def get_backtest_history(self, limit: int = 10) -> List[Dict]:
        return [
            {
                "strategy": r.strategy,
                "sharpe": r.sharpe_ratio,
                "max_drawdown": r.max_drawdown,
                "profit_factor": r.profit_factor,
                "timestamp": r.timestamp.isoformat()
            }
            for r in self.backtest_history[-limit:]
        ]
