from __future__ import annotations

import httpx
import pytest

from app import db
from app.services.llm.base import (
    LLMAuthError,
    LLMBadRequest,
    LLMRateLimit,
    LLMTransientError,
    LLMUnavailable,
)
from app.services.llm.cache import DbLlmCache, cache_key
from app.services.llm.gemini import GeminiProvider
from app.services.llm.groq import GroqProvider
from app.services.llm.limiter import TokenLimiter, estimate_tokens
from app.services.llm.service import LLMService, parse_json_object
from tests.fakes.llm_fake import FakeProvider

# ---- limiter -----------------------------------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


def limiter(rpm=3, tpm=1000):
    c = Clock()
    return TokenLimiter(rpm, tpm, clock=c.now, sleep=c.sleep), c


def test_limiter_lets_requests_through_under_the_limits():
    lim, c = limiter()
    for _ in range(3):
        lim.acquire(100)
    assert c.slept == []


def test_limiter_waits_for_the_request_budget():
    lim, c = limiter(rpm=2, tpm=10_000)
    lim.acquire(10)
    c.t += 5
    lim.acquire(10)
    c.t += 5
    lim.acquire(10)  # third request: must wait until the first leaves the 60 s window
    assert c.slept and abs(sum(c.slept) - 50.0) < 1e-6


def test_limiter_waits_for_the_token_budget():
    lim, c = limiter(rpm=100, tpm=1000)
    lim.acquire(600)
    c.t += 10
    lim.acquire(300)
    c.t += 10
    lim.acquire(400)  # 600 + 300 + 400 > 1000: wait until the 600-token request ages out
    assert abs(sum(c.slept) - 40.0) < 1e-6


def test_limiter_corrects_the_estimate_with_actual_usage():
    lim, c = limiter(rpm=100, tpm=1000)
    entry = lim.acquire(900)
    lim.record(entry, 100)  # the real cost was far lower
    lim.acquire(800)
    assert c.slept == []


def test_limiter_lets_an_oversized_request_through_once_the_window_is_empty():
    lim, c = limiter(rpm=100, tpm=1000)
    lim.acquire(5000)  # can never fit; must not block forever
    assert c.slept == []
    lim.acquire(10)
    assert c.slept  # and the next one waits for it to age out


def test_estimate_tokens_counts_devanagari_as_heavier():
    assert estimate_tokens("नमस्कार मी रोहित" * 10) > estimate_tokens("namaskar me rohit " * 10)


# ---- json parsing ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        'Here you go: {"a": 1} Hope that helps',
        '  {"a": 1}  ',
    ],
)
def test_parse_json_object_strips_fences_and_prose(text):
    assert parse_json_object(text) == {"a": 1}


@pytest.mark.parametrize("text", ["", "not json", "[1, 2]", '{"a": '])
def test_parse_json_object_rejects_garbage(text):
    with pytest.raises(ValueError):
        parse_json_object(text)


# ---- cache -------------------------------------------------------------------------------------------------------


def test_cache_key_depends_on_every_part():
    base = cache_key("groq", "m", "v1", "sys", "user")
    assert base == cache_key("groq", "m", "v1", "sys", "user")
    for changed in [
        ("gemini", "m", "v1", "sys", "user"),
        ("groq", "m2", "v1", "sys", "user"),
        ("groq", "m", "v2", "sys", "user"),
        ("groq", "m", "v1", "sys2", "user"),
        ("groq", "m", "v1", "sys", "user2"),
    ]:
        assert cache_key(*changed) != base
    assert cache_key("a", "bc", "v", "s", "u") != cache_key("ab", "c", "v", "s", "u")


def test_db_cache_round_trip_and_disable(session):
    cache = DbLlmCache(db.session_scope, enabled=True)
    assert cache.get("k") is None
    cache.put("k", {"a": [1, 2]})
    assert cache.get("k") == {"a": [1, 2]}
    cache.put("k", {"a": 3})
    assert cache.get("k") == {"a": 3}
    assert DbLlmCache(db.session_scope, enabled=False).get("k") is None


# ---- service -----------------------------------------------------------------------------------------------------

GOOD = {"ok": True}


def validate(d):
    if "ok" not in d:
        raise ValueError("missing ok")
    return d["ok"]


def make_service(primary, fallback=None, cache=None, sleeps=None, version="v1"):
    sleeps = sleeps if sleeps is not None else []
    limiters = {p.name: TokenLimiter(1000, 10_000_000, sleep=lambda s: None) for p in (primary, fallback) if p}
    return LLMService(primary, fallback, limiters, cache, version, sleep=sleeps.append), sleeps


def test_success_returns_value_and_usage():
    p = FakeProvider(responses=[GOOD])
    svc, _ = make_service(p)
    out = svc.complete("sys", "user", validate)
    assert out.value is True and out.provider == "fake" and not out.cached and not out.fallback_used
    assert out.prompt_tokens == 400 and out.completion_tokens == 80


def test_cache_hit_skips_the_provider(session):
    cache = DbLlmCache(db.session_scope)
    p = FakeProvider(responses=[GOOD])
    svc, _ = make_service(p, cache=cache)
    assert not svc.complete("s", "u", validate).cached
    second = svc.complete("s", "u", validate)
    assert second.cached and len(p.calls) == 1


def test_cache_is_not_shared_across_prompt_versions_or_providers(session):
    cache = DbLlmCache(db.session_scope)
    p = FakeProvider(responses=[GOOD])
    make_service(p, cache=cache, version="v1")[0].complete("s", "u", validate)
    make_service(p, cache=cache, version="v2")[0].complete("s", "u", validate)
    make_service(FakeProvider(name="other", responses=[GOOD]), cache=cache, version="v1")[0].complete(
        "s", "u", validate
    )
    assert len(p.calls) == 2


def test_invalid_cache_entry_is_ignored_and_refetched(session):
    cache = DbLlmCache(db.session_scope)
    p = FakeProvider(responses=[GOOD])
    cache.put(cache_key("fake", "fake-1", "v1", "s", "u"), {"unexpected": 1})
    out = make_service(p, cache=cache)[0].complete("s", "u", validate)
    assert out.value is True and not out.cached and len(p.calls) == 1


def test_rate_limit_honours_retry_after():
    p = FakeProvider(responses=[LLMRateLimit("429", retry_after=7.0), GOOD])
    svc, sleeps = make_service(p)
    assert svc.complete("s", "u", validate).value is True
    assert sleeps == [7.0]


def test_rate_limit_without_retry_after_uses_exponential_backoff():
    p = FakeProvider(responses=[LLMRateLimit("429"), LLMRateLimit("429"), GOOD])
    svc, sleeps = make_service(p)
    svc.complete("s", "u", validate)
    assert sleeps == [1.0, 2.0]


def test_three_failures_switch_to_the_fallback():
    primary = FakeProvider(name="groq", responses=[LLMRateLimit("429")] * 3)
    fallback = FakeProvider(name="gemini", responses=[GOOD])
    svc, sleeps = make_service(primary, fallback)
    out = svc.complete("s", "u", validate)
    assert out.provider == "gemini" and out.fallback_used and len(primary.calls) == 3 and sleeps == [1.0, 2.0]


def test_transient_errors_are_retried_then_fall_back():
    primary = FakeProvider(name="groq", responses=[LLMTransientError("500")] * 3)
    fallback = FakeProvider(name="gemini", responses=[GOOD])
    assert make_service(primary, fallback)[0].complete("s", "u", validate).fallback_used


def test_invalid_json_gets_one_retry():
    p = FakeProvider(responses=["not json", GOOD])
    svc, sleeps = make_service(p)
    assert svc.complete("s", "u", validate).value is True and len(p.calls) == 2 and sleeps == []


def test_schema_invalid_json_counts_as_invalid():
    p = FakeProvider(responses=[{"wrong": 1}, GOOD])
    assert make_service(p)[0].complete("s", "u", validate).value is True and len(p.calls) == 2


def test_two_invalid_responses_switch_to_the_fallback():
    primary = FakeProvider(name="groq", responses=["nope", "still nope"])
    fallback = FakeProvider(name="gemini", responses=[GOOD])
    out = make_service(primary, fallback)[0].complete("s", "u", validate)
    assert out.fallback_used and len(primary.calls) == 2


def test_code_fenced_json_is_accepted():
    p = FakeProvider(responses=['```json\n{"ok": true}\n```'])
    assert make_service(p)[0].complete("s", "u", validate).value is True


def test_auth_error_goes_straight_to_the_fallback():
    primary = FakeProvider(name="groq", responses=[LLMAuthError("bad key")])
    fallback = FakeProvider(name="gemini", responses=[GOOD])
    out = make_service(primary, fallback)[0].complete("s", "u", validate)
    assert out.fallback_used and len(primary.calls) == 1


def test_bad_request_is_not_retried():
    primary = FakeProvider(name="groq", responses=[LLMBadRequest("no")])
    svc, sleeps = make_service(primary)
    with pytest.raises(LLMUnavailable):
        svc.complete("s", "u", validate)
    assert len(primary.calls) == 1 and sleeps == []


def test_everything_failing_raises_llm_unavailable():
    primary = FakeProvider(name="groq", responses=[LLMTransientError("x")] * 3)
    fallback = FakeProvider(name="gemini", responses=["bad", "bad"])
    with pytest.raises(LLMUnavailable) as e:
        make_service(primary, fallback)[0].complete("s", "u", validate)
    assert "groq" in str(e.value) and "gemini" in str(e.value)


def test_no_fallback_configured():
    with pytest.raises(LLMUnavailable):
        make_service(FakeProvider(responses=[LLMTransientError("x")] * 3))[0].complete("s", "u", validate)


# ---- Groq provider -----------------------------------------------------------------------------------------------


def groq_with(handler) -> GroqProvider:
    return GroqProvider("gsk-test", "openai/gpt-oss-120b", http=httpx.Client(transport=httpx.MockTransport(handler)))


def ok_body(content='{"ok": true}'):
    return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 120, "completion_tokens": 30}}


def test_groq_request_shape_and_usage():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = __import__("json").loads(req.content)
        return httpx.Response(200, json=ok_body())

    r = groq_with(handler).complete_json("SYS", "USER")
    assert r.text == '{"ok": true}' and (r.prompt_tokens, r.completion_tokens) == (120, 30)
    assert seen["auth"] == "Bearer gsk-test"
    body = seen["body"]
    assert body["model"] == "openai/gpt-oss-120b" and body["temperature"] == 0
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_groq_maps_errors():
    with pytest.raises(LLMRateLimit) as e:
        groq_with(lambda r: httpx.Response(429, headers={"retry-after": "12"}, json={})).complete_json("s", "u")
    assert e.value.retry_after == 12.0
    with pytest.raises(LLMAuthError):
        groq_with(lambda r: httpx.Response(401, json={})).complete_json("s", "u")
    with pytest.raises(LLMTransientError):
        groq_with(lambda r: httpx.Response(503, json={})).complete_json("s", "u")
    with pytest.raises(LLMBadRequest):
        groq_with(lambda r: httpx.Response(400, json={"error": {"message": "bad model"}})).complete_json("s", "u")


def test_groq_drops_response_format_if_the_model_rejects_it():
    bodies = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(req.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": {"message": "response_format is not supported with this model"}})
        return httpx.Response(200, json=ok_body())

    p = groq_with(handler)
    assert p.complete_json("s", "u").text
    assert len(bodies) == 2 and "response_format" not in bodies[1]
    p.complete_json("s", "u")  # remembered: no more rejected attempts
    assert len(bodies) == 3


def test_groq_connection_error_is_transient():
    def boom(req):
        raise httpx.ConnectError("down")

    with pytest.raises(LLMTransientError):
        groq_with(boom).complete_json("s", "u")


# ---- Gemini provider ---------------------------------------------------------------------------------------------


class FakeGenai:
    def __init__(self, result=None, error=None):
        self.calls = []
        outer = self

        class Models:
            def generate_content(self, **kw):
                outer.calls.append(kw)
                if error:
                    raise error
                return result

        self.models = Models()


def gemini_result(text='{"ok": true}'):
    from types import SimpleNamespace as NS

    return NS(text=text, usage_metadata=NS(prompt_token_count=50, candidates_token_count=9))


def test_gemini_request_and_usage():
    client = FakeGenai(gemini_result())
    r = GeminiProvider("k", "gemini-2.5-flash", client=client).complete_json("SYS", "USER")
    assert r.text == '{"ok": true}' and (r.prompt_tokens, r.completion_tokens) == (50, 9)
    call = client.calls[0]
    assert call["model"] == "gemini-2.5-flash" and call["contents"] == "USER"
    cfg = call["config"]
    assert cfg.system_instruction == "SYS" and cfg.temperature == 0 and cfg.response_mime_type == "application/json"


def test_gemini_needs_a_model_name():
    with pytest.raises(ValueError, match="GEMINI_MODEL"):
        GeminiProvider("k", "", client=FakeGenai())


@pytest.mark.parametrize(
    "code,exc",
    [(429, LLMRateLimit), (401, LLMAuthError), (403, LLMAuthError), (503, LLMTransientError), (400, LLMBadRequest)],
)
def test_gemini_maps_api_errors(code, exc):
    from google.genai import errors

    client = FakeGenai(error=errors.APIError(code, {"error": {"message": "x"}}))
    with pytest.raises(exc):
        GeminiProvider("k", "gemini-2.5-flash", client=client).complete_json("s", "u")
