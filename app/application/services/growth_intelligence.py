"""Read-only growth status for the designated platform owner.

The payload names sources that are actually wired. Missing integrations are
explicit statuses. This module does not query billing rows, Search Console,
ad accounts, or trading state, and it does not change any of them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.application.services.growth_automation import growth_automation_status
from app.domain.billing.plans import plans_public

_NOT_CONNECTED = "not_connected"
_UNAVAILABLE = "unavailable"
_STOPPED = "stopped"


def _metric(
    *,
    metric_id: str,
    label: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "label": label,
        "status": status,
        "value": None,
        "period": None,
        "fetched_at": None,
        "reason": reason,
    }


def growth_intelligence_status() -> dict[str, Any]:
    """Owner status document. ``value`` is null whenever a source is absent."""
    built_at = datetime.now(UTC).isoformat()
    catalog = plans_public()
    return {
        "read_only": True,
        "mutates_accounts": False,
        "places_orders": False,
        "ads_kill_switch": _STOPPED,
        "automation": growth_automation_status(),
        "status_document_built_at": built_at,
        "catalog": {
            "source": "app.domain.billing.plans.plans_public",
            "kind": "published_software_prices",
            "trial_offered": False,
            "automatic_renewal": False,
            "plans": catalog,
            "note": (
                "These are catalog prices for software access. "
                "They are not subscriber counts, revenue, or trading results."
            ),
        },
        "sections": [
            {
                "id": "seo",
                "title": "SEO performance",
                "status": _NOT_CONNECTED,
                "metrics": [
                    _metric(
                        metric_id="impressions",
                        label="Search impressions",
                        status=_NOT_CONNECTED,
                        reason="Google Search Console is not connected.",
                    ),
                    _metric(
                        metric_id="clicks",
                        label="Search clicks",
                        status=_NOT_CONNECTED,
                        reason="Google Search Console is not connected.",
                    ),
                    _metric(
                        metric_id="indexed_pages",
                        label="Indexed pages",
                        status=_NOT_CONNECTED,
                        reason=(
                            "A sitemap entry is not an indexed page. "
                            "Search Console is not connected."
                        ),
                    ),
                ],
            },
            {
                "id": "queries",
                "title": "Search queries",
                "status": _NOT_CONNECTED,
                "metrics": [
                    _metric(
                        metric_id="queries",
                        label="Queries",
                        status=_NOT_CONNECTED,
                        reason="Google Search Console is not connected.",
                    ),
                ],
            },
            {
                "id": "traffic",
                "title": "Organic traffic",
                "status": _NOT_CONNECTED,
                "metrics": [
                    _metric(
                        metric_id="sessions",
                        label="Organic sessions",
                        status=_NOT_CONNECTED,
                        reason="No analytics property is connected.",
                    ),
                ],
            },
            {
                "id": "content",
                "title": "Content performance",
                "status": _UNAVAILABLE,
                "metrics": [
                    _metric(
                        metric_id="landing_conversion",
                        label="Landing page conversion",
                        status=_UNAVAILABLE,
                        reason="No page-level analytics export is connected.",
                    ),
                ],
            },
            {
                "id": "subscriptions",
                "title": "Pricing and subscriptions",
                "status": _UNAVAILABLE,
                "metrics": [
                    _metric(
                        metric_id="paid_subscribers",
                        label="Paid subscribers",
                        status=_UNAVAILABLE,
                        reason=(
                            "This view does not query billing rows. "
                            "Catalog prices are listed separately and are not a count."
                        ),
                    ),
                    _metric(
                        metric_id="revenue",
                        label="Recurring revenue",
                        status=_UNAVAILABLE,
                        reason="No revenue aggregate is loaded.",
                    ),
                    _metric(
                        metric_id="churn",
                        label="Churn",
                        status=_UNAVAILABLE,
                        reason="No retention aggregate is loaded.",
                    ),
                ],
            },
            {
                "id": "funnel",
                "title": "Conversion funnel",
                "status": _UNAVAILABLE,
                "metrics": [
                    _metric(
                        metric_id="registrations",
                        label="Registrations",
                        status=_UNAVAILABLE,
                        reason="No registration aggregate is loaded.",
                    ),
                    _metric(
                        metric_id="activation",
                        label="Activation",
                        status=_UNAVAILABLE,
                        reason="No activation event aggregate is loaded.",
                    ),
                ],
            },
            {
                "id": "acquisition",
                "title": "Acquisition sources",
                "status": _NOT_CONNECTED,
                "metrics": [
                    _metric(
                        metric_id="channels",
                        label="Channel results",
                        status=_NOT_CONNECTED,
                        reason="No campaign or analytics source is connected.",
                    ),
                ],
            },
            {
                "id": "decision_evidence",
                "title": "Decision Evidence usage",
                "status": _UNAVAILABLE,
                "metrics": [
                    _metric(
                        metric_id="reports_viewed",
                        label="Decision reports viewed",
                        status=_UNAVAILABLE,
                        reason=(
                            "No usage event store is connected. "
                            "Opening a route is not recorded as a viewed report."
                        ),
                    ),
                ],
            },
            {
                "id": "automation",
                "title": "Growth automation",
                "status": _STOPPED,
                "metrics": [
                    _metric(
                        metric_id="scheduled_jobs",
                        label="Scheduled growth jobs",
                        status=_STOPPED,
                        reason=(
                            "No growth job is registered on the trading scheduler. "
                            "The emergency stop starts engaged. "
                            "A run while it is engaged does not execute."
                        ),
                    ),
                ],
            },
            {
                "id": "campaigns",
                "title": "Campaigns",
                "status": _STOPPED,
                "metrics": [
                    _metric(
                        metric_id="ads",
                        label="Paid advertising",
                        status=_STOPPED,
                        reason=(
                            "The ads kill switch is stopped. "
                            "No campaign is created or changed from this view."
                        ),
                    ),
                ],
            },
        ],
    }
