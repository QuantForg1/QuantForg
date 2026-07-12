"""Domain interfaces (ports)."""

from app.domain.interfaces.app_info import AppInfoPort
from app.domain.interfaces.event_bus import (
    EventBusPort,
    EventDispatcherPort,
    EventPublisherPort,
    EventSubscriber,
)
from app.domain.interfaces.fair_value_gap import (
    FairValueGapRepositoryPort,
    OrderBlockSnapshotPort,
)
from app.domain.interfaces.health import HealthCheckPort
from app.domain.interfaces.liquidity import (
    LiquidityRepositoryPort,
    MarketStructurePort,
    PriceHistoryPort,
    SwingProviderPort,
)
from app.domain.interfaces.market_context import (
    CalendarPort,
    ClockPort,
    LiquidityProfilePort,
    SessionPort,
    VolatilityProfilePort,
)
from app.domain.interfaces.market_data import (
    MarketDataProviderPort,
    MarketDataStoragePort,
)
from app.domain.interfaces.market_structure import (
    PriceSeriesPort,
    StructureRepositoryPort,
    SwingDetectorPort,
    TrendAnalyzerPort,
)
from app.domain.interfaces.order_block import (
    LiquiditySnapshotPort,
    OrderBlockRepositoryPort,
)
from app.domain.interfaces.repositories import (
    AuditLogRepositoryPort,
    BrokerRepositoryPort,
    LicenseRepositoryPort,
    RiskProfileRepositoryPort,
    SignalRepositoryPort,
    SymbolRepositoryPort,
    TradingAccountRepositoryPort,
    TradingSessionRepositoryPort,
    UserRepositoryPort,
)
from app.domain.interfaces.repository import RepositoryPort
from app.domain.interfaces.time import TimeProviderPort
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkPort

__all__ = [
    "AppInfoPort",
    "AuditLogRepositoryPort",
    "BrokerRepositoryPort",
    "CalendarPort",
    "ClockPort",
    "EventBusPort",
    "EventDispatcherPort",
    "EventPublisherPort",
    "EventSubscriber",
    "FairValueGapRepositoryPort",
    "HealthCheckPort",
    "LicenseRepositoryPort",
    "LiquidityProfilePort",
    "LiquidityRepositoryPort",
    "LiquiditySnapshotPort",
    "MarketDataProviderPort",
    "MarketDataStoragePort",
    "MarketStructurePort",
    "OrderBlockRepositoryPort",
    "OrderBlockSnapshotPort",
    "PriceHistoryPort",
    "PriceSeriesPort",
    "RepositoryPort",
    "RiskProfileRepositoryPort",
    "SessionPort",
    "SignalRepositoryPort",
    "StructureRepositoryPort",
    "SwingDetectorPort",
    "SwingProviderPort",
    "SymbolRepositoryPort",
    "TimeProviderPort",
    "TradingAccountRepositoryPort",
    "TradingSessionRepositoryPort",
    "TrendAnalyzerPort",
    "UnitOfWorkFactory",
    "UnitOfWorkPort",
    "UserRepositoryPort",
    "VolatilityProfilePort",
]
