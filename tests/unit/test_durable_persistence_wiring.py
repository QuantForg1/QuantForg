"""Unit tests for durable Postgres persistence factory wiring (no live DB)."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.config.environments import testing_settings
from core.config.settings import AppEnvironment, Settings


def test_testing_env_uses_memory_factories() -> None:
    from app.infrastructure.persistence.factory import build_persistence_factories
    from app.infrastructure.persistence.memory_ops import MemoryOpsUnitOfWorkFactory
    from app.infrastructure.persistence.memory_paper import MemoryPaperUnitOfWorkFactory

    settings = testing_settings()
    factories = build_persistence_factories(settings, MagicMock())
    assert isinstance(factories["ops_uow_factory"], MemoryOpsUnitOfWorkFactory)
    assert isinstance(factories["paper_uow_factory"], MemoryPaperUnitOfWorkFactory)
    assert factories["uow_factory"] is None


def test_durable_persistence_false_forces_memory() -> None:
    from app.infrastructure.persistence.factory import build_persistence_factories
    from app.infrastructure.persistence.memory_broker import (
        MemoryBrokerUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.memory_ops import MemoryOpsUnitOfWorkFactory

    settings = Settings(
        app_env=AppEnvironment.DEVELOPMENT,
        durable_persistence=False,
        _env_file=None,
    )
    factories = build_persistence_factories(settings, MagicMock())
    assert isinstance(factories["ops_uow_factory"], MemoryOpsUnitOfWorkFactory)
    assert isinstance(factories["broker_uow_factory"], MemoryBrokerUnitOfWorkFactory)


def test_postgres_factories_construct_with_mock_database() -> None:
    from app.infrastructure.persistence.postgres_backtest import (
        PostgresBacktestUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_broker import (
        PostgresBrokerUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_execution import (
        PostgresExecutionUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_mt5 import PostgresMT5UnitOfWorkFactory
    from app.infrastructure.persistence.postgres_ops import PostgresOpsUnitOfWorkFactory
    from app.infrastructure.persistence.postgres_paper import (
        PostgresPaperUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_platform import (
        PostgresPlatformUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_portfolio import (
        PostgresPortfolioUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_risk import (
        PostgresRiskUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_strategy import (
        PostgresStrategyUnitOfWorkFactory,
    )
    from app.infrastructure.persistence.postgres_walkforward import (
        PostgresWalkForwardUnitOfWorkFactory,
    )

    database = MagicMock()
    factories = [
        PostgresOpsUnitOfWorkFactory(database),
        PostgresPaperUnitOfWorkFactory(database),
        PostgresBacktestUnitOfWorkFactory(database),
        PostgresWalkForwardUnitOfWorkFactory(database),
        PostgresExecutionUnitOfWorkFactory(database),
        PostgresRiskUnitOfWorkFactory(database),
        PostgresStrategyUnitOfWorkFactory(database),
        PostgresPortfolioUnitOfWorkFactory(database),
        PostgresMT5UnitOfWorkFactory(database),
        PostgresBrokerUnitOfWorkFactory(database),
        PostgresPlatformUnitOfWorkFactory(database),
    ]
    for factory in factories:
        uow = factory()
        assert uow is not None
        assert getattr(uow, "_database", None) is database


def test_non_testing_durable_true_selects_postgres() -> None:
    from app.infrastructure.persistence.factory import build_persistence_factories
    from app.infrastructure.persistence.postgres_ops import PostgresOpsUnitOfWorkFactory
    from app.infrastructure.persistence.postgres_platform import (
        PostgresPlatformUnitOfWorkFactory,
    )

    settings = Settings(
        app_env=AppEnvironment.DEVELOPMENT,
        durable_persistence=True,
        _env_file=None,
    )
    factories = build_persistence_factories(settings, MagicMock())
    assert isinstance(factories["ops_uow_factory"], PostgresOpsUnitOfWorkFactory)
    assert isinstance(
        factories["platform_uow_factory"], PostgresPlatformUnitOfWorkFactory
    )
