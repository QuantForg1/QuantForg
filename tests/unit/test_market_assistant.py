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
    assert last[0]["text"].startswith("LIVE_DATA:")
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


# ------------------------------------------------------------ v2: streaming


def _sse_body(*events: dict) -> bytes:
    import json as _j

    return "".join(f"data: {_j.dumps(e)}\n\n" for e in events).encode()


def _stream_client(handler):
    import httpx

    from app.infrastructure.ai.openai_responses import OpenAIResponsesClient

    return OpenAIResponsesClient(
        api_key="sk-test", model="m", transport=httpx.MockTransport(handler)
    )


def _collect(agen):
    async def run():
        return [x async for x in agen]

    return asyncio.run(run())


def test_stream_output_text_yields_deltas_and_sends_reasoning():
    import httpx

    from app.infrastructure.ai.openai_responses import stream_output_text

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _j

        seen.append(_j.loads(request.content))
        return httpx.Response(
            200,
            content=_sse_body(
                {"type": "response.created"},
                {"type": "response.output_text.delta", "delta": "Gold "},
                {"type": "response.output_text.delta", "delta": "is up."},
                {"type": "response.completed"},
            ),
            headers={"content-type": "text/event-stream"},
        )

    out = _collect(
        stream_output_text(
            _stream_client(handler),
            input_items="hi",
            instructions="x",
            reasoning_effort="low",
        )
    )
    assert "".join(e["text"] for e in out) == "Gold is up."
    assert seen[0]["stream"] is True
    assert seen[0]["reasoning"] == {"effort": "low"}
    assert seen[0]["store"] is False


def test_stream_retries_without_reasoning_when_model_rejects_it():
    import httpx

    from app.infrastructure.ai.openai_responses import stream_output_text

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _j

        body = _j.loads(request.content)
        calls.append("reasoning" in body)
        if "reasoning" in body:
            return httpx.Response(400, json={"error": {"message": "unsupported"}})
        return httpx.Response(
            200,
            content=_sse_body({"type": "response.output_text.delta", "delta": "ok"}),
        )

    out = _collect(
        stream_output_text(
            _stream_client(handler),
            input_items="hi",
            instructions="x",
            reasoning_effort="low",
        )
    )
    assert out == [{"type": "text", "text": "ok"}]
    assert calls == [True, False]


def test_stream_quota_error_raises_typed_error():
    import httpx

    from app.infrastructure.ai.openai_responses import stream_output_text

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": "insufficient_quota"}})

    with pytest.raises(OpenAIProviderError) as exc:
        _collect(
            stream_output_text(
                _stream_client(handler), input_items="x", instructions="x"
            )
        )
    assert exc.value.code == "insufficient_quota"


def test_stream_chat_emits_meta_deltas_done():
    async def fake_stream(client, **kw):
        assert kw["reasoning_effort"] == "low"
        assert kw["reasoning_summary"] is True
        yield {"type": "thinking", "text": "hmm"}
        for t in ("A", "B"):
            yield {"type": "text", "text": t}

    out = _collect(
        ma.stream_chat(
            client=SimpleNamespace(model="m"),
            history=[],
            message="hi",
            images=[],
            snapshot={
                "generated_at_utc": "2026-11-19T19:22:43+00:00",
                "quote": {"bid": 1},
            },
            streamer=fake_stream,
        )
    )
    kinds = [o.split("\n")[0].removeprefix("event: ") for o in out]
    assert kinds[0] == "stage" and '"status": "active"' in out[0]
    meta = out[kinds.index("meta")]
    assert '"as_of_utc": "2026-11-19T19:22:43+00:00"' in meta
    assert kinds[kinds.index("meta") + 1 :] == [
        "thinking",
        "stage",
        "delta",
        "delta",
        "done",
    ]


def test_stream_chat_reports_provider_error_as_event():
    async def failing(client, **kw):
        raise OpenAIProviderError("insufficient_quota", "x")
        yield  # pragma: no cover

    out = _collect(
        ma.stream_chat(
            client=SimpleNamespace(model="m"),
            history=[],
            message="hi",
            images=[],
            snapshot={},
            streamer=failing,
        )
    )
    assert out[-1].startswith("event: error")
    assert "credits" in out[-1]


def test_stream_chat_uses_more_reasoning_for_images():
    assert ma.reasoning_for([]) == "low"
    assert ma.reasoning_for(["x"]) == "medium"


# --------------------------------------------------- v2: levels & conditions


def test_quote_time_is_fetch_time_not_broker_clock():
    snap = asyncio.run(
        ma.build_market_snapshot(
            feed=_Feed(), news=None, now=datetime(2026, 11, 19, 19, 22, 43, tzinfo=UTC)
        )
    )
    assert snap["quote"]["fetched_at_utc"] == "2026-11-19T19:22:43+00:00"
    assert "as_of" not in snap["quote"]
    assert snap["session"] == "New York"
    assert snap["bias"]["direction"] == "bullish"


def test_swing_levels_split_around_price():
    base = []
    t0 = datetime(2026, 11, 1, tzinfo=UTC)
    prices = [
        100,
        104,
        108,
        104,
        100,
        96,
        92,
        96,
        100,
        104,
        108,
        112,
        108,
        104,
        100,
    ] * 3
    for i, p in enumerate(prices):
        base.append(
            _Candle(t0 + timedelta(hours=i), str(p), str(p + 1), str(p - 1), str(p))
        )
    lv = ma.swing_levels(base, 101.0)
    assert lv["resistances"] and all(x > 101 for x in lv["resistances"])
    assert lv["supports"] and all(x < 101 for x in lv["supports"])
    assert lv["resistances"] == sorted(lv["resistances"])
    assert lv["supports"] == sorted(lv["supports"], reverse=True)


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (datetime(2026, 11, 19, 13, 0, tzinfo=UTC), "London-New York overlap"),
        (datetime(2026, 11, 19, 8, 0, tzinfo=UTC), "London"),
        (datetime(2026, 11, 19, 2, 0, tzinfo=UTC), "Asia"),
        (datetime(2026, 11, 21, 12, 0, tzinfo=UTC), "closed (weekend)"),
    ],
)
def test_trading_session(when, expected):
    assert ma.trading_session(when) == expected


def _snap_for_conditions(**over):
    snap = {
        "session": "London",
        "bias": {"direction": "bearish", "aligned": 3, "of": 3},
        "quote": {"bid": 2650.0, "ask": 2650.3, "spread": 0.3},
        "timeframes": [
            {"timeframe": "M15", "available": True, "atr14": 4.0},
            {
                "timeframe": "H1",
                "available": True,
                "atr14": 10.0,
                "rsi14": 45.0,
                "last_close": 2650,
            },
            {"timeframe": "H4", "available": True},
        ],
        "key_levels_h1": {"supports": [2620.0], "resistances": [2670.0]},
        "volatility_h1": {"state": "normal", "atr_vs_average": 1.0},
        "economic_calendar": [],
    }
    snap.update(over)
    return snap


def test_conditions_supportive_when_everything_lines_up():
    c = ma.trade_conditions(_snap_for_conditions())
    assert c["tone"] == "good"
    assert c["score"] == 100
    assert {i["key"] for i in c["items"]} == {
        "trend",
        "momentum",
        "room",
        "volatility",
        "spread",
        "news",
        "session",
    }


def test_imminent_high_impact_news_means_stand_aside():
    cal = [{"title": "US CPI", "impact": "High", "minutes_from_now": 30}]
    c = ma.trade_conditions(_snap_for_conditions(economic_calendar=cal))
    news = next(i for i in c["items"] if i["key"] == "news")
    assert news["status"] == "avoid"
    assert "US CPI in 30 min" in news["detail"]
    assert c["tone"] == "avoid"


def test_no_room_to_level_and_stretched_rsi_flagged():
    snap = _snap_for_conditions(key_levels_h1={"supports": [2648.0], "resistances": []})
    snap["timeframes"][1]["rsi14"] = 22.0
    c = ma.trade_conditions(snap)
    by = {i["key"]: i for i in c["items"]}
    assert by["room"]["status"] == "avoid"
    assert by["momentum"]["status"] == "caution"


def test_snapshot_cache_reuses_recent_data():
    ma.clear_snapshot_cache_for_tests()
    calls = {"n": 0}

    class CountingFeed(_Feed):
        async def tick(self, *, symbol):
            calls["n"] += 1
            return await super().tick(symbol=symbol)

    async def run():
        f = CountingFeed()
        await ma.cached_market_snapshot(feed=f, news=None)
        await ma.cached_market_snapshot(feed=f, news=None)

    asyncio.run(run())
    assert calls["n"] == 1
    ma.clear_snapshot_cache_for_tests()


def test_stream_sends_reasoning_summary_and_parses_thinking():
    import httpx

    from app.infrastructure.ai.openai_responses import stream_output_text

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _j

        seen.append(_j.loads(request.content))
        return httpx.Response(
            200,
            content=_sse_body(
                {
                    "type": "response.reasoning_summary_text.delta",
                    "delta": "Checking trend",
                },
                {"type": "response.reasoning_summary_part.done"},
                {"type": "response.output_text.delta", "delta": "Down."},
                {"type": "response.completed"},
            ),
        )

    out = _collect(
        stream_output_text(
            _stream_client(handler),
            input_items="hi",
            instructions="x",
            reasoning_effort="low",
            reasoning_summary=True,
        )
    )
    assert seen[0]["reasoning"] == {"effort": "low", "summary": "auto"}
    assert out[0] == {"type": "thinking", "text": "Checking trend"}
    assert out[-1] == {"type": "text", "text": "Down."}


def test_stream_downgrade_ladder_summary_then_effort_then_none():
    import httpx

    from app.infrastructure.ai.openai_responses import stream_output_text

    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _j

        body = _j.loads(request.content)
        sent.append(body.get("reasoning"))
        if body.get("reasoning"):
            return httpx.Response(400, json={"error": {"message": "unsupported"}})
        return httpx.Response(
            200,
            content=_sse_body({"type": "response.output_text.delta", "delta": "ok"}),
        )

    out = _collect(
        stream_output_text(
            _stream_client(handler),
            input_items="hi",
            instructions="x",
            reasoning_effort="low",
            reasoning_summary=True,
        )
    )
    assert out == [{"type": "text", "text": "ok"}]
    assert sent == [{"effort": "low", "summary": "auto"}, {"effort": "low"}, None]


def test_analysis_stages_describe_real_data():
    snap = {
        "quote": {"bid": 3675.33, "ask": 3675.68, "spread": 0.35},
        "session": "New York",
        "timeframes": [{"timeframe": "H1", "rsi14": 20.3}],
        "bias": {"direction": "bearish", "aligned": 3, "of": 3},
        "key_levels_h1": {"supports": [3665.73], "resistances": [3680.08]},
        "economic_calendar": [
            {"title": "Fed Chair Speech", "impact": "High", "minutes_from_now": 95}
        ],
    }
    st = {s["key"]: s["detail"] for s in ma.analysis_stages(snap)}
    assert st["price"] == "XAUUSD 3,675.51 · spread 0.35 · New York"
    assert st["trend"] == "Bearish on 3/3 timeframes · H1 RSI 20.3"
    assert st["levels"] == "Support 3,665.73 · Resistance 3,680.08"
    assert st["news"] == "Fed Chair Speech in 95 min"


def test_analysis_stages_say_when_data_missing():
    st = {s["key"]: s["detail"] for s in ma.analysis_stages({})}
    assert "unavailable" in st["price"].lower()
    assert "unavailable" in st["trend"].lower()
    assert st["news"] == "Calendar unavailable"


def test_stream_chat_fetches_snapshot_inside_stream_and_reports_chart_stage():
    async def provider():
        return {"generated_at_utc": "t"}

    async def fake_stream(client, **kw):
        assert kw["reasoning_effort"] == "medium"
        yield {"type": "text", "text": "x"}

    out = _collect(
        ma.stream_chat(
            client=SimpleNamespace(model="m"),
            history=[],
            message="",
            images=["data:image/png;base64,AA=="],
            snapshot_provider=provider,
            streamer=fake_stream,
        )
    )
    assert any('"key": "chart"' in o for o in out)
    assert out[-1].startswith("event: done")


def test_stream_never_exposes_the_underlying_model():
    async def fake_stream(client, **kw):
        assert kw["web_search"] is True
        yield {"type": "text", "text": "ok"}

    out = _collect(
        ma.stream_chat(
            client=SimpleNamespace(model="gpt-secret-model"),
            history=[],
            message="hi",
            images=[],
            snapshot={"generated_at_utc": "t"},
            streamer=fake_stream,
        )
    )
    joined = "".join(out)
    assert "gpt-secret-model" not in joined
    assert '"assistant": "QuantForg AI"' in joined


def test_chat_response_never_exposes_the_underlying_model():
    out = _chat(_Client())
    assert "model" not in out
    assert out["assistant"] == "QuantForg AI"
    assert "test-model" not in str(out)


def test_instructions_forbid_naming_the_vendor():
    text = ma.INSTRUCTIONS
    assert "You are QuantForg AI" in text
    assert "Never name or hint at the" in text


def test_web_search_requested_first_and_dropped_when_rejected():
    import httpx

    from app.infrastructure.ai.openai_responses import stream_output_text

    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _j

        body = _j.loads(request.content)
        sent.append(("tools" in body, body.get("reasoning")))
        if "tools" in body:
            return httpx.Response(400, json={"error": {"message": "tools unsupported"}})
        return httpx.Response(
            200,
            content=_sse_body({"type": "response.output_text.delta", "delta": "ok"}),
        )

    out = _collect(
        stream_output_text(
            _stream_client(handler),
            input_items="hi",
            instructions="x",
            reasoning_effort="low",
            reasoning_summary=True,
            web_search=True,
        )
    )
    assert out == [{"type": "text", "text": "ok"}]
    assert sent[0] == (True, {"effort": "low", "summary": "auto"})
    assert sent[1] == (False, {"effort": "low", "summary": "auto"})


def test_web_search_progress_becomes_a_stage():
    async def fake_stream(client, **kw):
        yield {"type": "search", "text": "searching"}
        yield {"type": "search", "text": "done"}
        yield {"type": "text", "text": "Answer"}

    out = _collect(
        ma.stream_chat(
            client=SimpleNamespace(model="m"),
            history=[],
            message="news?",
            images=[],
            snapshot={},
            streamer=fake_stream,
        )
    )
    web = [o for o in out if '"key": "web"' in o]
    assert len(web) == 2
    assert '"status": "active"' in web[0] and '"status": "done"' in web[1]
