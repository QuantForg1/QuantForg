"""Trade Replay Studio — step through completed trade timeline."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.performance_lab.config import DEFAULT_LAB_CONFIG
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReplayFrame:
    index: int
    label: str
    at: str
    detail: str
    price: float | None = None
    stop: float | None = None
    tp: float | None = None
    trail: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TradeReplay:
    id: str
    ticket: str | None
    symbol: str
    direction: str
    created_at: str
    market_snapshot: dict[str, Any]
    structure: dict[str, Any]
    liquidity: dict[str, Any]
    bos: str | None
    choch: str | None
    fvg: str | None
    order_blocks: list[str]
    ai_reasoning: str
    entry: float | None
    exit: float | None
    sl: float | None
    tp: float | None
    frames: list[ReplayFrame] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["frames"] = [f.to_dict() if hasattr(f, "to_dict") else f for f in self.frames]
        return d


def build_replay_from_decision(
    *,
    decision: Any,
    snapshot: Any | None = None,
    ticket: str | None = None,
    entry: float | None = None,
    exit_price: float | None = None,
    explanation: str | None = None,
    trail_events: list[dict[str, Any]] | None = None,
) -> TradeReplay:
    stop = getattr(decision, "stop_zone", None)
    target = getattr(decision, "target_zone", None)
    entry_zone = getattr(decision, "entry_zone", None)
    sl = float(getattr(stop, "mid", None) or getattr(stop, "low", 0) or 0) or None
    tp = float(getattr(target, "mid", None) or getattr(target, "high", 0) or 0) or None
    if entry is None and entry_zone is not None:
        entry = float(getattr(entry_zone, "mid", None) or getattr(entry_zone, "low", 0) or 0) or None

    structure: dict[str, Any] = {}
    liquidity: dict[str, Any] = {}
    bos = choch = fvg = None
    order_blocks: list[str] = []
    market_snapshot: dict[str, Any] = {}
    if snapshot is not None:
        market_snapshot = {
            "symbol": getattr(snapshot, "symbol", None),
            "spread": str(getattr(snapshot, "spread", None)),
            "session": str(getattr(getattr(snapshot, "session", None), "session", None)),
        }
        mtf = getattr(snapshot, "mtf", None)
        if mtf is not None:
            structure = {
                "aligned": getattr(mtf, "aligned", None),
                "bias": str(getattr(mtf, "bias", None)),
            }
        liq = getattr(snapshot, "liquidity", None)
        if liq is not None:
            liquidity = {"summary": str(liq)[:200]}
        # Best-effort SMC labels from reasons / confluence
    reasons = tuple(getattr(decision, "reasons", ()) or ())
    for r in reasons:
        text = str(r).upper()
        if "BOS" in text and bos is None:
            bos = str(r)
        if "CHOCH" in text and choch is None:
            choch = str(r)
        if "FVG" in text and fvg is None:
            fvg = str(r)
        if "ORDER BLOCK" in text or "OB" in text:
            order_blocks.append(str(r))

    frames: list[ReplayFrame] = [
        ReplayFrame(0, "SIGNAL", datetime.now(UTC).isoformat(), "Opportunity identified"),
        ReplayFrame(1, "AI", datetime.now(UTC).isoformat(), explanation or "; ".join(reasons[:6]) or "AI decision"),
        ReplayFrame(2, "ENTRY", datetime.now(UTC).isoformat(), f"entry={entry}", price=entry, stop=sl, tp=tp),
    ]
    for i, ev in enumerate(trail_events or [], start=3):
        frames.append(
            ReplayFrame(
                i,
                str(ev.get("label") or "TRAIL"),
                str(ev.get("at") or datetime.now(UTC).isoformat()),
                str(ev.get("detail") or ""),
                price=ev.get("price"),
                stop=ev.get("stop"),
                tp=ev.get("tp"),
                trail=ev.get("trail"),
            )
        )
    if exit_price is not None:
        frames.append(
            ReplayFrame(
                len(frames),
                "EXIT",
                datetime.now(UTC).isoformat(),
                f"exit={exit_price}",
                price=exit_price,
                stop=sl,
                tp=tp,
            )
        )

    return TradeReplay(
        id=str(uuid4()),
        ticket=ticket,
        symbol=str(getattr(decision, "symbol", "") or ""),
        direction=str(
            getattr(getattr(decision, "direction", None), "value", None)
            or getattr(decision, "direction", "")
            or ""
        ),
        created_at=datetime.now(UTC).isoformat(),
        market_snapshot=market_snapshot,
        structure=structure,
        liquidity=liquidity,
        bos=bos,
        choch=choch,
        fvg=fvg,
        order_blocks=order_blocks[:8],
        ai_reasoning=explanation or "; ".join(str(r) for r in reasons[:12]),
        entry=entry,
        exit=exit_price,
        sl=sl,
        tp=tp,
        frames=frames,
    )


@dataclass
class TradeReplayStore:
    max_rows: int = DEFAULT_LAB_CONFIG.max_replays
    _rows: list[TradeReplay] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "trade_replays_v8.json"
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            # Keep as dicts for simplicity after reload
            with self._lock:
                self._rows = []
                for row in raw.get("replays", [])[-self.max_rows :]:
                    if isinstance(row, dict):
                        frames = [
                            ReplayFrame(**f) if isinstance(f, dict) else f
                            for f in row.get("frames", [])
                        ]
                        self._rows.append(
                            TradeReplay(
                                id=str(row.get("id") or uuid4()),
                                ticket=row.get("ticket"),
                                symbol=str(row.get("symbol") or ""),
                                direction=str(row.get("direction") or ""),
                                created_at=str(row.get("created_at") or ""),
                                market_snapshot=dict(row.get("market_snapshot") or {}),
                                structure=dict(row.get("structure") or {}),
                                liquidity=dict(row.get("liquidity") or {}),
                                bos=row.get("bos"),
                                choch=row.get("choch"),
                                fvg=row.get("fvg"),
                                order_blocks=list(row.get("order_blocks") or []),
                                ai_reasoning=str(row.get("ai_reasoning") or ""),
                                entry=row.get("entry"),
                                exit=row.get("exit"),
                                sl=row.get("sl"),
                                tp=row.get("tp"),
                                frames=frames,
                            )
                        )
        except Exception:
            logger.exception("trade_replay_load_failed")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "replays": [r.to_dict() for r in self._rows[-self.max_rows :]],
                }
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("trade_replay_persist_failed")

    def record(self, replay: TradeReplay) -> TradeReplay:
        with self._lock:
            self._rows.append(replay)
            if len(self._rows) > self.max_rows:
                self._rows = self._rows[-self.max_rows :]
        self._persist()
        return replay

    def list(self, *, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]

    def get(self, replay_id: str) -> dict[str, Any] | None:
        with self._lock:
            for r in self._rows:
                if r.id == replay_id:
                    return r.to_dict()
        return None

    def step(self, replay_id: str, frame_index: int) -> dict[str, Any] | None:
        rep = self.get(replay_id)
        if rep is None:
            return None
        frames = rep.get("frames") or []
        idx = max(0, min(frame_index, len(frames) - 1)) if frames else 0
        return {
            "replay_id": replay_id,
            "frame_index": idx,
            "frame_count": len(frames),
            "frame": frames[idx] if frames else None,
            "replay": rep,
        }


_STORE: TradeReplayStore | None = None
_LOCK = threading.Lock()


def get_trade_replay_store() -> TradeReplayStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = TradeReplayStore()
        return _STORE
