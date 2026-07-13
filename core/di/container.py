"""Application-scoped dependency injection container.

The container is constructed once during FastAPI lifespan startup and
torn down on shutdown. Presentation-layer dependency providers resolve
services from this container rather than constructing them inline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.config.settings import Settings
from core.database.session import DatabaseManager
from core.logging import get_logger

if TYPE_CHECKING:
    from app.infrastructure.cache.redis_client import RedisClient
    from app.infrastructure.supabase.client import SupabaseClient

logger = get_logger(__name__)


@dataclass
class Container:
    """Holds shared application dependencies for the process lifetime.

    Attributes
    ----------
    settings:
        Validated application configuration.
    database:
        Async database manager (engine + session factory).
    redis:
        Redis client wrapper, initialised during ``startup``.
    supabase:
        Supabase client wrapper, initialised during ``startup`` when configured.
    uow_factory:
        Unit of Work factory for identity profile persistence.
    """

    settings: Settings
    database: DatabaseManager
    redis: RedisClient | None = field(default=None, init=False)
    supabase: SupabaseClient | None = field(default=None, init=False)
    uow_factory: Any = field(default=None, init=False)
    platform_uow_factory: Any = field(default=None, init=False)
    broker_uow_factory: Any = field(default=None, init=False)
    broker_registry: Any = field(default=None, init=False)
    broker_health_monitor: Any = field(default=None, init=False)
    broker_reconnect_manager: Any = field(default=None, init=False)
    mt5_adapter: Any = field(default=None, init=False)
    mt5_uow_factory: Any = field(default=None, init=False)
    mt5_market_data: Any = field(default=None, init=False)
    mt5_order_validation: Any = field(default=None, init=False)
    execution_uow_factory: Any = field(default=None, init=False)
    execution_safety: Any = field(default=None, init=False)
    execution_gateway: Any = field(default=None, init=False)
    portfolio_uow_factory: Any = field(default=None, init=False)
    portfolio_sync: Any = field(default=None, init=False)
    risk_uow_factory: Any = field(default=None, init=False)
    risk_engine: Any = field(default=None, init=False)
    strategy_uow_factory: Any = field(default=None, init=False)
    strategy_runtime: Any = field(default=None, init=False)
    backtest_uow_factory: Any = field(default=None, init=False)
    backtest_engine: Any = field(default=None, init=False)
    paper_uow_factory: Any = field(default=None, init=False)
    paper_trading_engine: Any = field(default=None, init=False)
    walkforward_uow_factory: Any = field(default=None, init=False)
    walkforward_engine: Any = field(default=None, init=False)
    ops_uow_factory: Any = field(default=None, init=False)
    metrics_collector: Any = field(default=None, init=False)
    alerting_service: Any = field(default=None, init=False)

    async def startup(self) -> None:
        """Start managed infrastructure; optional deps fail soft with warnings."""
        try:
            await self.database.start()
        except Exception as exc:
            logger.warning("database_startup_failed", error=str(exc))

        from app.application.services.broker_health import (
            AutomaticReconnectManager,
            ConnectionHealthMonitor,
        )
        from app.infrastructure.brokers.placeholders import (
            register_placeholder_adapters,
        )
        from app.infrastructure.brokers.registry import BrokerRegistry
        from app.infrastructure.cache.redis_client import RedisClient
        from app.infrastructure.persistence.factory import build_persistence_factories

        if self.settings.redis_configured:
            self.redis = RedisClient(self.settings)
            try:
                await self.redis.connect()
            except Exception as exc:
                logger.warning("redis_startup_failed", error=str(exc))
                self.redis = None
        else:
            self.redis = None
            logger.info("redis_disabled", reason="REDIS_URL not configured")

        if self.settings.supabase_configured:
            try:
                from app.infrastructure.supabase.client import SupabaseClient

                self.supabase = SupabaseClient(self.settings)
                self.supabase.connect()
            except Exception as exc:
                logger.warning("supabase_startup_failed", error=str(exc))
                self.supabase = None

        try:
            persistence = build_persistence_factories(
                self.settings, self.database, supabase=self.supabase
            )
        except Exception as exc:
            logger.warning("persistence_factory_failed", error=str(exc))
            from app.infrastructure.persistence.memory_ops import (
                MemoryOpsUnitOfWorkFactory,
            )

            persistence = {"ops_uow_factory": MemoryOpsUnitOfWorkFactory()}

        self.platform_uow_factory = persistence.get("platform_uow_factory")
        self.broker_uow_factory = persistence.get("broker_uow_factory")
        self.mt5_uow_factory = persistence.get("mt5_uow_factory")
        self.execution_uow_factory = persistence.get("execution_uow_factory")
        self.portfolio_uow_factory = persistence.get("portfolio_uow_factory")
        self.risk_uow_factory = persistence.get("risk_uow_factory")
        self.strategy_uow_factory = persistence.get("strategy_uow_factory")
        self.backtest_uow_factory = persistence.get("backtest_uow_factory")
        self.paper_uow_factory = persistence.get("paper_uow_factory")
        self.walkforward_uow_factory = persistence.get("walkforward_uow_factory")
        self.ops_uow_factory = persistence.get("ops_uow_factory")
        if self.ops_uow_factory is None:
            from app.infrastructure.persistence.memory_ops import (
                MemoryOpsUnitOfWorkFactory,
            )

            self.ops_uow_factory = MemoryOpsUnitOfWorkFactory()
        if persistence.get("uow_factory") is not None:
            self.uow_factory = persistence["uow_factory"]

        self.broker_registry = BrokerRegistry()
        register_placeholder_adapters(self.broker_registry)
        self.broker_health_monitor = ConnectionHealthMonitor()
        self.broker_reconnect_manager = AutomaticReconnectManager()

        from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter

        execution_enabled = bool(self.settings.execution_enabled)
        try:
            if self.settings.mt5_enabled:
                client = MockMT5Client()
                if not self.settings.mt5_use_mock:
                    # Live MetaTrader5 package is Windows-only and optional.
                    # Sprint 1 defaults to mock; live client is a future enhancement.
                    client = MockMT5Client()
                self.mt5_adapter = MT5Adapter(
                    client=client, execution_enabled=execution_enabled
                )
                self.broker_registry.register(self.mt5_adapter)
            else:
                self.mt5_adapter = MT5Adapter(
                    client=MockMT5Client(), execution_enabled=execution_enabled
                )
        except Exception as exc:
            logger.warning("mt5_startup_failed", error=str(exc))
            self.mt5_adapter = MT5Adapter(
                client=MockMT5Client(), execution_enabled=False
            )

        from app.application.services.execution_gateway import ExecutionGateway
        from app.application.services.execution_safety import ExecutionSafetyService
        from app.application.services.mt5_market_data import MT5MarketDataService
        from app.application.services.mt5_order_validation import (
            MT5OrderValidationService,
        )
        from app.application.services.portfolio_sync import PortfolioSyncService
        from app.application.services.risk_engine import RiskEngine
        from app.application.services.strategy_runtime import StrategyRuntimeService
        from app.domain.entities.execution_safety import ExecutionPolicy
        from app.domain.entities.risk_engine import RiskEngineConfig
        from app.domain.entities.strategy_runtime import StrategyRuntimeConfig

        self.mt5_market_data = MT5MarketDataService(adapter=self.mt5_adapter)
        self.mt5_order_validation = MT5OrderValidationService(adapter=self.mt5_adapter)
        self.execution_safety = ExecutionSafetyService(
            adapter=self.mt5_adapter,
            order_validation=self.mt5_order_validation,
            policy=ExecutionPolicy(),
        )
        self.execution_gateway = ExecutionGateway(
            adapter=self.mt5_adapter,
            order_validation=self.mt5_order_validation,
        )
        self.portfolio_sync = PortfolioSyncService(adapter=self.mt5_adapter)
        self.risk_engine = RiskEngine(config=RiskEngineConfig())
        self.strategy_runtime = StrategyRuntimeService(
            market_data=self.mt5_market_data,
            portfolio_sync=self.portfolio_sync,
            risk_engine=self.risk_engine,
            config=StrategyRuntimeConfig(),
        )
        from app.application.services.backtest_engine import BacktestEngine
        from app.application.services.backtest_metrics import MetricsEngine

        self.backtest_engine = BacktestEngine(
            strategy_runtime=self.strategy_runtime,
            risk_engine=self.risk_engine,
            execution_safety=self.execution_safety,
            metrics_engine=MetricsEngine(),
        )
        from app.application.services.paper_market_listener import PaperMarketListener
        from app.application.services.paper_trading import PaperTradingEngine
        from app.application.services.virtual_broker import VirtualBroker
        from app.domain.entities.paper import PaperBrokerAssumptions

        self.paper_trading_engine = PaperTradingEngine(
            market_listener=PaperMarketListener(market_data=self.mt5_market_data),
            broker=VirtualBroker(assumptions=PaperBrokerAssumptions()),
        )
        from app.application.services.rolling_windows import RollingWindowScheduler
        from app.application.services.walkforward_engine import WalkForwardEngine
        from app.application.services.walkforward_robustness import RobustnessEngine

        self.walkforward_engine = WalkForwardEngine(
            backtest_engine=self.backtest_engine,
            window_scheduler=RollingWindowScheduler(),
            robustness_engine=RobustnessEngine(),
        )
        from app.application.services.alerting_service import AlertingService
        from app.application.services.metrics_collector import MetricsCollector

        self.metrics_collector = MetricsCollector()
        self.alerting_service = AlertingService(
            uow_factory=self.ops_uow_factory,
            metrics=self.metrics_collector,
        )
        logger.info(
            "container_startup_complete",
            env=self.settings.app_env.value,
            redis=self.redis is not None,
            supabase=self.supabase is not None,
            execution_enabled=bool(self.settings.execution_enabled),
        )

    async def shutdown(self) -> None:
        """Gracefully close all managed infrastructure connections."""
        self.uow_factory = None
        self.platform_uow_factory = None
        self.broker_uow_factory = None
        self.broker_registry = None
        self.broker_health_monitor = None
        self.broker_reconnect_manager = None
        self.mt5_adapter = None
        self.mt5_uow_factory = None
        self.mt5_market_data = None
        self.mt5_order_validation = None
        self.execution_uow_factory = None
        self.execution_safety = None
        self.execution_gateway = None
        self.portfolio_uow_factory = None
        self.portfolio_sync = None
        self.risk_uow_factory = None
        self.risk_engine = None
        self.strategy_uow_factory = None
        self.strategy_runtime = None
        self.backtest_uow_factory = None
        self.backtest_engine = None
        self.paper_uow_factory = None
        self.paper_trading_engine = None
        self.walkforward_uow_factory = None
        self.walkforward_engine = None
        self.ops_uow_factory = None
        self.metrics_collector = None
        self.alerting_service = None
        if self.supabase is not None:
            self.supabase.disconnect()
            self.supabase = None
        if self.redis is not None:
            await self.redis.disconnect()
            self.redis = None
        await self.database.stop()
        logger.info("container_shutdown_complete")

    def require_redis(self) -> RedisClient:
        """Return the Redis client or raise if not connected."""
        if self.redis is None:
            msg = "Redis client is not available"
            raise RuntimeError(msg)
        return self.redis

    def require_supabase(self) -> SupabaseClient:
        """Return the Supabase client or raise if not connected."""
        if self.supabase is None:
            msg = "Supabase client is not available"
            raise RuntimeError(msg)
        return self.supabase


_container: Container | None = None


def get_container() -> Container:
    """Return the process-wide DI container.

    Raises
    ------
    RuntimeError
        If the container has not been initialised.
    """
    if _container is None:
        msg = "DI container has not been initialised"
        raise RuntimeError(msg)
    return _container


def set_container(container: Container) -> None:
    """Register the process-wide DI container (called during lifespan)."""
    global _container
    _container = container
