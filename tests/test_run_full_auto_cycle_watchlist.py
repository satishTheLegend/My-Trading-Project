"""Watchlist priority injection for the FULL_AUTO_LIVE cycle (task #22).

The cycle engine should evaluate hand-curated, high-conviction watchlist
setups BEFORE screener fallback candidates. Priority injection is read-only
against ``data/watchlist.json`` and never relaxes strategy/risk gates.

These tests target the pure selector ``select_watchlist_priority_symbols``
and the filesystem wrapper ``_load_watchlist_priority_symbols``. Both are
deterministic, no Binance access, no mocking of ``market`` needed.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from scripts.run_full_auto_cycle import (
    _load_watchlist_priority_symbols,
    prepend_watchlist_priority,
    select_watchlist_priority_symbols,
)


class _FakeSpec:
    """Tiny stand-in for SymbolSpec — only ``.symbol`` is read by the helper."""
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol


class _FakeTicker:
    """Tiny stand-in for Ticker24h — only identity tracking matters here."""
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _wl_entry(
    symbol: str,
    *,
    priority: str = "high",
    side_bias: str = "long",
    expires_at: str | None = "2099-01-01T00:00Z",
) -> dict:
    return {
        "symbol": symbol,
        "side_bias": side_bias,
        "priority": priority,
        "catalyst": f"test catalyst for {symbol}",
        "news_sources": [],
        "social_signal": "",
        "discovered_at": "2026-05-11T10:00Z",
        "expires_at": expires_at,
        "screener_metrics": {},
        "notes": "",
    }


_NOW = dt.datetime(2026, 5, 11, 13, 0, 0)


# ---------------------------------------------------------------------------
# Core ordering — watchlist priority comes FIRST
# ---------------------------------------------------------------------------


def test_watchlist_priority_symbols_are_returned_in_file_order():
    """Mocked watchlist [GTCUSDT, USUSDT, INXUSDT] all priority=high, valid
    side_bias, not expired, not open → selector returns them in file order.

    Combined with the cycle's prepend logic this guarantees the final
    candidate list is [GTC, US, INX, <screener fallback...>].
    """
    wl = {
        "watchlist": [
            _wl_entry("GTCUSDT", side_bias="long"),
            _wl_entry("USUSDT", side_bias="long"),
            _wl_entry("INXUSDT", side_bias="short"),
        ]
    }
    out = select_watchlist_priority_symbols(
        watchlist_data=wl,
        open_position_symbols=set(),
        now_utc=_NOW,
    )
    assert out == ["GTCUSDT", "USUSDT", "INXUSDT"]


# ---------------------------------------------------------------------------
# Exclusion: open positions
# ---------------------------------------------------------------------------


def test_watchlist_priority_excludes_already_open_symbols():
    """If a watchlist symbol matches an open position (status in is_open set),
    it MUST be excluded from the priority list — duplicate-symbol positions
    are forbidden by global rule 11 / Safety Agent.
    """
    wl = {
        "watchlist": [
            _wl_entry("GTCUSDT", side_bias="long"),
            _wl_entry("BUSDT", side_bias="long"),       # already open
            _wl_entry("INXUSDT", side_bias="short"),
        ]
    }
    out = select_watchlist_priority_symbols(
        watchlist_data=wl,
        open_position_symbols={"BUSDT", "SAGAUSDT"},
        now_utc=_NOW,
    )
    assert out == ["GTCUSDT", "INXUSDT"]
    assert "BUSDT" not in out


# ---------------------------------------------------------------------------
# Exclusion: expired entries
# ---------------------------------------------------------------------------


def test_watchlist_priority_excludes_expired_entries():
    """``expires_at`` in the past → entry is stale and MUST be excluded.

    Boundary case: ``expires_at == now`` is treated as expired (strict <).
    """
    wl = {
        "watchlist": [
            _wl_entry("GTCUSDT", side_bias="long",
                      expires_at="2026-05-11T12:00Z"),  # past
            _wl_entry("USUSDT", side_bias="long",
                      expires_at="2026-05-11T13:00Z"),  # exactly now → excluded
            _wl_entry("INXUSDT", side_bias="short",
                      expires_at="2026-05-11T14:00Z"),  # future
        ]
    }
    out = select_watchlist_priority_symbols(
        watchlist_data=wl,
        open_position_symbols=set(),
        now_utc=_NOW,
    )
    assert out == ["INXUSDT"]


# ---------------------------------------------------------------------------
# Filtering: priority + side_bias
# ---------------------------------------------------------------------------


def test_watchlist_priority_skips_medium_low_and_neutral():
    wl = {
        "watchlist": [
            _wl_entry("AAAUSDT", priority="medium", side_bias="long"),
            _wl_entry("BBBUSDT", priority="low", side_bias="short"),
            _wl_entry("CCCUSDT", priority="high", side_bias="neutral"),
            _wl_entry("DDDUSDT", priority="high", side_bias="long"),
        ]
    }
    out = select_watchlist_priority_symbols(
        watchlist_data=wl,
        open_position_symbols=set(),
        now_utc=_NOW,
    )
    assert out == ["DDDUSDT"]


def test_watchlist_priority_handles_missing_expires_at_as_not_expired():
    """Older watchlist revisions omit ``expires_at``. Selector treats them as
    not-expired so we don't silently drop hand-curated entries on schema drift.
    """
    wl = {
        "watchlist": [
            _wl_entry("GTCUSDT", side_bias="long", expires_at=None),
        ]
    }
    out = select_watchlist_priority_symbols(
        watchlist_data=wl,
        open_position_symbols=set(),
        now_utc=_NOW,
    )
    assert out == ["GTCUSDT"]


# ---------------------------------------------------------------------------
# Robustness: malformed / missing input
# ---------------------------------------------------------------------------


def test_watchlist_priority_handles_empty_or_malformed_input():
    assert select_watchlist_priority_symbols(None, set(), _NOW) == []
    assert select_watchlist_priority_symbols({}, set(), _NOW) == []
    assert select_watchlist_priority_symbols({"watchlist": "not a list"}, set(), _NOW) == []
    # Per-entry malformed rows are skipped, not fatal:
    wl = {
        "watchlist": [
            "not a dict",
            {"priority": "high"},                       # no symbol
            {"symbol": "", "priority": "high", "side_bias": "long"},
            _wl_entry("GTCUSDT", side_bias="long"),
        ]
    }
    out = select_watchlist_priority_symbols(wl, set(), _NOW)
    assert out == ["GTCUSDT"]


def test_watchlist_priority_dedupes_symbols():
    """If the file accidentally lists the same symbol twice, the selector
    yields it only once (in first-occurrence position)."""
    wl = {
        "watchlist": [
            _wl_entry("GTCUSDT", side_bias="long"),
            _wl_entry("GTCUSDT", side_bias="short"),
            _wl_entry("USUSDT", side_bias="long"),
        ]
    }
    out = select_watchlist_priority_symbols(wl, set(), _NOW)
    assert out == ["GTCUSDT", "USUSDT"]


# ---------------------------------------------------------------------------
# Filesystem wrapper
# ---------------------------------------------------------------------------


def test_load_watchlist_priority_returns_empty_when_file_absent(tmp_path):
    out = _load_watchlist_priority_symbols(
        open_position_symbols=set(),
        watchlist_path=tmp_path / "does-not-exist.json",
        now_utc=_NOW,
    )
    assert out == []


def test_load_watchlist_priority_returns_empty_on_corrupt_json(tmp_path):
    p = tmp_path / "watchlist.json"
    p.write_text("{this is not json", encoding="utf-8")
    out = _load_watchlist_priority_symbols(
        open_position_symbols=set(),
        watchlist_path=p,
        now_utc=_NOW,
    )
    assert out == []


# ---------------------------------------------------------------------------
# Prepend ordering — watchlist FIRST, screener AFTER
# ---------------------------------------------------------------------------


def test_prepend_watchlist_priority_puts_watchlist_first_and_screener_after():
    """The user-quoted scenario: priority [GTC, US, INX], screener fallback
    [FOLKS, ALCH, ...]. Final candidate list MUST be evaluated as
    [GTC, US, INX, FOLKS, ALCH, ...] — watchlist first, screener after.
    """
    specs = {sym: _FakeSpec(sym) for sym in
             ["GTCUSDT", "USUSDT", "INXUSDT", "FOLKSUSDT", "ALCHUSDT", "ABCUSDT"]}
    screener_pairs = [
        (specs["FOLKSUSDT"], _FakeTicker("FOLKSUSDT")),
        (specs["ALCHUSDT"], _FakeTicker("ALCHUSDT")),
        (specs["ABCUSDT"], _FakeTicker("ABCUSDT")),
    ]
    ticker_calls: list[str] = []

    def fetch(sym: str) -> _FakeTicker:
        ticker_calls.append(sym)
        return _FakeTicker(sym)

    out, injected, skipped = prepend_watchlist_priority(
        priority_symbols=["GTCUSDT", "USUSDT", "INXUSDT"],
        screener_pairs=screener_pairs,
        specs=specs,
        ticker_fetcher=fetch,
    )
    final_symbols = [spec.symbol for spec, _ in out]
    assert final_symbols == [
        "GTCUSDT", "USUSDT", "INXUSDT", "FOLKSUSDT", "ALCHUSDT", "ABCUSDT",
    ]
    assert injected == ["GTCUSDT", "USUSDT", "INXUSDT"]
    assert skipped == []
    # Three watchlist symbols, three ticker fetches — no screener fallback
    # tickers re-fetched.
    assert ticker_calls == ["GTCUSDT", "USUSDT", "INXUSDT"]


def test_prepend_watchlist_priority_hoists_overlap_no_duplicates():
    """A watchlist symbol that ALSO appears in the screener output is hoisted
    to the front but not duplicated."""
    specs = {sym: _FakeSpec(sym) for sym in ["GTCUSDT", "FOLKSUSDT", "ALCHUSDT"]}
    screener_pairs = [
        (specs["FOLKSUSDT"], _FakeTicker("FOLKSUSDT")),
        (specs["GTCUSDT"], _FakeTicker("GTCUSDT")),    # overlap
        (specs["ALCHUSDT"], _FakeTicker("ALCHUSDT")),
    ]
    out, injected, _ = prepend_watchlist_priority(
        priority_symbols=["GTCUSDT"],
        screener_pairs=screener_pairs,
        specs=specs,
        ticker_fetcher=lambda s: pytest_fail_if_called(s),  # noqa: F821 (defined below)
    )
    final_symbols = [spec.symbol for spec, _ in out]
    # GTCUSDT first; FOLKS + ALCH retain their original screener order; only
    # one GTCUSDT (no duplication).
    assert final_symbols == ["GTCUSDT", "FOLKSUSDT", "ALCHUSDT"]
    assert injected == ["GTCUSDT"]


def pytest_fail_if_called(symbol: str):
    """Used in the hoist test to assert the ticker fetcher is NEVER called for
    a symbol the screener already returned. We must reuse that ticker, not
    re-fetch."""
    raise AssertionError(
        f"ticker_fetcher must not be invoked for screener-overlap symbol {symbol}"
    )


def test_prepend_watchlist_priority_skips_unknown_specs():
    """Priority symbol absent from exchangeInfo → silently skipped, recorded
    in ``skipped``, and the cycle continues with the remaining priorities
    and screener fallback."""
    specs = {sym: _FakeSpec(sym) for sym in ["GTCUSDT", "FOLKSUSDT"]}
    screener_pairs = [(specs["FOLKSUSDT"], _FakeTicker("FOLKSUSDT"))]
    out, injected, skipped = prepend_watchlist_priority(
        priority_symbols=["GTCUSDT", "DELISTEDUSDT"],
        screener_pairs=screener_pairs,
        specs=specs,
        ticker_fetcher=lambda s: _FakeTicker(s),
    )
    final_symbols = [spec.symbol for spec, _ in out]
    assert final_symbols == ["GTCUSDT", "FOLKSUSDT"]
    assert injected == ["GTCUSDT"]
    assert skipped == [{"symbol": "DELISTEDUSDT", "reason": "not in exchangeInfo"}]


def test_prepend_watchlist_priority_skips_ticker_fetch_failures():
    """Transient ticker fetch failure → that priority symbol is skipped,
    cycle continues. Don't sacrifice the whole run for one bad fetch."""
    specs = {sym: _FakeSpec(sym) for sym in ["GTCUSDT", "FLAKEUSDT", "FOLKSUSDT"]}
    screener_pairs = [(specs["FOLKSUSDT"], _FakeTicker("FOLKSUSDT"))]

    def fetch(sym: str):
        if sym == "FLAKEUSDT":
            raise RuntimeError("simulated transient HTTP 500")
        return _FakeTicker(sym)

    out, injected, skipped = prepend_watchlist_priority(
        priority_symbols=["GTCUSDT", "FLAKEUSDT"],
        screener_pairs=screener_pairs,
        specs=specs,
        ticker_fetcher=fetch,
    )
    final_symbols = [spec.symbol for spec, _ in out]
    assert final_symbols == ["GTCUSDT", "FOLKSUSDT"]
    assert injected == ["GTCUSDT"]
    assert len(skipped) == 1
    assert skipped[0]["symbol"] == "FLAKEUSDT"
    assert "ticker fetch failed" in skipped[0]["reason"]


def test_prepend_watchlist_priority_empty_priority_returns_screener_unchanged():
    specs = {sym: _FakeSpec(sym) for sym in ["FOLKSUSDT", "ALCHUSDT"]}
    screener_pairs = [
        (specs["FOLKSUSDT"], _FakeTicker("FOLKSUSDT")),
        (specs["ALCHUSDT"], _FakeTicker("ALCHUSDT")),
    ]
    out, injected, skipped = prepend_watchlist_priority(
        priority_symbols=[],
        screener_pairs=screener_pairs,
        specs=specs,
        ticker_fetcher=lambda s: _FakeTicker(s),
    )
    final_symbols = [spec.symbol for spec, _ in out]
    assert final_symbols == ["FOLKSUSDT", "ALCHUSDT"]
    assert injected == []
    assert skipped == []


def test_load_watchlist_priority_reads_file_and_filters(tmp_path):
    """End-to-end: write a watchlist file, confirm wrapper parses + filters
    exactly as the selector does, with exclusion of an open symbol applied.

    This is the integration that exercises the priority-symbol resolution
    path the cycle engine takes before it prepends to the screener output.
    """
    p = tmp_path / "watchlist.json"
    p.write_text(json.dumps({
        "watchlist": [
            _wl_entry("GTCUSDT", side_bias="long"),
            _wl_entry("USUSDT", side_bias="long"),
            _wl_entry("BUSDT", side_bias="long"),   # excluded (already open)
            _wl_entry("INXUSDT", side_bias="short"),
            _wl_entry("EXPIREDUSDT", side_bias="short",
                      expires_at="2026-05-11T11:00Z"),  # excluded (past)
            _wl_entry("NEUTRALUSDT", side_bias="neutral"),  # excluded
        ]
    }), encoding="utf-8")
    out = _load_watchlist_priority_symbols(
        open_position_symbols={"BUSDT"},
        watchlist_path=p,
        now_utc=_NOW,
    )
    assert out == ["GTCUSDT", "USUSDT", "INXUSDT"]
