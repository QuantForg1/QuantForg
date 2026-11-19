"""QuantForg AI Assistant: grounded snapshot, image validation, provider errors."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.application.services import market_assistant as ma
from app.infrastructure.ai.openai_responses import OpenAIProviderError

PNG_1PX = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
    )
).decode()


@dataclass
class _Candle:
    open_time: datetime
    open: str
    high: str
    low: str
    close: str


def _candles(n: int, start: float = 2600.0, step: float = 1.0) -> list[_Candle]:
    t0 = datetime(2026, 11, 19, tzinfo=UTC)
    out = []
    price = start
    for i in range(n):
        o = price
        c = price + step
        out.append(
            _Candle(
                t0 + timedelta(hours=i),
                str(o),
                str(max(o, c) + 0.5),
                str(min(o, c) - 0.5),
                str(c),
            )
        )
        price = c
    return out


# ------------------------------------------------------------------ indicators


def test_indicators_on_steady_uptrend():
    s = ma.summarize_candles(_candles(80), "H1")
    assert s["available"] is True
    assert s["last_close"] == 2680.0
    assert s["trend"].startswith("up")
    assert s["rsi14"] == 100.0
    assert s["atr14"] == pytest.approx(2.0, abs=1e-6)
    assert s["high_last_20"] == 2680.5
    assert len(s["recent_bars"]) == 12


def test_too_few_candles_is_reported_unavailable_not_invented():
    assert ma.summarize_candles(_candles(3), "M15") == {
        "timeframe": "M15",
        "available": False,
    }


def test_ema_rsi_edge_cases():
    assert ma.ema([1.0, 2.0], 5) is None
    assert ma.rsi([1.0] * 5, 14) is None


# --------------------------------------------------------------------- images


def test_valid_png_passes():
    url = ma.validate_image(f"data:image/png;base64,{PNG_1PX}")
    assert url.startswith("data:image/png;base64,")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "http://evil/x.png",
        "data:text/html;base64,PGI+",
        "data:image/png;base64,@@@",
    ],
)
def test_invalid_images_rejected(bad):
    with pytest.raises(ma.AssistantError):
        ma.validate_image(bad)


def test_oversized_image_rejected():
    big = base64.b64encode(b"\0" * (ma.MAX_IMAGE_BYTES + 1)).decode()
    with pytest.raises(ma.AssistantError) as exc:
        ma.validate_image(f"data:image/jpeg;base64,{big}")
    assert exc.value.status == 413


# ----------------------------------------------------------------- rate limit


def test_rate_limit_per_user():
    ma.reset_rate_limits_for_tests()
    for i in range(ma.RATE_LIMIT_MESSAGES):
        ma.check_rate_limit("u1", now=float(i))
    with pytest.raises(ma.AssistantError) as exc:
        ma.check_rate_limit("u1", now=100.0)
    assert exc.value.status == 429
    ma.check_rate_limit("u2", now=100.0)  # other users unaffected
    ma.check_rate_limit("u1", now=100.0 + ma.RATE_LIMIT_WINDOW_S + 50)  # window slides
    ma.reset_rate_limits_for_tests()


# -------------------------------------------------------------------- snapshot


class _Feed:
    def __init__(self, *, tick_ok: bool = True) -> None:
        self.tick_ok = tick_ok

    async def tick(self, *, symbol: str):
        if not self.tick_ok:
            raise RuntimeError("feed down")
        return SimpleNamespace(
            tick=SimpleNamespace(bid="2650.10", ask="2650.35"),
            source="mt5",
            status="live",
            as_of="2026-11-19T18:00:00+00:00",
            market_open=True,
        )

    async def candles(self, *, symbol: str, timeframe: str, count: int):
        return SimpleNamespace(candles=_candles(count))


class _News:
    def news(self, *, limit: int):
        return [SimpleNamespace(title="Gold steadies", source="Wire", published_at="t")]

    def economic_events(self, *, limit: int):
        return [
            SimpleNamespace(
                title="CPI",
                country="US",
                impact="high",
                scheduled_at="t",
                forecast="3.0",
                previous="3.1",
                actual=None,
            )
        ]


def test_snapshot_uses_live_feed_values():
    snap = asyncio.run(ma.build_market_snapshot(feed=_Feed(), news=_News()))
    assert snap["quote"]["bid"] == 2650.10
    assert snap["quote"]["spread"] == 0.25
    assert [t["timeframe"] for t in snap["timeframes"]] == ["M15", "H1", "H4"]
    assert snap["economic_calendar"][0]["title"] == "CPI"


def test_snapshot_marks_missing_quote_instead_of_guessing():
    snap = asyncio.run(ma.build_market_snapshot(feed=_Feed(tick_ok=False), news=None))
    assert snap["quote"]["available"] is False
    assert "news" not in snap


# ------------------------------------------------------------------------ chat


class _Client:
    model = "test-model"

    def __init__(
        self, *, fail: str | None = None, text: str = "Gold is ranging."
    ) -> None:
        self.fail = fail
        self.text = text
        self.calls: list[dict] = []

    async def create_response(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise OpenAIProviderError(self.fail, "x")
        return {"output_text": self.text}


def _chat(client, images=None, history=None):
    return asyncio.run(
        ma.chat(
            client=client,
            history=history or [],
            message="Analyze",
            images=images or [],
            snapshot={"generated_at_utc": "now", "quote": {"bid": 1.0}},
        )
    )


def test_chat_sends_snapshot_history_and_images():
    c = _Client()
    img = f"data:image/png;base64,{PNG_1PX}"
    out = _chat(
        c,
        images=[img],
        history=[ma.ChatTurn("user", "hi"), ma.ChatTurn("assistant", "hello")],
    )
    assert out["answer"] == "Gold is ranging."
    assert out["advisory_only"] is True
    items = c.calls[0]["input_text"]
    assert items[0]["content"][0]["type"] == "input_text"
    assert items[1]["content"][0]["type"] == "output_text"
    last = items[-1]["content"]
    assert last[0]["text"].startswith("LIVE_SNAPSHOT:")
    assert any(p["type"] == "input_image" and p["image_url"] == img for p in last)
    assert "Never invent" in c.calls[0]["instructions"]


def test_chat_without_key_is_unavailable():
    with pytest.raises(ma.AssistantError) as exc:
        _chat(None)
    assert exc.value.status == 503


def test_provider_quota_error_is_explained():
    with pytest.raises(ma.AssistantError) as exc:
        _chat(_Client(fail="insufficient_quota"))
    assert "credits" in exc.value.message


def test_empty_answer_is_an_error_not_a_blank_reply():
    with pytest.raises(ma.AssistantError):
        _chat(_Client(text=""))


def test_history_is_trimmed_and_cleaned():
    turns = [ma.ChatTurn("system", "x" * 10)] + [
        ma.ChatTurn("user", f"m{i}") for i in range(30)
    ]
    out = ma.clean_history(turns)
    assert len(out) == ma.MAX_HISTORY_TURNS
    assert all(t.role in {"user", "assistant"} for t in out)
