import pytest
from langchain_core.messages import AIMessage

from llm import gemini
from store import db


@pytest.fixture
def keys(monkeypatch):
    for n, k in (("1", "free-a"), ("2", "paid"), ("3", "free-b")):
        monkeypatch.setenv(f"GOOGLE_API_KEY_{n}", k)
    monkeypatch.setenv("GEMINI_PAID_KEY", "2")
    monkeypatch.setenv("GEMINI_MONTHLY_BUDGET_USD", "5")
    db._memory_spend.clear()
    gemini._spend_cache.update(month="", usd=0.0, at=0.0)
    yield


def test_paid_key_goes_first(keys):
    assert gemini.api_keys() == ["paid", "free-a", "free-b"]


def test_only_the_paid_key_is_counted(keys):
    gemini.record_usage("free-a", "gemini-3-flash-preview", 1_000_000, 0)
    assert gemini.month_spend() == 0
    gemini.record_usage("paid", "gemini-3-flash-preview", 1_000_000, 1_000_000)  # 0.50 + 3.00
    assert gemini.month_spend() == pytest.approx(3.5)


def test_the_paid_key_is_skipped_once_the_budget_is_spent(keys):
    assert not gemini.over_budget("paid")
    gemini.record_usage("paid", "unknown-model", 0, 700_000)  # dearest default rate: 7.50/M
    assert gemini.month_spend() == pytest.approx(5.25) and gemini.over_budget("paid")
    assert not gemini.over_budget("free-a")

    calls = []
    model = gemini._guarded(lambda: calls.append(1), "gemini-3-flash-preview", "paid")
    with pytest.raises(gemini.QuotaBlocked):
        model.invoke("hola")
    assert not calls  # never reached the API


def test_structured_replies_are_unwrapped_and_counted(keys):
    class Fake:
        def invoke(self, value, config=None):
            raw = AIMessage("{}", usage_metadata={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1300})
            return {"raw": raw, "parsed": {"respuesta": "Buenas"}, "parsing_error": None}

    out = gemini._guarded(lambda: Fake(), "gemini-3-flash-preview", "paid").invoke("hola")
    assert out == {"respuesta": "Buenas"}
    # thinking tokens count as output: 300 = total - input
    assert gemini.month_spend() == pytest.approx((1000 * 0.50 + 300 * 3.00) / 1e6)


def test_running_out_of_credits_counts_as_out_of_quota():
    assert gemini.is_quota_error(Exception("402 PAYMENT_REQUIRED: prepaid credits depleted"))
    assert not gemini.is_quota_error(Exception("400 INVALID_ARGUMENT"))


def test_only_listed_users_spend_the_paid_key(keys, monkeypatch):
    monkeypatch.setenv("GEMINI_PAID_USERS", "Sofia@example.com, joaquin@example.com")
    with gemini.usuario("sofia@example.com"):
        assert not gemini.over_budget("paid")
    with gemini.usuario("alguien@gmail.com"):
        assert gemini.over_budget("paid")  # strangers get the free keys
        assert not gemini.over_budget("free-a")
    assert not gemini.over_budget("paid")  # outside a request (scripts, evals)


def test_deployed_calls_without_a_user_dont_spend(keys, monkeypatch):
    monkeypatch.setenv("GEMINI_PAID_USERS", "sofia@example.com")
    monkeypatch.setenv("VERCEL", "1")
    assert gemini.over_budget("paid")  # fail closed: no user known
    with gemini.usuario("sofia@example.com"):
        assert not gemini.over_budget("paid")


def test_the_feedback_thread_keeps_the_user(keys, monkeypatch):
    import contextvars
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("GEMINI_PAID_USERS", "sofia@example.com")
    with gemini.usuario("alguien@gmail.com"), ThreadPoolExecutor(1) as pool:
        assert pool.submit(contextvars.copy_context().run, gemini.over_budget, "paid").result()


def test_genai_client_is_one_per_key_even_from_concurrent_first_calls(monkeypatch):
    """Two threads asking for the first time must get the same client: the one not kept was garbage
    collected, closing its connection mid-call ("client has been closed")."""
    import threading
    import time

    from llm import gemini

    creados = []

    class Cliente:
        def __init__(self, api_key):
            time.sleep(0.05)  # widen the race window
            creados.append(self)

    monkeypatch.setattr("google.genai.Client", Cliente)
    monkeypatch.setattr(gemini, "_clients", {})
    vistos = []
    hilos = [threading.Thread(target=lambda: vistos.append(gemini.genai_client("k"))) for _ in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(creados) == 1 and all(v is creados[0] for v in vistos)
