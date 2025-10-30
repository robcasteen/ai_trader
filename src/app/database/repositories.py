"""
Data repositories for clean database access.

Repository pattern separates data access logic from business logic.
"""
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.database.models import (
    Signal, Trade, Holding, StrategyPerformance,
    StrategyDefinition, ErrorLog, RSSFeed, SeenNews, BotStatus
)


class SignalRepository:
    """Repository for Signal operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        timestamp: datetime,
        symbol: str,
        price: Decimal,
        final_signal: str,
        final_confidence: Decimal,
        aggregation_method: str,
        strategies: Dict,
        test_mode: bool = False,
        bot_version: str = "1.0.0",
        strategy_version: Optional[str] = None,
        signal_metadata: Optional[Dict] = None
    ) -> Signal:
        """Create a new signal."""
        signal = Signal(
            timestamp=timestamp,
            symbol=symbol,
            price=price,
            final_signal=final_signal,
            final_confidence=final_confidence,
            aggregation_method=aggregation_method,
            strategies=strategies,
            test_mode=test_mode,
            bot_version=bot_version,
            strategy_version=strategy_version,
            signal_metadata=signal_metadata
        )
        self.session.add(signal)
        self.session.flush()  # Get the ID without committing
        return signal

    def get_by_id(self, signal_id: int) -> Optional[Signal]:
        """Get signal by ID."""
        return self.session.query(Signal).filter(Signal.id == signal_id).first()

    def get_recent(
        self,
        hours: int = 24,
        test_mode: Optional[bool] = None,
        limit: int = 100
    ) -> List[Signal]:
        """Get recent signals."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = self.session.query(Signal).filter(Signal.timestamp >= cutoff)

        if test_mode is not None:
            query = query.filter(Signal.test_mode == test_mode)

        return query.order_by(Signal.timestamp.desc()).limit(limit).all()

    def get_by_symbol(
        self,
        symbol: str,
        hours: int = 24,
        test_mode: bool = False
    ) -> List[Signal]:
        """Get signals for a specific symbol."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.session.query(Signal)
            .filter(Signal.symbol == symbol)
            .filter(Signal.timestamp >= cutoff)
            .filter(Signal.test_mode == test_mode)
            .order_by(Signal.timestamp.desc())
            .all()
        )

    def get_non_hold_signals(
        self,
        hours: int = 24,
        test_mode: bool = False
    ) -> List[Signal]:
        """Get BUY/SELL signals (exclude HOLD)."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.session.query(Signal)
            .filter(Signal.final_signal != 'HOLD')
            .filter(Signal.timestamp >= cutoff)
            .filter(Signal.test_mode == test_mode)
            .order_by(Signal.timestamp.desc())
            .all()
        )

    def count_by_signal_type(
        self,
        hours: int = 24,
        test_mode: bool = False
    ) -> Dict[str, int]:
        """Count signals by type (BUY, SELL, HOLD)."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        results = (
            self.session.query(Signal.final_signal, func.count(Signal.id))
            .filter(Signal.timestamp >= cutoff)
            .filter(Signal.test_mode == test_mode)
            .group_by(Signal.final_signal)
            .all()
        )
        return {signal_type: count for signal_type, count in results}


class TradeRepository:
    """Repository for Trade operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        timestamp: datetime,
        action: str,
        symbol: str,
        price: Decimal,
        amount: Decimal,
        gross_value: Decimal,
        fee: Decimal,
        net_value: Decimal,
        signal_id: Optional[int] = None,
        strategies_used: Optional[List[str]] = None,
        test_mode: bool = False,
        bot_version: str = "1.0.0",
        reason: Optional[str] = None,
        balance_before: Optional[Decimal] = None,
        balance_after: Optional[Decimal] = None
    ) -> Trade:
        """Create a new trade."""
        trade = Trade(
            timestamp=timestamp,
            action=action,
            symbol=symbol,
            price=price,
            amount=amount,
            gross_value=gross_value,
            fee=fee,
            net_value=net_value,
            signal_id=signal_id,
            strategies_used=strategies_used or [],
            test_mode=test_mode,
            bot_version=bot_version,
            reason=reason,
            balance_before=balance_before,
            balance_after=balance_after
        )
        self.session.add(trade)
        self.session.flush()
        return trade

    def get_by_id(self, trade_id: int) -> Optional[Trade]:
        """Get trade by ID."""
        return self.session.query(Trade).filter(Trade.id == trade_id).first()

    def get_recent(
        self,
        hours: int = 24,
        test_mode: Optional[bool] = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get recent trades."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = self.session.query(Trade).filter(Trade.timestamp >= cutoff)

        if test_mode is not None:
            query = query.filter(Trade.test_mode == test_mode)

        return query.order_by(Trade.timestamp.desc()).limit(limit).all()

    def get_by_symbol(
        self,
        symbol: str,
        hours: int = 24,
        test_mode: bool = False
    ) -> List[Trade]:
        """Get trades for a specific symbol."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.session.query(Trade)
            .filter(Trade.symbol == symbol)
            .filter(Trade.timestamp >= cutoff)
            .filter(Trade.test_mode == test_mode)
            .order_by(Trade.timestamp.desc())
            .all()
        )

    def get_all(self, test_mode: bool = False, limit: int = 1000) -> List[Trade]:
        """Get all trades (with limit)."""
        return (
            self.session.query(Trade)
            .filter(Trade.test_mode == test_mode)
            .order_by(Trade.timestamp.desc())
            .limit(limit)
            .all()
        )

    def count_total(self, test_mode: bool = False) -> int:
        """Count total trades."""
        return self.session.query(Trade).filter(Trade.test_mode == test_mode).count()

    def get_win_loss_stats(
        self,
        hours: int = 24,
        test_mode: bool = False
    ) -> Dict[str, int]:
        """
        Calculate win/loss statistics.
        Note: Requires pairing buy/sell trades to determine P&L.
        """
        # TODO: Implement proper P&L calculation with buy/sell pairing
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        total = (
            self.session.query(Trade)
            .filter(Trade.timestamp >= cutoff)
            .filter(Trade.test_mode == test_mode)
            .count()
        )
        return {
            "total_trades": total,
            "wins": 0,  # TODO: Calculate from paired trades
            "losses": 0,  # TODO: Calculate from paired trades
            "win_rate": 0.0
        }


class HoldingRepository:
    """Repository for Holding operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        timestamp: datetime,
        symbol: str,
        amount: Decimal,
        avg_buy_price: Decimal,
        current_price: Optional[Decimal] = None,
        unrealized_pnl: Optional[Decimal] = None,
        entry_signal_id: Optional[int] = None,
        entry_trade_id: Optional[int] = None,
        test_mode: bool = False
    ) -> Holding:
        """Create a new holding snapshot."""
        holding = Holding(
            timestamp=timestamp,
            symbol=symbol,
            amount=amount,
            avg_buy_price=avg_buy_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            entry_signal_id=entry_signal_id,
            entry_trade_id=entry_trade_id,
            test_mode=test_mode
        )
        self.session.add(holding)
        self.session.flush()
        return holding

    def get_current_holdings(self, test_mode: bool = False) -> List[Holding]:
        """Get most recent holdings snapshot for each symbol."""
        # Get latest timestamp for each symbol
        subquery = (
            self.session.query(
                Holding.symbol,
                func.max(Holding.timestamp).label('max_timestamp')
            )
            .filter(Holding.test_mode == test_mode)
            .group_by(Holding.symbol)
            .subquery()
        )

        # Get holdings with latest timestamp
        return (
            self.session.query(Holding)
            .join(
                subquery,
                and_(
                    Holding.symbol == subquery.c.symbol,
                    Holding.timestamp == subquery.c.max_timestamp
                )
            )
            .filter(Holding.test_mode == test_mode)
            .filter(Holding.amount > 0)  # Only non-zero positions
            .all()
        )

    def get_history(
        self,
        symbol: str,
        hours: int = 24,
        test_mode: bool = False
    ) -> List[Holding]:
        """Get holding history for a symbol."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.session.query(Holding)
            .filter(Holding.symbol == symbol)
            .filter(Holding.timestamp >= cutoff)
            .filter(Holding.test_mode == test_mode)
            .order_by(Holding.timestamp.desc())
            .all()
        )


class PerformanceRepository:
    """Repository for performance analysis."""

    def __init__(self, session: Session):
        self.session = session

    def correlate_signals_to_trades(
        self,
        hours: int = 24,
        test_mode: bool = False,
        time_window_minutes: int = 10
    ) -> List[Dict]:
        """
        Correlate signals to trades within a time window.
        Returns list of {signal, trade, executed} dicts.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Get non-HOLD signals
        signals = (
            self.session.query(Signal)
            .filter(Signal.final_signal != 'HOLD')
            .filter(Signal.timestamp >= cutoff)
            .filter(Signal.test_mode == test_mode)
            .order_by(Signal.timestamp.desc())
            .all()
        )

        # Get trades in same period
        trades = (
            self.session.query(Trade)
            .filter(Trade.timestamp >= cutoff)
            .filter(Trade.test_mode == test_mode)
            .all()
        )

        # Correlate
        correlations = []
        for signal in signals:
            matched_trade = None

            # Find trade within time window
            for trade in trades:
                time_diff = abs((trade.timestamp - signal.timestamp).total_seconds() / 60)
                if (
                    trade.symbol == signal.symbol and
                    trade.action.upper() == signal.final_signal and
                    time_diff <= time_window_minutes
                ):
                    matched_trade = trade
                    break

            correlations.append({
                "signal": signal,
                "trade": matched_trade,
                "executed": matched_trade is not None
            })

        return correlations

    def get_strategy_performance(
        self,
        hours: int = 24,
        test_mode: bool = False
    ) -> Dict[str, Dict]:
        """Calculate performance metrics by strategy."""
        correlations = self.correlate_signals_to_trades(hours, test_mode)

        strategy_stats = {}
        for corr in correlations:
            signal = corr["signal"]
            strategies = signal.strategies or {}

            for strategy_name in strategies:
                if strategy_name not in strategy_stats:
                    strategy_stats[strategy_name] = {
                        "signals_generated": 0,
                        "signals_executed": 0,
                        "execution_rate": 0.0
                    }

                strategy_stats[strategy_name]["signals_generated"] += 1
                if corr["executed"]:
                    strategy_stats[strategy_name]["signals_executed"] += 1

        # Calculate rates
        for stats in strategy_stats.values():
            if stats["signals_generated"] > 0:
                stats["execution_rate"] = (
                    stats["signals_executed"] / stats["signals_generated"]
                )

        return strategy_stats


class RSSFeedRepository:
    """Repository for RSS Feed operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, url: str, name: str, enabled: bool = True, keywords: List[str] = None) -> RSSFeed:
        """Create a new RSS feed."""
        feed = RSSFeed(
            url=url,
            name=name,
            enabled=enabled,
            keywords=keywords or []
        )
        self.session.add(feed)
        self.session.flush()
        return feed

    def get_all(self, enabled_only: bool = False) -> List[RSSFeed]:
        """Get all RSS feeds."""
        query = self.session.query(RSSFeed)
        if enabled_only:
            query = query.filter(RSSFeed.enabled == True)
        return query.order_by(RSSFeed.name).all()

    def get_by_id(self, feed_id: int) -> Optional[RSSFeed]:
        """Get feed by ID."""
        return self.session.query(RSSFeed).filter(RSSFeed.id == feed_id).first()

    def get_by_url(self, url: str) -> Optional[RSSFeed]:
        """Get feed by URL."""
        return self.session.query(RSSFeed).filter(RSSFeed.url == url).first()

    def update(self, feed_id: int, **kwargs) -> Optional[RSSFeed]:
        """Update feed attributes."""
        feed = self.get_by_id(feed_id)
        if not feed:
            return None

        for key, value in kwargs.items():
            if hasattr(feed, key):
                setattr(feed, key, value)

        self.session.flush()
        return feed

    def delete(self, feed_id: int) -> bool:
        """Delete a feed."""
        feed = self.get_by_id(feed_id)
        if not feed:
            return False

        self.session.delete(feed)
        self.session.flush()
        return True

    def update_fetch_stats(self, feed_id: int, items_fetched: int, error: Optional[str] = None):
        """Update feed fetch statistics."""
        feed = self.get_by_id(feed_id)
        if not feed:
            return

        feed.last_fetch = datetime.now(timezone.utc).replace(tzinfo=None)
        feed.last_fetched = feed.last_fetch  # Alias
        feed.total_items_fetched = (feed.total_items_fetched or 0) + items_fetched

        if error:
            feed.error_count = (feed.error_count or 0) + 1
            feed.last_error = error
        else:
            feed.last_error = None

        self.session.flush()


class SeenNewsRepository:
    """Repository for SeenNews operations."""

    def __init__(self, session: Session):
        self.session = session

    def is_seen_by_url(self, url: str) -> bool:
        """Check if a news URL has been seen."""
        if not url:
            return False
        return self.session.query(SeenNews).filter(SeenNews.url == url).first() is not None

    def mark_seen(
        self,
        headline: str,
        url: str,
        feed_id: int,
        triggered_signal: bool = False,
        signal_id: Optional[int] = None
    ) -> SeenNews:
        """Mark a headline as seen."""
        # Check if already exists
        existing = self.session.query(SeenNews).filter(SeenNews.url == url).first()
        if existing:
            return existing

        seen = SeenNews(
            headline=headline,
            url=url,
            feed_id=feed_id,
            seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
            triggered_signal=triggered_signal,
            signal_id=signal_id
        )
        self.session.add(seen)
        self.session.flush()
        return seen

    def get_recent(self, hours: int = 24, limit: int = 100) -> List[SeenNews]:
        """Get recent seen news."""
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
        return (
            self.session.query(SeenNews)
            .filter(SeenNews.seen_at >= cutoff)
            .order_by(SeenNews.seen_at.desc())
            .limit(limit)
            .all()
        )


class BotConfigRepository:
    """Repository for Bot Configuration operations."""

    def __init__(self, session: Session):
        self.session = session

    def get_current(self) -> Optional[BotStatus]:
        """Get the current/latest bot configuration."""
        return self.session.query(BotStatus).order_by(BotStatus.timestamp.desc()).first()

    def create_or_update(
        self,
        mode: str = "paper",
        min_confidence: Optional[Decimal] = None,
        position_size: Optional[Decimal] = None,
        balance: Optional[Decimal] = None,
        **kwargs
    ) -> BotStatus:
        """Create or update bot configuration."""
        current = self.get_current()

        if current:
            # Update existing
            current.timestamp = datetime.utcnow()
            if mode is not None:
                current.mode = mode
            if min_confidence is not None:
                current.min_confidence = min_confidence
            if position_size is not None:
                current.position_size = position_size
            if balance is not None:
                current.balance = balance

            # Update any other fields
            for key, value in kwargs.items():
                if hasattr(current, key) and value is not None:
                    setattr(current, key, value)

            self.session.flush()
            return current
        else:
            # Create new
            config = BotStatus(
                timestamp=datetime.utcnow(),
                mode=mode,
                min_confidence=min_confidence or Decimal("0.5"),
                position_size=position_size or Decimal("5.0"),
                balance=balance,
                is_running=True,
                **kwargs
            )
            self.session.add(config)
            self.session.flush()
            return config

    def get_config_dict(self) -> Dict:
        """Get configuration as dictionary."""
        config = self.get_current()
        if not config:
            # Return defaults
            return {
                "mode": "paper",
                "min_confidence": 0.5,
                "position_size": 5.0,
                "aggregation_method": "weighted_vote",
                "strategy_weights": {
                    "sentiment": 1.0,
                    "technical": 1.0,
                    "volume": 0.8
                }
            }

        return {
            "mode": config.mode or "paper",
            "min_confidence": float(config.min_confidence) if config.min_confidence else 0.5,
            "position_size": float(config.position_size) if config.position_size else 5.0,
            "balance": float(config.balance) if config.balance else None,
            "aggregation_method": "weighted_vote",  # This could be added to BotStatus model
            "strategy_weights": {
                "sentiment": 1.0,
                "technical": 1.0,
                "volume": 0.8
            }
        }


def get_repositories(session: Session) -> Dict:
    """
    Get all repositories for a session.

    Usage:
        with get_db() as db:
            repos = get_repositories(db)
            signal = repos['signals'].create(...)
    """
    return {
        "signals": SignalRepository(session),
        "trades": TradeRepository(session),
        "holdings": HoldingRepository(session),
        "performance": PerformanceRepository(session),
        "feeds": RSSFeedRepository(session),
        "config": BotConfigRepository(session)
    }
