"""Exotic FX pairs must not be misclassified as CRYPTO via USDT substring."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.ai_scalping.broker_profile_store import (
    BrokerProfileStore,
    _default_path,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    classify_broker_symbol,
)
from app.domain.market_universe.classification import classify_instrument


@pytest.mark.unit
@pytest.mark.parametrize(
    ("symbol", "expected_scalp", "expected_product"),
    [
        ("USDTHB", "forex", "FOREX"),
        ("USDTRY", "forex", "FOREX"),
        ("USDZAR", "forex", "FOREX"),
        ("USDHKD", "forex", "FOREX"),
        ("EURUSD", "forex", "FOREX"),
        ("BTCUSD", "crypto", "CRYPTO"),
        ("ETHUSD", "crypto", "CRYPTO"),
        ("XRPUSDT", "crypto", "CRYPTO"),
    ],
)
def test_exotic_fx_not_crypto_via_usdt_substring(
    symbol: str, expected_scalp: str, expected_product: str
) -> None:
    assert classify_broker_symbol(symbol) == expected_scalp
    assert classify_instrument(symbol).asset_class == expected_product


@pytest.mark.unit
def test_broker_profile_prefers_railway_volume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    volume = tmp_path / "vol"
    volume.mkdir()
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    monkeypatch.delenv("QUANTFORG_BROKER_PROFILE_PATH", raising=False)
    monkeypatch.delenv("QUANTFORG_DATA_DIR", raising=False)
    path = _default_path()
    assert path == volume / "broker_runtime_profile.json"
    store = BrokerProfileStore(path=path)
    store.save(
        broker="weltrade",
        server="Weltrade-Real",
        login=12439799,
        user_id="7d31c808-1670-4604-867b-0d4a2bc9e078",
    )
    loaded = store.load()
    assert loaded is not None
    assert loaded.login == 12439799
    assert loaded.user_id is not None
