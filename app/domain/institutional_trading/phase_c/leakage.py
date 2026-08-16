"""Strict time-series validation / leakage detection — research only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class LeakageFinding:
    code: str
    severity: str  # BLOCK | WARN
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity, "detail": self.detail}


def check_time_splits(
    *,
    train_end: Any = None,
    validation_end: Any = None,
    oos_start: Any = None,
    train_indices: Sequence[int] | None = None,
    validation_indices: Sequence[int] | None = None,
    oos_indices: Sequence[int] | None = None,
    label_end_indices: Sequence[int] | None = None,
    feature_end_indices: Sequence[int] | None = None,
    embargo_bars: int = 0,
) -> dict[str, Any]:
    """Detect look-ahead / overlap / contamination. Never fabricates a pass."""
    findings: list[LeakageFinding] = []

    def _ts(x: Any) -> str | None:
        return None if x is None else str(x)

    te, ve, os_ = _ts(train_end), _ts(validation_end), _ts(oos_start)
    if te and ve and te > ve:
        findings.append(
            LeakageFinding(
                "TRAIN_AFTER_VALIDATION",
                "BLOCK",
                "train_end is after validation_end",
            )
        )
    if ve and os_ and ve > os_:
        findings.append(
            LeakageFinding(
                "VALIDATION_AFTER_OOS",
                "BLOCK",
                "validation_end is after oos_start — future leakage risk",
            )
        )
    if te and os_ and te > os_:
        findings.append(
            LeakageFinding(
                "TRAIN_AFTER_OOS",
                "BLOCK",
                "train_end is after oos_start",
            )
        )

    train_set = set(train_indices or ())
    val_set = set(validation_indices or ())
    oos_set = set(oos_indices or ())
    if train_set & val_set:
        findings.append(
            LeakageFinding(
                "OVERLAPPING_TRAIN_VAL",
                "BLOCK",
                f"overlap={len(train_set & val_set)} indices",
            )
        )
    if train_set & oos_set:
        findings.append(
            LeakageFinding(
                "OVERLAPPING_TRAIN_OOS",
                "BLOCK",
                f"overlap={len(train_set & oos_set)} indices",
            )
        )
    if val_set & oos_set:
        findings.append(
            LeakageFinding(
                "OVERLAPPING_VAL_OOS",
                "BLOCK",
                f"overlap={len(val_set & oos_set)} indices",
            )
        )

    # Feature / label leakage: feature end must not exceed label end for same event
    if label_end_indices and feature_end_indices:
        n = min(len(label_end_indices), len(feature_end_indices))
        leaks = sum(
            1
            for i in range(n)
            if int(feature_end_indices[i]) > int(label_end_indices[i])
        )
        if leaks:
            findings.append(
                LeakageFinding(
                    "FEATURE_LABEL_LOOKAHEAD",
                    "BLOCK",
                    f"{leaks} events have features after label end",
                )
            )

    # Embargo: train max + embargo must be < oos min when both provided
    if train_set and oos_set and embargo_bars > 0:
        if max(train_set) + embargo_bars >= min(oos_set):
            findings.append(
                LeakageFinding(
                    "EMBARGO_VIOLATION",
                    "BLOCK",
                    "purged/embargoed gap insufficient between train and OOS",
                )
            )

    if not any(
        [
            te,
            ve,
            os_,
            train_indices,
            validation_indices,
            oos_indices,
            label_end_indices,
            feature_end_indices,
        ]
    ):
        findings.append(
            LeakageFinding(
                "INSUFFICIENT_SPLIT_METADATA",
                "WARN",
                "no split metadata provided — cannot certify OOS",
            )
        )

    blocked = any(f.severity == "BLOCK" for f in findings)
    return {
        "ok": not blocked,
        "oos_certified": not blocked
        and bool(oos_indices or os_)
        and not any(f.code == "INSUFFICIENT_SPLIT_METADATA" for f in findings),
        "findings": [f.to_dict() for f in findings],
        "protocol": "TRAIN→VALIDATION→OUT_OF_SAMPLE",
        "purged_embargo_bars": int(embargo_bars),
    }
