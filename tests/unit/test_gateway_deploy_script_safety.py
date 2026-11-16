"""Static safety checks for the Windows gateway deploy script.

The script runs on the production Windows host, where CI cannot execute it.
These checks pin the safety properties that the owner review depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "deploy"
    / "mt5_gateway"
    / "deploy_main_gateway.ps1"
)


@pytest.fixture(scope="module")
def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_script_is_ascii_for_windows_powershell_5(source: str) -> None:
    assert source.isascii()


def test_deploys_an_exact_reviewed_sha(source: str) -> None:
    assert re.search(
        r"\[Parameter\(Mandatory = \$true\)\]\[string\]\$TargetSha", source
    )
    assert "^[0-9a-f]{40}$" in source
    assert "git checkout --detach $TargetSha" in source
    assert "$Commit -ne $TargetSha" in source


def test_never_pulls_a_moving_branch(source: str) -> None:
    assert "git pull" not in source
    assert "git checkout main" not in source


def test_refuses_dirty_tree_and_records_rollback_target(source: str) -> None:
    assert "git status --porcelain" in source
    assert "$PreviousCommit" in source


def test_refuses_to_restart_with_exposure(source: str) -> None:
    assert '/positions"' in source and '/orders"' in source
    assert source.count("Assert-Flat ") >= 2
    flat = source.index('Assert-Flat "pre-restart"')
    kill = source.index("taskkill")
    assert flat < kill


def test_verifies_the_broker_symbol_not_the_old_alias(source: str) -> None:
    assert "XAUUSD_I" not in source
    assert '[string]$Symbol = "XAUUSD"' in source


def test_reports_the_owner_limits_loaded(source: str) -> None:
    assert "owner_live_limits" in source


def test_hung_gateway_needs_explicit_terminal_confirmation(source: str) -> None:
    assert "[switch]$ConfirmFlatInTerminal" in source
    assert 'Read-Host "MT5 terminal Trade tab' in source
    assert '$answer -ne "FLAT"' in source
    # The override is only reachable from the catch branch (gateway silent),
    # never when the gateway reports exposure.
    catch = source.index("} catch {", source.index("function Assert-Flat"))
    exposure = source.index("open positions or pending orders exist")
    assert catch < source.index("ConfirmFlatInTerminal)", catch) < exposure
