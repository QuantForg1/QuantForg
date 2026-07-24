"""QuantForg Paper Trading Campaign Manager (QPTCM).

Governed paper-trading campaigns for certified strategies. Never places live
trades, modifies production, allocates capital, or auto-approves graduation.
Every lifecycle transition and graduation step requires explicit human approval.
"""

from __future__ import annotations

from app.domain.quantforg_paper_trading_campaign.platform import (
    QuantForgPaperTradingCampaignManager,
)

__all__ = ["QuantForgPaperTradingCampaignManager", "get_qptcm"]

_QPTCM: QuantForgPaperTradingCampaignManager | None = None


def get_qptcm() -> QuantForgPaperTradingCampaignManager:
    global _QPTCM
    if _QPTCM is None:
        _QPTCM = QuantForgPaperTradingCampaignManager()
    return _QPTCM
