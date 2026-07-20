"""Persistence Unit-of-Work factory selection (memory vs durable Postgres)."""

from __future__ import annotations

from typing import Any

from app.infrastructure.persistence.memory_backtest import (
    MemoryBacktestUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_execution import (
    MemoryExecutionUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_execution_audit import (
    MemoryExecutionAuditUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.infrastructure.persistence.memory_ops import MemoryOpsUnitOfWorkFactory
from app.infrastructure.persistence.memory_paper import MemoryPaperUnitOfWorkFactory
from app.infrastructure.persistence.memory_platform import (
    MemoryPlatformUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_portfolio import (
    MemoryPortfolioUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_risk import MemoryRiskUnitOfWorkFactory
from app.infrastructure.persistence.memory_strategy import (
    MemoryStrategyUnitOfWorkFactory,
)
from app.infrastructure.persistence.memory_walkforward import (
    MemoryWalkForwardUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_backtest import (
    PostgresBacktestUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_broker import (
    PostgresBrokerUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_execution import (
    PostgresExecutionUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_execution_audit import (
    PostgresExecutionAuditUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_mt5 import PostgresMT5UnitOfWorkFactory
from app.infrastructure.persistence.postgres_ops import PostgresOpsUnitOfWorkFactory
from app.infrastructure.persistence.postgres_paper import PostgresPaperUnitOfWorkFactory
from app.infrastructure.persistence.postgres_platform import (
    PostgresPlatformUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_portfolio import (
    PostgresPortfolioUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_risk import PostgresRiskUnitOfWorkFactory
from app.infrastructure.persistence.postgres_strategy import (
    PostgresStrategyUnitOfWorkFactory,
)
from app.infrastructure.persistence.postgres_walkforward import (
    PostgresWalkForwardUnitOfWorkFactory,
)
from app.infrastructure.persistence.supabase_identity import (
    SupabaseIdentityUnitOfWorkFactory,
)


def build_persistence_factories(
    settings: Any,
    database: Any,
    supabase: Any = None,
) -> dict[str, Any]:
    """Return UoW factories for container wiring.

    Uses in-memory stores when ``settings.is_testing`` or durable persistence
    is disabled; otherwise binds Postgres factories to ``database``.
    """
    use_memory = bool(settings.is_testing) or not bool(
        getattr(settings, "durable_persistence", True)
    )

    if use_memory:
        factories: dict[str, Any] = {
            "platform_uow_factory": MemoryPlatformUnitOfWorkFactory(),
            "broker_uow_factory": MemoryBrokerUnitOfWorkFactory(),
            "mt5_uow_factory": MemoryMT5UnitOfWorkFactory(),
            "execution_uow_factory": MemoryExecutionUnitOfWorkFactory(),
            "execution_audit_uow_factory": MemoryExecutionAuditUnitOfWorkFactory(),
            "portfolio_uow_factory": MemoryPortfolioUnitOfWorkFactory(),
            "risk_uow_factory": MemoryRiskUnitOfWorkFactory(),
            "strategy_uow_factory": MemoryStrategyUnitOfWorkFactory(),
            "backtest_uow_factory": MemoryBacktestUnitOfWorkFactory(),
            "paper_uow_factory": MemoryPaperUnitOfWorkFactory(),
            "walkforward_uow_factory": MemoryWalkForwardUnitOfWorkFactory(),
            "ops_uow_factory": MemoryOpsUnitOfWorkFactory(),
            "uow_factory": None,
        }
    else:
        factories = {
            "platform_uow_factory": PostgresPlatformUnitOfWorkFactory(database),
            "broker_uow_factory": PostgresBrokerUnitOfWorkFactory(database),
            "mt5_uow_factory": PostgresMT5UnitOfWorkFactory(database),
            "execution_uow_factory": PostgresExecutionUnitOfWorkFactory(database),
            "execution_audit_uow_factory": PostgresExecutionAuditUnitOfWorkFactory(
                database
            ),
            "portfolio_uow_factory": PostgresPortfolioUnitOfWorkFactory(database),
            "risk_uow_factory": PostgresRiskUnitOfWorkFactory(database),
            "strategy_uow_factory": PostgresStrategyUnitOfWorkFactory(database),
            "backtest_uow_factory": PostgresBacktestUnitOfWorkFactory(database),
            "paper_uow_factory": PostgresPaperUnitOfWorkFactory(database),
            "walkforward_uow_factory": PostgresWalkForwardUnitOfWorkFactory(database),
            "ops_uow_factory": PostgresOpsUnitOfWorkFactory(database),
            "uow_factory": None,
        }

    if supabase is not None and bool(settings.supabase_configured):
        factories["uow_factory"] = SupabaseIdentityUnitOfWorkFactory(supabase=supabase)

    return factories
