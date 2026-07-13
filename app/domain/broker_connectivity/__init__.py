"""Broker Connectivity Framework — domain package."""

from app.domain.broker_connectivity.matrix import (
    CAPABILITY_MATRIX,
    matrix_as_dicts,
    profile_for,
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
    "BrokerCapabilityProfile",
    "BrokerConnectivityPort",
    "ConnectivityCapability",
    "ConnectivityResult",
    "ConnectivityStatus",
    "matrix_as_dicts",
    "profile_for",
]
