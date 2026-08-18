"""
Risk Manager — Portfolio risk monitoring and position limits
Enforces hard limits and dynamic risk adjustment
"""
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_drawdown: float = 0.15
    max_position_size: float = 0.25
    max_leverage: float = 2.0
    max_daily_loss: float = 0.05
    max_sector_exposure: float = 0.40
    max_correlation_exposure: float = 0.60
    var_limit: float = 0.02
    stop_loss_per_position: float = 0.03
    max_open_orders: int = 50
    max_orders_per_symbol: int = 5


@dataclass
class RiskMetrics:
    portfolio_value: float
    daily_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    max_drawdown: float
    current_drawdown: float
    var_95: float
    sharpe_ratio: float
    exposure_by_asset: Dict[str, float]
    greeks_exposure: Dict[str, float]
    risk_score: float
    risk_level: str
    violations: List[str]
    ts: datetime


class RiskManager:
    """Real-time risk management and position monitoring"""

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.peak_value = 0
        self.daily_start_value = 0
        self.pnl_history: List[float] = []
        self.position_history: List[dict] = []
        self.violations: List[str] = []
        self.halt_triggered = False

    def check_order(
        self,
        order: dict,
        current_positions: dict,
        portfolio_value: float
    ) -> tuple:
        """Check if order is within risk limits"""
        violations = []

        position_size = order.get("quantity", 0) * order.get("price", 0)
        position_pct = position_size / portfolio_value if portfolio_value > 0 else 0

        if position_pct > self.limits.max_position_size:
            violations.append(f"Position size {position_pct:.2%} exceeds limit {self.limits.max_position_size:.2%}")

        symbol = order.get("symbol", "")
        current_exposure = sum(
            abs(p.get("quantity", 0) * p.get("price", 0))
            for s, p in current_positions.items()
            if s == symbol
        )
        new_exposure = (current_exposure + position_size) / portfolio_value
        if new_exposure > self.limits.max_position_size:
            violations.append(f"Total exposure to {symbol} would be {new_exposure:.2%}")

        total_exposure = sum(
            abs(p.get("quantity", 0) * p.get("price", 0))
            for p in current_positions.values()
        )
        new_total = (total_exposure + position_size) / portfolio_value
        if new_total > self.limits.max_leverage:
            violations.append(f"Leverage {new_total:.2f}x exceeds limit {self.limits.max_leverage:.2f}x")

        if order.get("stop_loss"):
            stop_distance = abs(order["price"] - order["stop_loss"]) / order["price"]
            if stop_distance > self.limits.stop_loss_per_position:
                violations.append(f"Stop loss distance {stop_distance:.2%} exceeds limit")

        return (len(violations) == 0, violations)

    def update_portfolio(self, portfolio_value: float, positions: dict, greeks: dict):
        """Update portfolio state and calculate risk metrics"""
        self.pnl_history.append(portfolio_value)

        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value

        if self.daily_start_value == 0:
            self.daily_start_value = portfolio_value

        current_drawdown = (self.peak_value - portfolio_value) / self.peak_value if self.peak_value > 0 else 0
        daily_pnl = (portfolio_value - self.daily_start_value) / self.daily_start_value if self.daily_start_value > 0 else 0

        var_95 = self._calculate_var()
        sharpe = self._calculate_sharpe()
        exposure = self._calculate_exposure(positions, portfolio_value)
        greeks_exposure = self._calculate_greeks_exposure(greeks)
        risk_score = self._calculate_risk_score(
            current_drawdown, daily_pnl, var_95, exposure, greeks_exposure
        )

        violations = self._check_violations(
            current_drawdown, daily_pnl, var_95, exposure, positions, portfolio_value
        )

        return RiskMetrics(
            portfolio_value=portfolio_value,
            daily_pnl=daily_pnl,
            unrealized_pnl=0,
            realized_pnl=0,
            max_drawdown=(self.peak_value - portfolio_value) / self.peak_value if self.peak_value > 0 else 0,
            current_drawdown=current_drawdown,
            var_95=var_95,
            sharpe_ratio=sharpe,
            exposure_by_asset=exposure,
            greeks_exposure=greeks_exposure,
            risk_score=risk_score,
            risk_level=self._risk_level(risk_score),
            violations=violations,
            ts=datetime.utcnow()
        )

    def _calculate_var(self) -> float:
        """Calculate 95% Value at Risk"""
        if len(self.pnl_history) < 20:
            return 0.0

        returns = np.diff(self.pnl_history[-252:]) / self.pnl_history[-252:-1]
        returns = returns[~np.isnan(returns)]

        if len(returns) < 20:
            return 0.0

        return float(-np.percentile(returns, 5))

    def _calculate_sharpe(self) -> float:
        """Calculate rolling Sharpe ratio"""
        if len(self.pnl_history) < 20:
            return 0.0

        returns = np.diff(self.pnl_history[-252:]) / self.pnl_history[-252:-1]
        returns = returns[~np.isnan(returns)]

        if len(returns) < 20 or np.std(returns) == 0:
            return 0.0

        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))

    def _calculate_exposure(self, positions: dict, portfolio_value: float) -> dict:
        """Calculate exposure by asset"""
        if portfolio_value == 0:
            return {}

        exposure = {}
        for symbol, pos in positions.items():
            pos_value = abs(pos.get("quantity", 0) * pos.get("price", 0))
            exposure[symbol] = pos_value / portfolio_value

        return exposure

    def _calculate_greeks_exposure(self, greeks: dict) -> dict:
        """Calculate aggregate Greeks exposure"""
        return {
            "delta": greeks.get("delta", 0),
            "gamma": greeks.get("gamma", 0),
            "vega": greeks.get("vega", 0),
            "theta": greeks.get("theta", 0)
        }

    def _calculate_risk_score(
        self,
        drawdown: float,
        daily_pnl: float,
        var_95: float,
        exposure: dict,
        greeks: dict
    ) -> float:
        """Calculate overall risk score (0-100)"""
        score = 0

        drawdown_score = min(100, drawdown / self.limits.max_drawdown * 100)
        score += drawdown_score * 0.25

        pnl_score = min(100, abs(daily_pnl) / self.limits.max_daily_loss * 100)
        score += pnl_score * 0.25

        var_score = min(100, var_95 / self.limits.var_limit * 100)
        score += var_score * 0.20

        max_exposure = max(exposure.values()) if exposure else 0
        exposure_score = min(100, max_exposure / self.limits.max_position_size * 100)
        score += exposure_score * 0.15

        greek_risk = abs(greeks.get("gamma", 0)) * 100 + abs(greeks.get("vega", 0)) * 50
        greek_score = min(100, greek_risk)
        score += greek_score * 0.15

        return min(100, score)

    def _risk_level(self, score: float) -> str:
        """Map risk score to level"""
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 40:
            return "MODERATE"
        elif score >= 20:
            return "LOW"
        return "MINIMAL"

    def _check_violations(
        self,
        drawdown: float,
        daily_pnl: float,
        var_95: float,
        exposure: dict,
        positions: dict,
        portfolio_value: float
    ) -> List[str]:
        """Check for risk limit violations"""
        violations = []

        if drawdown > self.limits.max_drawdown:
            violations.append(f"Drawdown {drawdown:.2%} exceeds limit {self.limits.max_drawdown:.2%}")

        if abs(daily_pnl) > self.limits.max_daily_loss:
            violations.append(f"Daily PnL {daily_pnl:.2%} exceeds limit {self.limits.max_daily_loss:.2%}")

        if var_95 > self.limits.var_limit:
            violations.append(f"VaR {var_95:.2%} exceeds limit {self.limits.var_limit:.2%}")

        for symbol, exp in exposure.items():
            if exp > self.limits.max_position_size:
                violations.append(f"Exposure to {symbol} ({exp:.2%}) exceeds limit")

        total_exposure = sum(exposure.values())
        if total_exposure > self.limits.max_leverage:
            violations.append(f"Total leverage {total_exposure:.2f}x exceeds limit")

        if violations:
            self.halt_triggered = True
            self.violations.extend(violations)

        return violations

    def should_halt(self) -> tuple:
        """Check if trading should be halted"""
        if self.halt_triggered:
            return True, "Risk limits breached - trading halted"

        if len(self.pnl_history) >= 2:
            recent_pnl = self.pnl_history[-1] - self.pnl_history[-2]
            if len(self.pnl_history) >= 3:
                prev_pnl = self.pnl_history[-2] - self.pnl_history[-3]
                if recent_pnl < 0 and prev_pnl < 0:
                    return True, "Consecutive daily losses - trading halted"

        return False, ""

    def reset_daily(self):
        """Reset daily risk tracking"""
        if self.pnl_history:
            self.daily_start_value = self.pnl_history[-1]
        self.halt_triggered = False
