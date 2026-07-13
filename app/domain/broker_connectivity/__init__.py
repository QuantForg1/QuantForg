"""Broker Connectivity Framework — domain package."""

from app.domain.broker_connectivity.matrix import (
    CAPABILITY_MATRIX,
    matrix_as_dicts,
    profile_for,
)
from app.domain.broker_connectivity.mt5_ecosystem import (
    MT5_ECOSYSTEM,
    MT5BrokerProfile,
    ecosystem_as_dicts,
    match_broker_for_server,
    profile_by_slug,
)
from app.domain.broker_connectivity.port import BrokerConnectivityPort
from app.domain.broker_connectivity.types import (
    BrokerCapabilityProfile,
    ConnectivityCapability,
    ConnectivityResult,
    ConnectivityStatus,
)

__all__ = [
    "CAPABILITY_MATRIX",
    "MT5_ECOSYSTEM",
    "BrokerCapabilityProfile",
    "BrokerConnectivityPort",
    "ConnectivityCapability",
    "ConnectivityResult",
    "ConnectivityStatus",
    "MT5BrokerProfile",
    "ecosystem_as_dicts",
    "match_broker_for_server",
    "matrix_as_dicts",
    "profile_by_slug",
    "profile_for",
]
