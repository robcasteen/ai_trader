"""
TDD Test: Strategy Template System

Tests for creating, managing, and using strategy templates.

Templates allow users to:
1. Browse pre-built strategy configurations
2. Clone templates to create custom variations
3. Modify parameters without touching code
4. Enable/disable strategies for backtesting
5. Create entirely new strategies from scratch
"""

import pytest
from decimal import Decimal
from datetime import datetime

from app.database.models import StrategyDefinition
from app.database.repositories import StrategyDefinitionRepository


class TestStrategyTemplates:
    """Test strategy template system."""

    def test_create_strategy_from_template(self, db_session):
        """Test creating a strategy instance from a template."""
        repo = StrategyDefinitionRepository(db_session)

        # Create a template (is_template=True)
        template = repo.create(
            name="technical_conservative",
            version="1.0.0",
            enabled=False,  # Templates start disabled
            weight=Decimal("1.0"),
            parameters={
                "sma_period": 20,
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30
            },
            class_name="TechnicalStrategy",
            module_path="app.strategies.technical_strategy",
            is_template=True,  # Mark as template
            description="Conservative technical analysis with standard RSI/SMA settings",
            category="technical"
        )
        db_session.commit()

        assert template.is_template is True
        assert template.enabled is False
        assert template.description is not None
        assert template.category == "technical"

    def test_clone_template_to_active_strategy(self, db_session):
        """Test cloning a template to create an active strategy instance."""
        repo = StrategyDefinitionRepository(db_session)

        # Create template
        template = repo.create(
            name="volume_aggressive_template",
            version="1.0.0",
            enabled=False,
            weight=Decimal("1.5"),
            parameters={"volume_threshold": 1.5},
            class_name="VolumeStrategy",
            module_path="app.strategies.volume_strategy",
            is_template=True,
            description="Aggressive volume-based strategy",
            category="volume"
        )
        db_session.commit()

        # Clone template to active strategy
        cloned = repo.clone_template(
            template_id=template.id,
            new_name="my_volume_strategy",
            enabled=True,
            parameter_overrides={"volume_threshold": 2.0}  # Tweak parameter
        )
        db_session.commit()

        # Verify clone
        assert cloned.is_template is False
        assert cloned.enabled is True
        assert cloned.name == "my_volume_strategy"
        assert cloned.parameters["volume_threshold"] == 2.0
        assert cloned.weight == template.weight  # Inherited
        assert cloned.class_name == template.class_name  # Inherited
        assert cloned.parent_template_id == template.id  # Track lineage

    def test_list_all_templates(self, db_session):
        """Test getting all available templates."""
        repo = StrategyDefinitionRepository(db_session)

        # Create multiple templates
        repo.create(
            name="technical_conservative",
            version="1.0.0",
            enabled=False,
            weight=Decimal("1.0"),
            parameters={},
            is_template=True,
            description="Conservative technical",
            category="technical"
        )

        repo.create(
            name="technical_aggressive",
            version="1.0.0",
            enabled=False,
            weight=Decimal("2.0"),
            parameters={},
            is_template=True,
            description="Aggressive technical",
            category="technical"
        )

        repo.create(
            name="sentiment_baseline",
            version="1.0.0",
            enabled=False,
            weight=Decimal("1.0"),
            parameters={},
            is_template=True,
            description="Baseline sentiment",
            category="sentiment"
        )

        # Create active strategy (not template)
        repo.create(
            name="my_active_strategy",
            version="1.0.0",
            enabled=True,
            weight=Decimal("1.0"),
            parameters={},
            is_template=False
        )

        db_session.commit()

        # Get only templates
        templates = repo.get_all_templates()

        assert len(templates) == 3
        for template in templates:
            assert template.is_template is True

    def test_get_templates_by_category(self, db_session):
        """Test filtering templates by category."""
        repo = StrategyDefinitionRepository(db_session)

        # Create templates in different categories
        repo.create(
            name="tech1", version="1.0.0", enabled=False, weight=Decimal("1.0"),
            parameters={}, is_template=True, category="technical"
        )
        repo.create(
            name="tech2", version="1.0.0", enabled=False, weight=Decimal("1.0"),
            parameters={}, is_template=True, category="technical"
        )
        repo.create(
            name="sent1", version="1.0.0", enabled=False, weight=Decimal("1.0"),
            parameters={}, is_template=True, category="sentiment"
        )
        db_session.commit()

        # Filter by category
        tech_templates = repo.get_templates_by_category("technical")
        sent_templates = repo.get_templates_by_category("sentiment")

        assert len(tech_templates) == 2
        assert len(sent_templates) == 1

    def test_get_active_strategies_excludes_templates(self, db_session):
        """Test that get_all_enabled() excludes templates."""
        repo = StrategyDefinitionRepository(db_session)

        # Create template (enabled but is_template=True)
        repo.create(
            name="template1",
            version="1.0.0",
            enabled=True,  # Even if enabled
            weight=Decimal("1.0"),
            parameters={},
            is_template=True
        )

        # Create active strategy
        repo.create(
            name="active1",
            version="1.0.0",
            enabled=True,
            weight=Decimal("1.0"),
            parameters={},
            is_template=False
        )

        db_session.commit()

        # Get enabled strategies (should exclude templates)
        enabled = repo.get_all_enabled()

        assert len(enabled) == 1
        assert enabled[0].name == "active1"

    def test_update_strategy_parameters(self, db_session):
        """Test updating strategy parameters."""
        repo = StrategyDefinitionRepository(db_session)

        strategy = repo.create(
            name="my_strategy",
            version="1.0.0",
            enabled=True,
            weight=Decimal("1.0"),
            parameters={"threshold": 0.5},
            is_template=False
        )
        db_session.commit()

        # Update parameters
        repo.update_parameters(
            strategy_id=strategy.id,
            parameters={"threshold": 0.7, "new_param": 100}
        )
        db_session.commit()

        # Verify update
        updated = repo.get_by_id(strategy.id)
        assert updated.parameters["threshold"] == 0.7
        assert updated.parameters["new_param"] == 100

    def test_delete_strategy_but_not_template(self, db_session):
        """Test that deleting a cloned strategy doesn't delete the template."""
        repo = StrategyDefinitionRepository(db_session)

        # Create template
        template = repo.create(
            name="base_template",
            version="1.0.0",
            enabled=False,
            weight=Decimal("1.0"),
            parameters={},
            is_template=True
        )
        db_session.commit()

        # Clone it
        cloned = repo.clone_template(template.id, "cloned_strategy", enabled=True)
        db_session.commit()

        cloned_id = cloned.id

        # Delete cloned strategy
        repo.delete(cloned_id)
        db_session.commit()

        # Verify template still exists
        assert repo.get_by_id(template.id) is not None
        # Verify cloned is deleted
        assert repo.get_by_id(cloned_id) is None

    def test_create_strategy_with_validation_rules(self, db_session):
        """Test creating strategy with min_confidence and max_position_size."""
        repo = StrategyDefinitionRepository(db_session)

        strategy = repo.create(
            name="validated_strategy",
            version="1.0.0",
            enabled=True,
            weight=Decimal("1.0"),
            parameters={},
            is_template=False,
            min_confidence=Decimal("0.6"),  # Only trade with 60%+ confidence
            max_position_size=Decimal("0.05")  # Max 5% of portfolio
        )
        db_session.commit()

        assert strategy.min_confidence == Decimal("0.6")
        assert strategy.max_position_size == Decimal("0.05")

    def test_get_strategy_with_lineage(self, db_session):
        """Test getting strategy with its template lineage."""
        repo = StrategyDefinitionRepository(db_session)

        # Create template
        template = repo.create(
            name="parent_template",
            version="1.0.0",
            enabled=False,
            weight=Decimal("1.0"),
            parameters={"base_param": 10},
            is_template=True,
            description="Parent template"
        )
        db_session.commit()

        # Clone it
        child = repo.clone_template(template.id, "child_strategy", enabled=True)
        db_session.commit()

        # Get child with lineage
        child_with_parent = repo.get_with_lineage(child.id)

        assert child_with_parent.parent_template_id == template.id
        assert child_with_parent.parent_template.name == "parent_template"
        assert child_with_parent.parent_template.description == "Parent template"


class TestStrategyTemplateSeeding:
    """Test seeding default strategy templates."""

    def test_seed_default_templates(self, db_session):
        """Test seeding database with default strategy templates."""
        from app.database.seed_strategy_templates import seed_default_templates

        # Seed templates
        count = seed_default_templates(db_session)
        db_session.commit()

        assert count > 0

        # Verify templates exist
        repo = StrategyDefinitionRepository(db_session)
        templates = repo.get_all_templates()

        assert len(templates) >= 6  # At least 6 default templates

        # Verify categories
        categories = {t.category for t in templates}
        assert "technical" in categories
        assert "sentiment" in categories
        assert "volume" in categories

    def test_default_templates_have_descriptions(self, db_session):
        """Test that default templates have user-friendly descriptions."""
        from app.database.seed_strategy_templates import seed_default_templates

        seed_default_templates(db_session)
        db_session.commit()

        repo = StrategyDefinitionRepository(db_session)
        templates = repo.get_all_templates()

        for template in templates:
            assert template.description is not None
            assert len(template.description) > 10  # Meaningful description

    def test_templates_have_sensible_defaults(self, db_session):
        """Test that template parameters have sensible default values."""
        from app.database.seed_strategy_templates import seed_default_templates

        seed_default_templates(db_session)
        db_session.commit()

        repo = StrategyDefinitionRepository(db_session)
        templates = repo.get_all_templates()

        for template in templates:
            assert template.weight > 0
            assert template.version is not None
            assert template.class_name is not None
            assert template.module_path is not None


class TestStrategyTemplateUI:
    """Test UI-related functionality for strategy templates."""

    def test_get_template_summary_for_ui(self, db_session):
        """Test getting template data formatted for UI display."""
        repo = StrategyDefinitionRepository(db_session)

        template = repo.create(
            name="ui_test_template",
            version="1.0.0",
            enabled=False,
            weight=Decimal("1.5"),
            parameters={"param1": 10, "param2": "test"},
            is_template=True,
            description="Test template for UI",
            category="technical"
        )
        db_session.commit()

        # Get summary for UI
        summary = repo.get_template_summary(template.id)

        assert "id" in summary
        assert "name" in summary
        assert "description" in summary
        assert "category" in summary
        assert "weight" in summary
        assert "parameters" in summary
        assert "param_count" in summary

        assert summary["param_count"] == 2

    def test_get_all_strategies_for_backtest_ui(self, db_session):
        """
        Test getting strategies formatted for backtest UI checkboxes.

        Should return both templates and active strategies with metadata
        for UI rendering (checkboxes, descriptions, etc.).
        """
        repo = StrategyDefinitionRepository(db_session)

        # Create template
        repo.create(
            name="template1",
            version="1.0.0",
            enabled=False,
            weight=Decimal("1.0"),
            parameters={},
            is_template=True,
            description="Template 1",
            category="technical"
        )

        # Create active strategy
        repo.create(
            name="active1",
            version="1.0.0",
            enabled=True,
            weight=Decimal("1.5"),
            parameters={},
            is_template=False,
            description="Active strategy",
            category="volume"
        )

        db_session.commit()

        # Get all for UI
        strategies = repo.get_all_for_ui()

        assert len(strategies) == 2

        for strategy in strategies:
            assert "id" in strategy
            assert "name" in strategy
            assert "enabled" in strategy
            assert "is_template" in strategy
            assert "description" in strategy
            assert "category" in strategy
