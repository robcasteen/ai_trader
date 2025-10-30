"""
Performance metrics calculator for backtest results.
"""

import numpy as np
from typing import Dict, List, Any
from datetime import datetime


class PerformanceAnalyzer:
    """Calculate performance metrics from backtest results."""

    @staticmethod
    def calculate_metrics(results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive performance metrics.

        Args:
            results: Backtest results from BacktestEngine

        Returns:
            Dict with performance metrics
        """
        portfolio_values = results.get("portfolio_values", [])
        trades = results.get("trades", [])
        initial_capital = results.get("initial_capital", 0)

        if not portfolio_values:
            return {"error": "No portfolio value history"}

        # Extract value series
        values = [pv["total_value"] for pv in portfolio_values]
        timestamps = [pv["timestamp"] for pv in portfolio_values]

        # Calculate returns
        returns = np.diff(values) / values[:-1]

        # Total return
        total_return = (values[-1] - initial_capital) / initial_capital
        total_return_pct = total_return * 100

        # Annualized return
        days = (timestamps[-1] - timestamps[0]).days
        if days > 0:
            annualized_return = ((values[-1] / initial_capital) ** (365 / days)) - 1
            annualized_return_pct = annualized_return * 100
        else:
            annualized_return_pct = 0

        # Maximum drawdown
        cumulative_max = np.maximum.accumulate(values)
        drawdowns = (cumulative_max - values) / cumulative_max
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        max_drawdown_pct = max_drawdown * 100

        # Sharpe ratio (assuming 0% risk-free rate for simplicity)
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(365)
        else:
            sharpe_ratio = 0

        # Volatility (annualized)
        volatility = np.std(returns) * np.sqrt(365) if len(returns) > 0 else 0
        volatility_pct = volatility * 100

        # Win rate and trade stats
        buy_trades = [t for t in trades if t["action"] == "BUY"]
        sell_trades = [t for t in trades if t["action"] == "SELL"]

        profitable_trades = 0
        total_profit = 0
        total_loss = 0

        for sell in sell_trades:
            symbol = sell["symbol"]
            sell_time = sell["timestamp"]

            # Find corresponding buy
            buy = next(
                (b for b in reversed(buy_trades)
                 if b["symbol"] == symbol and b["timestamp"] < sell_time),
                None
            )

            if buy:
                profit = (sell["price"] - buy["price"]) * sell["amount"] - sell["fee"] - buy["fee"]
                if profit > 0:
                    profitable_trades += 1
                    total_profit += profit
                else:
                    total_loss += abs(profit)

        completed_trades = len(sell_trades)
        win_rate = (profitable_trades / completed_trades * 100) if completed_trades > 0 else 0

        # Profit factor
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0

        # Average trade
        avg_profit_per_trade = (total_profit - total_loss) / completed_trades if completed_trades > 0 else 0

        # Calculate Calmar ratio (return / max drawdown)
        calmar_ratio = annualized_return_pct / max_drawdown_pct if max_drawdown_pct > 0 else 0

        return {
            # Returns
            "total_return_pct": round(total_return_pct, 2),
            "annualized_return_pct": round(annualized_return_pct, 2),

            # Risk metrics
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "volatility_pct": round(volatility_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "calmar_ratio": round(calmar_ratio, 2),

            # Trade metrics
            "total_trades": len(trades),
            "completed_trades": completed_trades,
            "win_rate": round(win_rate, 2),
            "profitable_trades": profitable_trades,
            "losing_trades": completed_trades - profitable_trades,

            # P&L
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "net_profit": round(total_profit - total_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_profit_per_trade": round(avg_profit_per_trade, 2),

            # Portfolio
            "initial_capital": initial_capital,
            "final_value": round(values[-1], 2),
            "peak_value": round(max(values), 2),

            # Time period
            "backtest_days": days,
            "start_date": timestamps[0].strftime("%Y-%m-%d"),
            "end_date": timestamps[-1].strftime("%Y-%m-%d"),
        }

    @staticmethod
    def generate_report(results: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        """
        Generate a human-readable text report.

        Args:
            results: Backtest results
            metrics: Calculated metrics

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 70)
        report.append("BACKTEST PERFORMANCE REPORT")
        report.append("=" * 70)
        report.append("")

        # Configuration
        report.append("CONFIGURATION")
        report.append("-" * 70)
        report.append(f"Symbols:          {', '.join(results.get('symbols', []))}")
        report.append(f"Period:           {metrics['start_date']} to {metrics['end_date']} ({metrics['backtest_days']} days)")
        report.append(f"Interval:         {results.get('interval_minutes', 0)} minutes")
        report.append(f"Initial Capital:  ${metrics['initial_capital']:,.2f}")
        report.append("")

        # Returns
        report.append("RETURNS")
        report.append("-" * 70)
        report.append(f"Total Return:       {metrics['total_return_pct']:>8.2f}%")
        report.append(f"Annualized Return:  {metrics['annualized_return_pct']:>8.2f}%")
        report.append(f"Final Value:        ${metrics['final_value']:>10,.2f}")
        report.append(f"Peak Value:         ${metrics['peak_value']:>10,.2f}")
        report.append(f"Net Profit:         ${metrics['net_profit']:>10,.2f}")
        report.append("")

        # Risk Metrics
        report.append("RISK METRICS")
        report.append("-" * 70)
        report.append(f"Max Drawdown:       {metrics['max_drawdown_pct']:>8.2f}%")
        report.append(f"Volatility:         {metrics['volatility_pct']:>8.2f}%")
        report.append(f"Sharpe Ratio:       {metrics['sharpe_ratio']:>8.2f}")
        report.append(f"Calmar Ratio:       {metrics['calmar_ratio']:>8.2f}")
        report.append("")

        # Trade Statistics
        report.append("TRADE STATISTICS")
        report.append("-" * 70)
        report.append(f"Total Trades:       {metrics['total_trades']:>8}")
        report.append(f"Completed Trades:   {metrics['completed_trades']:>8}")
        report.append(f"Win Rate:           {metrics['win_rate']:>8.2f}%")
        report.append(f"Profitable Trades:  {metrics['profitable_trades']:>8}")
        report.append(f"Losing Trades:      {metrics['losing_trades']:>8}")
        report.append("")

        # P&L
        report.append("PROFIT & LOSS")
        report.append("-" * 70)
        report.append(f"Total Profit:       ${metrics['total_profit']:>10,.2f}")
        report.append(f"Total Loss:         ${metrics['total_loss']:>10,.2f}")
        report.append(f"Net Profit:         ${metrics['net_profit']:>10,.2f}")
        report.append(f"Profit Factor:      {metrics['profit_factor']:>10.2f}")
        report.append(f"Avg Per Trade:      ${metrics['avg_profit_per_trade']:>10,.2f}")
        report.append("")

        report.append("=" * 70)

        return "\n".join(report)
