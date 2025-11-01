"""
TDD Test: Strategy Telemetry System

Tests comprehensive signal telemetry to understand:
1. Why strategies trigger or don't trigger
2. Individual strategy contributions to final signal
3. Confidence distribution over time
4. Why signals don't execute (below threshold)
5. Context at signal time (price, volume, etc.)

This is Step 0 - Write the test FIRST to define what telemetry should look like.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from app.strategies.strategy_manager import StrategyManager
from app.database.models import StrategyDefinition


class TestStrategyTelemetry:
    """Test that strategy manager provides detailed telemetry for analysis."""

    def test_get_signal_returns_telemetry_object(self):
        """
        Test that get_signal returns detailed telemetry, not just (signal, confidence, reason).

        NEW BEHAVIOR:
        Instead of returning Tuple[str, float, str, int], return a dict with:
        - final_signal: "BUY"/"SELL"/"HOLD"
        - final_confidence: 0.0-1.0
        - final_reason: str
        - signal_id: int (from database)
        - telemetry: dict with detailed breakdown
        """
        manager = StrategyManager(config={})

        context = {
            "headlines": [{"title": "Bitcoin surges", "sentiment": "positive"}],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [64000 + i*10 for i in range(100)],
            "volume_history": [95 + i*0.5 for i in range(100)]
        }

        # Get signal with telemetry
        result = manager.get_signal_with_telemetry("BTCUSD", context)

        # Verify structure
        assert isinstance(result, dict)
        assert "final_signal" in result
        assert "final_confidence" in result
        assert "final_reason" in result
        assert "telemetry" in result

        # Verify telemetry exists
        telemetry = result["telemetry"]
        assert isinstance(telemetry, dict)

    def test_telemetry_includes_individual_strategy_votes(self):
        """Test that telemetry includes what each strategy voted."""
        manager = StrategyManager(config={})

        context = {
            "headlines": [{"title": "Bitcoin surges to new ATH", "sentiment": "positive"}],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [64000 + i*10 for i in range(100)],
            "volume_history": [95 + i*0.5 for i in range(100)]
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)
        telemetry = result["telemetry"]

        # Should have individual strategy votes
        assert "strategy_votes" in telemetry
        votes = telemetry["strategy_votes"]

        # Should be a list of dicts, one per strategy
        assert isinstance(votes, list)
        assert len(votes) > 0

        # Each vote should have strategy details
        for vote in votes:
            assert "strategy_name" in vote
            assert "signal" in vote  # BUY/SELL/HOLD
            assert "confidence" in vote  # 0.0-1.0
            assert "reason" in vote
            assert "weight" in vote
            assert "enabled" in vote

    def test_telemetry_includes_aggregation_breakdown(self):
        """Test that telemetry explains HOW the final signal was calculated."""
        manager = StrategyManager(config={"aggregation_method": "weighted_vote"})

        context = {
            "headlines": [{"title": "BTC positive news", "sentiment": "positive"}],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [64000 + i*10 for i in range(100)],
            "volume_history": [95 + i*0.5 for i in range(100)]
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)
        telemetry = result["telemetry"]

        # Should explain aggregation
        assert "aggregation" in telemetry
        agg = telemetry["aggregation"]

        assert "method" in agg  # "weighted_vote"
        assert "buy_score" in agg
        assert "sell_score" in agg
        assert "hold_score" in agg
        assert "total_weight" in agg

        # Scores should be numeric
        assert isinstance(agg["buy_score"], (int, float))
        assert isinstance(agg["sell_score"], (int, float))
        assert isinstance(agg["hold_score"], (int, float))

    def test_telemetry_includes_execution_decision(self):
        """Test that telemetry explains WHY signal executed or didn't execute."""
        manager = StrategyManager(config={"min_confidence": 0.5})

        context = {
            "headlines": [{"title": "Weak BTC signal", "sentiment": "slightly positive"}],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [65000] * 100,  # Flat price = low confidence
            "volume_history": [100] * 100
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)
        telemetry = result["telemetry"]

        # Should explain execution decision
        assert "execution" in telemetry
        exec_info = telemetry["execution"]

        assert "would_execute" in exec_info  # True/False
        assert "min_confidence_threshold" in exec_info  # 0.5
        assert "actual_confidence" in exec_info
        assert "reason" in exec_info  # Why it would/wouldn't execute

        # Verify calculation
        assert exec_info["min_confidence_threshold"] == 0.5
        assert exec_info["actual_confidence"] == result["final_confidence"]

        if result["final_confidence"] >= 0.5:
            assert exec_info["would_execute"] is True
            assert "meets threshold" in exec_info["reason"].lower()
        else:
            assert exec_info["would_execute"] is False
            assert "below threshold" in exec_info["reason"].lower()

    def test_telemetry_includes_market_context(self):
        """Test that telemetry captures market context at signal time."""
        manager = StrategyManager(config={})

        context = {
            "headlines": [{"title": "Test", "sentiment": "neutral"}],
            "price": 65432.10,
            "volume": 123.45,
            "price_history": [65000 + i*10 for i in range(100)],
            "volume_history": [100 + i for i in range(100)]
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)
        telemetry = result["telemetry"]

        # Should capture context
        assert "context" in telemetry
        ctx = telemetry["context"]

        assert "symbol" in ctx
        assert "price" in ctx
        assert "volume" in ctx
        assert "timestamp" in ctx
        assert "num_headlines" in ctx

        # Verify values
        assert ctx["symbol"] == "BTCUSD"
        assert ctx["price"] == 65432.10
        assert ctx["volume"] == 123.45
        assert ctx["num_headlines"] == 1
        assert isinstance(ctx["timestamp"], datetime)

    def test_telemetry_tracks_confidence_gaps(self):
        """
        Test that telemetry identifies 'near misses' - signals just below threshold.
        This helps identify if threshold is too high.
        """
        manager = StrategyManager(config={"min_confidence": 0.5})

        # Create context that generates confidence around 0.45 (near miss)
        context = {
            "headlines": [],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [65000 - i*2 for i in range(100)],  # Slight downtrend
            "volume_history": [100] * 100
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)
        telemetry = result["telemetry"]

        exec_info = telemetry["execution"]

        # Should identify near miss
        if not exec_info["would_execute"]:
            gap = exec_info["min_confidence_threshold"] - exec_info["actual_confidence"]

            assert "confidence_gap" in exec_info
            assert exec_info["confidence_gap"] == pytest.approx(gap, abs=0.01)

            # If gap is small, should flag as near miss
            if gap < 0.1:
                assert exec_info.get("near_miss", False) is True

    def test_telemetry_includes_strategy_attribution(self):
        """
        Test that telemetry attributes final signal to contributing strategies.
        Helps answer: "Which strategy was responsible for this signal?"
        """
        manager = StrategyManager(config={})

        context = {
            "headlines": [{"title": "Bitcoin explodes higher!", "sentiment": "very positive"}],
            "price": 70000.0,
            "volume": 200.0,
            "price_history": [60000 + i*100 for i in range(100)],  # Strong uptrend
            "volume_history": [150 + i for i in range(100)]
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)
        telemetry = result["telemetry"]

        # Should attribute signal to strategies
        assert "attribution" in telemetry
        attr = telemetry["attribution"]

        # Should show which strategies agreed with final signal
        assert "agreeing_strategies" in attr  # List of strategy names that voted for final signal
        assert "disagreeing_strategies" in attr  # List that voted differently

        assert isinstance(attr["agreeing_strategies"], list)
        assert isinstance(attr["disagreeing_strategies"], list)

        # Should show contribution percentages
        assert "contribution_by_strategy" in attr
        contributions = attr["contribution_by_strategy"]

        # Should be dict of {strategy_name: percentage}
        assert isinstance(contributions, dict)
        for strategy_name, pct in contributions.items():
            assert 0.0 <= pct <= 100.0

    def test_telemetry_json_serializable(self):
        """Test that telemetry can be JSON serialized for storage."""
        import json

        manager = StrategyManager(config={})

        context = {
            "headlines": [{"title": "Test", "sentiment": "neutral"}],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [65000] * 100,
            "volume_history": [100] * 100
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)

        # Should be JSON serializable
        try:
            json_str = json.dumps(result, default=str)  # Use default=str for datetime
            assert len(json_str) > 0

            # Should be able to deserialize
            deserialized = json.loads(json_str)
            assert deserialized["final_signal"] == result["final_signal"]
        except (TypeError, ValueError) as e:
            pytest.fail(f"Telemetry not JSON serializable: {e}")

    def test_telemetry_backward_compatible_with_old_get_signal(self):
        """
        Test that existing get_signal() method still works (backward compatibility).
        Old code should not break.
        """
        manager = StrategyManager(config={})

        context = {
            "headlines": [],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [65000] * 100,
            "volume_history": [100] * 100
        }

        # Old method should still work
        signal, confidence, reason, signal_id = manager.get_signal("BTCUSD", context)

        assert signal in ["BUY", "SELL", "HOLD"]
        assert 0.0 <= confidence <= 1.0
        assert isinstance(reason, str)
        assert signal_id is None or isinstance(signal_id, int)

    def test_telemetry_stores_to_database(self, db_session):
        """Test that telemetry is stored to database for historical analysis."""
        manager = StrategyManager(config={}, db_session=db_session)

        context = {
            "headlines": [{"title": "Test headline", "sentiment": "positive"}],
            "price": 65000.0,
            "volume": 100.0,
            "price_history": [65000] * 100,
            "volume_history": [100] * 100
        }

        result = manager.get_signal_with_telemetry("BTCUSD", context)

        # Should have database ID
        assert "signal_id" in result
        assert result["signal_id"] is not None

        # Should be able to query it from database
        from app.database.repositories import StrategySignalRepository
        from app.database.models import StrategySignal

        repo = StrategySignalRepository(db_session)
        signal = db_session.query(StrategySignal).filter(
            StrategySignal.id == result["signal_id"]
        ).first()

        assert signal is not None
        assert signal.symbol == "BTCUSD"
        assert signal.final_signal == result["final_signal"]

        # Should have telemetry stored as JSON
        assert signal.telemetry is not None
        assert "strategy_votes" in signal.telemetry


class TestTelemetryAnalysisTools:
    """Test tools for analyzing telemetry data."""

    def test_get_telemetry_summary_for_symbol(self, db_session):
        """Test getting telemetry summary for a specific symbol."""
        from app.telemetry import get_telemetry_summary

        # Generate some signals
        manager = StrategyManager(config={}, db_session=db_session)

        for i in range(10):
            context = {
                "headlines": [],
                "price": 65000.0 + i*100,
                "volume": 100.0,
                "price_history": [65000] * 100,
                "volume_history": [100] * 100
            }
            manager.get_signal_with_telemetry("BTCUSD", context)

        # Get summary
        summary = get_telemetry_summary(db_session, symbol="BTCUSD", limit=10)

        assert "total_signals" in summary
        assert summary["total_signals"] == 10
        assert "avg_confidence" in summary
        assert "signal_distribution" in summary  # {BUY: X, SELL: Y, HOLD: Z}
        assert "avg_confidence_by_signal" in summary
        assert "strategy_vote_distribution" in summary

    def test_get_near_miss_signals(self, db_session):
        """Test querying signals that were just below threshold (near misses)."""
        from app.telemetry import get_near_miss_signals

        # Generate signals with varying confidence
        manager = StrategyManager(config={"min_confidence": 0.5}, db_session=db_session)

        # Create some near misses (0.45-0.49 confidence)
        for i in range(5):
            context = {
                "headlines": [],
                "price": 65000.0,
                "volume": 100.0,
                "price_history": [65000 - i for i in range(100)],
                "volume_history": [100] * 100
            }
            manager.get_signal_with_telemetry("BTCUSD", context)

        # Get near misses
        near_misses = get_near_miss_signals(
            db_session,
            threshold=0.5,
            tolerance=0.1,  # Within 0.1 of threshold
            limit=10
        )

        # Should return list of signals
        assert isinstance(near_misses, list)

        # Each should be close to threshold
        for signal in near_misses:
            gap = abs(signal["final_confidence"] - 0.5)
            assert gap <= 0.1

    def test_get_strategy_win_rates(self, db_session):
        """
        Test calculating win rates per strategy.
        Requires linking signals to trade outcomes.
        """
        from app.telemetry import get_strategy_win_rates

        # This would require:
        # 1. Generate signals
        # 2. Execute trades based on signals
        # 3. Track trade outcomes (win/loss)
        # 4. Calculate which strategies contributed to winners

        win_rates = get_strategy_win_rates(db_session, days_back=7)

        assert isinstance(win_rates, dict)
        # {strategy_name: {wins: X, losses: Y, win_rate: Z}}

        for strategy_name, stats in win_rates.items():
            assert "wins" in stats
            assert "losses" in stats
            assert "win_rate" in stats
            assert 0.0 <= stats["win_rate"] <= 1.0
