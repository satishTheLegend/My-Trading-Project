"""Stdlib-only test runner for Phase 2.

The sandbox doesn't have pytest and can't reach pypi/Binance, so this is the
verification harness. It:

  1. Provides a tiny ``pytest`` shim (approx / raises / fixture / skipif).
  2. Discovers ``test_*`` functions in tests/test_symbol_filters.py,
     tests/test_indicators.py, and tests/test_risk_engine.py.
  3. Resolves fixtures by calling them as plain functions.
  4. Runs each test and prints a green/red summary.
  5. Then runs a synthetic-data end-to-end pipeline (screener-shaped data →
     research → strategy → risk approval) so we know the wiring is correct.

This file is *not* part of the agency runtime. It only exists for development
verification. Real test runs (Phase 3+) should use real pytest.
"""

from __future__ import annotations

import importlib.util
import inspect
import math
import sys
import time
import traceback
import types
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Tiny pytest shim
# ---------------------------------------------------------------------------


class _Approx:
    def __init__(self, expected, abs=None, rel=None):
        self.expected = expected
        self.abs = abs
        if rel is None and abs is None:
            rel = 1e-6
        self.rel = rel

    def __eq__(self, other):
        if isinstance(self.expected, Decimal) or isinstance(other, Decimal):
            a = Decimal(str(self.expected))
            b = Decimal(str(other))
            tol = Decimal(str(self.abs)) if self.abs is not None else abs(a) * Decimal(str(self.rel or 0))
            return abs(a - b) <= tol
        if math.isnan(other) and math.isnan(self.expected):
            return True
        diff = abs(other - self.expected)
        if self.abs is not None and diff <= self.abs:
            return True
        if self.rel is not None and abs(self.expected) > 0 and diff <= abs(self.expected) * self.rel:
            return True
        return diff < 1e-9

    def __repr__(self):
        return f"approx({self.expected!r}, abs={self.abs}, rel={self.rel})"


class _Raises:
    def __init__(self, exc):
        self.exc = exc
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, etype, evalue, tb):
        if etype is None:
            raise AssertionError(f"expected {self.exc.__name__}, no exception raised")
        if not issubclass(etype, self.exc):
            return False
        self.value = evalue
        return True


class _Mark:
    def __getattr__(self, _):
        def deco(*a, **k):
            def wrap(f):
                return f
            return wrap
        return deco


def _fixture(*args, **kwargs):
    if args and callable(args[0]):
        f = args[0]
        f._is_fixture = True
        return f
    def deco(f):
        f._is_fixture = True
        return f
    return deco


pytest_shim = types.SimpleNamespace(
    approx=_Approx,
    raises=_Raises,
    fixture=_fixture,
    mark=_Mark(),
    skip=lambda *a, **k: (_ for _ in ()).throw(SystemExit("skipped")),
)
sys.modules["pytest"] = pytest_shim


# ---------------------------------------------------------------------------
# Test discovery + runner
# ---------------------------------------------------------------------------


def _load(path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _make_builtin_fixture(name: str, mod: types.ModuleType):
    """Lazily build pytest's standard fixtures we depend on."""
    import tempfile
    if name == "tmp_path":
        return Path(tempfile.mkdtemp(prefix="agency-test-"))
    if name == "monkeypatch":
        return _MonkeyPatch()
    return None


class _MonkeyPatch:
    """Minimal stand-in for pytest's monkeypatch.

    Supports setattr (string-target or attr-on-class), setenv, delenv.
    """
    _SENTINEL = object()

    def __init__(self):
        self._undo: list = []
        self._env_undo: list = []

    def setattr(self, target, name=None, value=_SENTINEL):
        # Two calling styles:
        #   monkeypatch.setattr("module.path.attr", value)
        #   monkeypatch.setattr(klass_or_module, "attr", value)
        if isinstance(target, str):
            if name is not _MonkeyPatch._SENTINEL or value is _MonkeyPatch._SENTINEL:
                # 2-arg form: target, value
                if name is _MonkeyPatch._SENTINEL:
                    raise ValueError("setattr 2-arg string form needs (target, value)")
                value = name
            module_path, attr = target.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_path)
            old = getattr(mod, attr)
            setattr(mod, attr, value)
            self._undo.append((mod, attr, old))
        else:
            if name is None or value is _MonkeyPatch._SENTINEL:
                raise ValueError("setattr 3-arg form needs (target, attr_name, value)")
            old = getattr(target, name)
            setattr(target, name, value)
            self._undo.append((target, name, old))

    def setenv(self, name: str, value: str):
        import os
        old = os.environ.get(name, _MonkeyPatch._SENTINEL)
        os.environ[name] = value
        self._env_undo.append((name, old))

    def delenv(self, name: str, raising: bool = True):
        import os
        if name not in os.environ:
            if raising:
                raise KeyError(name)
            return
        old = os.environ[name]
        del os.environ[name]
        self._env_undo.append((name, old))

    def undo(self):
        for target, attr, old in reversed(self._undo):
            setattr(target, attr, old)
        self._undo.clear()
        import os
        for name, old in reversed(self._env_undo):
            if old is _MonkeyPatch._SENTINEL:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old
        self._env_undo.clear()


def _resolve_callable(fn, fixtures: dict, mod: types.ModuleType,
                      cleanup_callbacks: list, depth: int = 0):
    """Call ``fn`` after recursively resolving its fixture/built-in arguments."""
    if depth > 5:
        raise RuntimeError(f"fixture resolution too deep on {fn}")
    sig = inspect.signature(fn)
    kwargs: dict = {}
    for pname, _ in sig.parameters.items():
        if pname in fixtures:
            kwargs[pname] = _resolve_callable(fixtures[pname], fixtures, mod,
                                              cleanup_callbacks, depth + 1)
        else:
            builtin = _make_builtin_fixture(pname, mod)
            if builtin is not None:
                kwargs[pname] = builtin
                if isinstance(builtin, _MonkeyPatch):
                    cleanup_callbacks.append(builtin.undo)
    return fn(**kwargs)


def _run_module(mod: types.ModuleType) -> tuple[int, int, list[str]]:
    fixtures = {
        name: getattr(mod, name)
        for name in dir(mod)
        if callable(getattr(mod, name)) and getattr(getattr(mod, name), "_is_fixture", False)
    }
    tests = [
        (name, getattr(mod, name))
        for name in dir(mod)
        if name.startswith("test_") and callable(getattr(mod, name))
    ]
    passed = 0
    failed = 0
    failures: list[str] = []
    for name, fn in tests:
        cleanup_callbacks: list = []
        try:
            _resolve_callable(fn, fixtures, mod, cleanup_callbacks)
        except Exception:
            failed += 1
            failures.append(f"FAIL: {mod.__name__}::{name}\n{traceback.format_exc()}")
            sys.stdout.write("F")
        else:
            passed += 1
            sys.stdout.write(".")
        finally:
            for cb in cleanup_callbacks:
                try:
                    cb()
                except Exception:
                    pass
        sys.stdout.flush()
    sys.stdout.write("\n")
    return passed, failed, failures


def run_unit_tests() -> bool:
    test_files = [
        ROOT / "tests" / "test_symbol_filters.py",
        ROOT / "tests" / "test_indicators.py",
        ROOT / "tests" / "test_risk_engine.py",
        ROOT / "tests" / "test_paper_execution.py",
        ROOT / "tests" / "test_positions_store.py",
        ROOT / "tests" / "test_exit_simulator.py",
        ROOT / "tests" / "test_backtester.py",
        ROOT / "tests" / "test_learning.py",
        ROOT / "tests" / "test_binance_signed_client.py",
        ROOT / "tests" / "test_live_execution.py",
        ROOT / "tests" / "test_position_manager.py",
        ROOT / "tests" / "test_emergency_close.py",
        ROOT / "tests" / "test_approval_policy.py",
        ROOT / "tests" / "test_pending_approvals.py",
        ROOT / "tests" / "test_execution_router.py",
        ROOT / "tests" / "test_safety_state.py",
        ROOT / "tests" / "test_limits.py",
        ROOT / "tests" / "test_env_loader.py",
        ROOT / "tests" / "test_mode_manager.py",
        ROOT / "tests" / "test_profit_protection.py",
        ROOT / "tests" / "test_telegram_commands.py",
        ROOT / "tests" / "test_binance_position_sync.py",
    ]
    total_passed = 0
    total_failed = 0
    all_failures: list[str] = []
    for path in test_files:
        print(f"\n{path.relative_to(ROOT)}:")
        mod = _load(path)
        p, f, fails = _run_module(mod)
        total_passed += p
        total_failed += f
        all_failures.extend(fails)
    print(f"\n=== unit tests: {total_passed} passed, {total_failed} failed ===")
    for f in all_failures:
        print(f)
    return total_failed == 0


# ---------------------------------------------------------------------------
# Synthetic end-to-end pipeline
# ---------------------------------------------------------------------------


def run_synthetic_pipeline() -> bool:
    """Exercise screener-research-strategy-risk on synthetic Binance-shaped data.

    Builds 200 fake 1h candles for a fictional decimal-priced token in a
    clean uptrend with a recent pullback (good setup for ``pullback_long``),
    feeds them through every Phase 2 module, and asserts:

      - research produces non-empty timeframe summaries
      - strategy ranking returns at least one scored strategy
      - risk engine produces a deterministic decision (approved / rejected)
    """
    from scripts.market_data import Candle, Ticker24h, MarkPriceSnapshot, OrderBook, OrderBookLevel
    from scripts.indicators import ema, rsi, support_resistance
    from scripts.risk_engine import evaluate_proposal, RiskConfig
    from scripts.strategy_scoring import rank_strategies
    from scripts.symbol_filters import parse_symbol_spec, round_price
    from scripts.token_research import (
        TokenResearchReport, TimeframeSnapshot, StructureFlags, LiquidityProfile,
    )

    # 1) build a synthetic SymbolSpec.
    raw = {
        "symbol": "FAKEUSDT", "pair": "FAKEUSDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "FAKE", "quoteAsset": "USDT",
        "pricePrecision": 5, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "10000000", "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1", "maxQty": "5900000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    spec = parse_symbol_spec(raw)
    assert spec.is_decimal_priced

    # 2) Build a TokenResearchReport directly (skip the live HTTP fetch).
    # Price 0.66% above 1h support → pullback_long should fire confidently.
    last_close = Decimal("0.07550")

    def tf(interval: str, ema_fast: float, ema_slow: float, trend: str, rsi_v: float) -> TimeframeSnapshot:
        from scripts.indicators import SRLevels
        return TimeframeSnapshot(
            interval=interval,
            candles_examined=200,
            last_close=last_close,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            ema_trend=trend,
            rsi_14=rsi_v,
            atr_pct=1.2,
            realized_vol_pct=15.0,
            sr=SRLevels(
                supports=(0.07500, 0.07350),
                resistances=(0.07800, 0.08000),
            ),
            pct_from_nearest_resistance=3.31,   # 0.07800 vs 0.07550
            pct_from_nearest_support=0.66,
            last_three_close_changes_pct=(-0.5, -0.3, +0.2),
            avg_volume_quote=2_500_000.0,
            last_volume_quote=2_700_000.0,
            volume_ratio=1.08,
        )

    timeframes = {
        "4h":  tf("4h",  0.0758, 0.0748, "up", 58.0),
        "1h":  tf("1h",  0.0758, 0.0750, "up", 48.0),
        "15m": tf("15m", 0.0760, 0.0756, "up", 45.0),
        "5m":  tf("5m",  0.0758, 0.0756, "flat", 50.0),
    }
    structure = StructureFlags(
        is_in_uptrend_1h=True, is_in_downtrend_1h=False,
        is_overextended_long=False, is_overextended_short=False,
        has_recent_pump=False, has_recent_dump=False,
        failed_breakout_long=False, failed_breakout_short=False,
        pct_from_24h_high=-2.5, pct_from_24h_low=4.0,
    )
    liquidity = LiquidityProfile(
        spread_bps=4.0,
        bid_depth_within_0_5pct_usdt=8000.0,
        ask_depth_within_0_5pct_usdt=8200.0,
        bid_depth_within_2pct_usdt=42000.0,
        ask_depth_within_2pct_usdt=44000.0,
        is_liquid_for_small_position=True,
    )
    report = TokenResearchReport(
        symbol="FAKEUSDT",
        is_decimal_priced=True,
        last_price=last_close,
        mark_price=last_close,
        funding_rate_8h=Decimal("0.0001"),
        next_funding_in_minutes=180,
        open_interest_base=Decimal("123456"),
        open_interest_quote_usdt=Decimal("9450"),
        ticker_24h={
            "open": "0.07350", "high": "0.07854", "low": "0.07350",
            "last": "0.07654", "change_pct": "4.13",
            "quote_volume_usdt": "8500000", "trades": 42000,
        },
        timeframes=timeframes,
        structure=structure,
        liquidity=liquidity,
        no_trade_reasons=tuple(),
        spec=spec,
    )

    # 3) Run strategy ranking.
    ranking = rank_strategies(report)
    assert ranking.scores, "strategy ranking should produce scores"
    print(f"  → strategies scored: {len(ranking.scores)}, best="
          f"{ranking.best.strategy if ranking.best else 'no_trade'} "
          f"({ranking.best.confidence:.2f} confidence)" if ranking.best else
          f"  → strategies scored: {len(ranking.scores)}, best=no_trade")
    assert ranking.best is not None, "uptrend-with-pullback should produce a tradeable signal"
    assert ranking.best.side == "LONG"
    assert ranking.best.entry_zone is not None
    assert ranking.best.invalidation is not None
    assert ranking.best.take_profit_targets

    # 4) Run risk evaluation. Tick-align all three prices first — Binance
    # rejects orders that aren't multiples of PRICE_FILTER.tickSize.
    entry_mid = (ranking.best.entry_zone[0] + ranking.best.entry_zone[1]) / Decimal("2")
    side = ranking.best.side
    entry = round_price(spec, entry_mid, mode="down")
    stop = round_price(
        spec, ranking.best.invalidation,
        mode="down" if side == "LONG" else "up",
    )
    tp1 = round_price(
        spec, ranking.best.take_profit_targets[0],
        mode="down" if side == "LONG" else "up",
    )
    # Use the realistic 2 USDT-margin / 8% loss config — the default 1 USDT
    # margin / 5% loss combo is too tight to clear MIN_NOTIONAL on most
    # decimal-priced tokens.
    approval = evaluate_proposal(
        proposal_id="SMOKE-001",
        spec=spec,
        side=ranking.best.side,
        entry_price=entry,
        stop_price=stop,
        take_profit_price=tp1,
        cfg=RiskConfig(
            default_margin_per_trade_usdt=Decimal("2"),
            max_margin_per_trade_usdt=Decimal("2"),
            max_planned_loss_pct_of_margin=Decimal("0.08"),
        ),
    )
    print(f"  → risk decision: {approval.risk_decision} ({approval.risk_reason[:80]})")
    assert approval.risk_decision in ("approved", "reduce_size", "rejected", "lower_leverage", "wait")
    if approval.sizing:
        print(f"  → sizing: qty={approval.sizing.quantity} margin={approval.sizing.margin_usdt:.4f} "
              f"USDT lev={approval.sizing.leverage}x notional={approval.sizing.notional_usdt:.4f} USDT")
        assert approval.sizing.quantity > 0
    if approval.liquidation:
        print(f"  → liquidation: {approval.liquidation.liquidation_price} "
              f"(distance {approval.liquidation.distance_pct:.2f}%)")
    if approval.profit:
        print(f"  → profit at TP1: gross={approval.profit.gross_profit_usdt:.4f} "
              f"net={approval.profit.net_profit_usdt:.4f} "
              f"({approval.profit.net_profit_pct_of_margin:.2f}% of margin) "
              f"R:R={approval.profit.risk_reward_ratio:.2f}")

    return True


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def run_phase3_pipeline() -> bool:
    """End-to-end Phase 3 pipeline against synthetic candles:

      open via paper_execution → watch with exit_simulator → close →
      append to trade-journal → generate learning report → assert wins counted.
    """
    import datetime as dt
    import json
    import tempfile
    from decimal import Decimal

    from scripts.exit_simulator import (
        DECISION_FULL_TP, DECISION_HOLD, DECISION_STOP_HIT,
        apply_decision, decide_from_candle,
    )
    from scripts.market_data import Candle, OrderBook, OrderBookLevel
    from scripts.paper_execution import simulate_market_fill
    from scripts.positions_store import Position, PositionsStore, make_position_id
    from scripts.symbol_filters import parse_symbol_spec
    from scripts.journal_writer import append_paper_trade, TRADE_JOURNAL
    from scripts import learning, journal_writer

    # 1) Synthetic spec.
    raw = {
        "symbol": "FAKE3USDT", "pair": "FAKE3USDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "FAKE3", "quoteAsset": "USDT",
        "pricePrecision": 5, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "10000000", "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1", "maxQty": "5900000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    spec = parse_symbol_spec(raw)

    # 2) Order book → simulate a market LONG fill.
    book = OrderBook(
        symbol=spec.symbol, last_update_id=1,
        bids=(OrderBookLevel(price=Decimal("0.07650"), quantity=Decimal("1000")),),
        asks=(
            OrderBookLevel(price=Decimal("0.07655"), quantity=Decimal("100")),
            OrderBookLevel(price=Decimal("0.07656"), quantity=Decimal("200")),
        ),
        transaction_time_ms=1,
    )
    fill = simulate_market_fill("LONG", Decimal("80"), book)
    print(f"  → fill: qty={fill.filled_qty} avg={fill.average_price} "
          f"slippage={fill.slippage_bps:.2f} bps")
    assert fill.is_complete

    # 3) Open paper position via positions_store, in a temp file.
    with tempfile.TemporaryDirectory() as td:
        store = PositionsStore(Path(td) / "open-positions.json")
        pos = Position(
            position_id=make_position_id(spec.symbol),
            symbol=spec.symbol, side="LONG", status="open",
            entry_price=fill.average_price,
            quantity=fill.filled_qty, initial_quantity=fill.filled_qty,
            leverage=3, margin_mode="ISOLATED",
            margin_usdt=Decimal("2"), notional_usdt=fill.notional_usdt,
            stop_loss=Decimal("0.07550"),
            take_profit_targets=[Decimal("0.07750"), Decimal("0.07850")],
            unrealized_pnl=Decimal("0"),
            realized_pnl=-fill.fees_usdt,
            max_favorable_pnl=Decimal("0"), max_adverse_pnl=Decimal("0"),
            liquidation_price=Decimal("0.05100"),
            fees_paid_usdt=fill.fees_usdt, funding_paid_usdt=Decimal("0"),
            proposal_id="SMOKE-PHASE3-001", strategy="pullback_long",
            market_regime="bullish",
            opened_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            updated_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            closed_at=None, exit_price=None, exit_reason=None, mode="PAPER_TRADING",
        )
        store.upsert(pos)
        assert len(store.load_open()) == 1

        # 4) Walk through 3 candles. Bar 1 = grind up. Bar 2 = tag final TP.
        bar1 = Candle(
            open_time_ms=2, open=Decimal("0.07655"), high=Decimal("0.07700"),
            low=Decimal("0.07650"), close=Decimal("0.07690"),
            volume=Decimal("100000"), close_time_ms=2 + 60_000,
            quote_volume=Decimal("7700"), trades=50,
            taker_buy_base_volume=Decimal("60000"),
            taker_buy_quote_volume=Decimal("4620"),
        )
        bar2 = Candle(
            open_time_ms=2 + 60_000, open=Decimal("0.07690"),
            high=Decimal("0.07870"),       # blasts past final TP @ 0.07850
            low=Decimal("0.07680"), close=Decimal("0.07820"),
            volume=Decimal("250000"), close_time_ms=2 + 120_000,
            quote_volume=Decimal("19550"), trades=120,
            taker_buy_base_volume=Decimal("180000"),
            taker_buy_quote_volume=Decimal("14062"),
        )

        for bar in (bar1, bar2):
            pos.update_pnl(bar.close)
            d = decide_from_candle(pos, bar)
            apply_decision(pos, d)
            print(f"  → bar close={bar.close}: {d.decision} ({d.reason[:60]})")

        store.upsert(pos)

        assert pos.status == "closed", f"expected closed, got {pos.status}"
        assert pos.exit_reason in ("partial_tp", "full_tp"), pos.exit_reason
        assert pos.realized_pnl > 0, f"expected profit, got {pos.realized_pnl}"
        print(f"  → final: status={pos.status} exit_reason={pos.exit_reason} "
              f"net_pnl={pos.realized_pnl}")

        # 5) Append a trade-journal entry, run learning report on it.
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix="-trade-journal.md",
            dir=td, delete=False,
        ) as tf:
            tf.write("# trade-journal.md\n\n")
            tj_path = Path(tf.name)
        old_tj = journal_writer.TRADE_JOURNAL
        journal_writer.TRADE_JOURNAL = tj_path
        try:
            for i in range(25):       # 25 wins to clear default floor=20
                append_paper_trade({
                    "trade_id": f"TRADE-SMOKE-{i:03d}",
                    "proposal_id": f"PROP-SMOKE-{i}",
                    "mode": "PAPER_TRADING",
                    "symbol": spec.symbol,
                    "side": "LONG",
                    "strategy": "pullback_long",
                    "market_regime": "bullish",
                    "entry_time": "2026-05-10T10:00:00Z",
                    "entry_price": str(pos.entry_price),
                    "quantity": str(pos.initial_quantity),
                    "leverage": 3, "margin_mode": "ISOLATED",
                    "margin_usdt": "2", "notional_usdt": str(pos.notional_usdt),
                    "stop_loss": str(pos.stop_loss),
                    "take_profit_targets": [str(t) for t in pos.take_profit_targets],
                    "exit_time": "2026-05-10T11:00:00Z",
                    "exit_price": str(pos.exit_price),
                    "exit_reason": pos.exit_reason,
                    "gross_pnl_usdt": str(pos.realized_pnl + pos.fees_paid_usdt),
                    "fees_usdt": str(pos.fees_paid_usdt),
                    "funding_usdt": "0",
                    "slippage_usdt": "0",
                    "net_pnl_usdt": str(pos.realized_pnl),
                    "max_favorable_pnl_usdt": str(pos.max_favorable_pnl),
                    "max_adverse_pnl_usdt": str(pos.max_adverse_pnl),
                    "mistake_tags": [],
                    "lessons": "",
                    "order_ids": [],
                })
            empty_rj = Path(td) / "rejected.md"
            empty_rj.write_text("# rejected\n\n", encoding="utf-8")
            report = learning.generate_report(tj_path, empty_rj, statistical_floor=20)
            print(f"  → learning: trades_analyzed={report.trades_analyzed} "
                  f"win_rate={report.overall.get('win_rate')} "
                  f"insights={len(report.insights)}")
            assert report.trades_analyzed == 25
            assert any(i.requires_user_approval for i in report.insights)
        finally:
            journal_writer.TRADE_JOURNAL = old_tj

    return True


def run_phase5_pipeline() -> bool:
    """End-to-end Phase 5 routing test.

    Builds a fake LiveExecution + a synthetic order book, then runs three
    proposals through the router:
      A) small notional (~$8)   → auto-fires
      B) large notional (~$80)  → queues for approval
      C) approve B and let the worker fire it

    Asserts that the threshold rule and the queue lifecycle behave correctly.
    """
    import tempfile
    from decimal import Decimal
    from pathlib import Path

    from scripts.execution_router import ExecutionRouter
    from scripts.live_execution import OrderResult
    from scripts.market_data import OrderBook, OrderBookLevel
    from scripts.pending_approvals import PendingApprovalsStore
    from scripts.symbol_filters import parse_symbol_spec

    raw = {
        "symbol": "FAKE5USDT", "pair": "FAKE5USDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "FAKE5", "quoteAsset": "USDT",
        "pricePrecision": 5, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "10000000", "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1", "maxQty": "5900000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    spec = parse_symbol_spec(raw)

    class _FakeLive:
        def __init__(self):
            self.next_id = 5000
            self.calls = []
        def set_margin_mode(self, *a, **k): self.calls.append(("margin", a, k)); return {}
        def set_leverage(self, *a, **k): self.calls.append(("lev", a, k)); return {}
        def place_market_entry(self, sp, *, side, quantity, risk_approval_id, client_order_id=None):
            self.calls.append(("entry", sp.symbol, side, str(quantity)))
            oid = self.next_id; self.next_id += 1
            return OrderResult(
                success=True, order_id=oid, client_order_id=client_order_id,
                status="FILLED", symbol=sp.symbol, side="BUY" if side == "LONG" else "SELL",
                type="MARKET",
                avg_price=Decimal("0.07655"), executed_qty=quantity,
                cum_quote=Decimal("0.07655") * quantity,
                reduce_only=False, raw={},
            )

    fake = _FakeLive()
    with tempfile.TemporaryDirectory() as td:
        store = PendingApprovalsStore(Path(td) / "pending.json")
        router = ExecutionRouter(live_execution=fake, approvals_store=store)
        router._first_live_trade_done = True   # skip first-trade defensive rule

        # A) Small notional → auto-fire.
        out_a = router.route(
            mode="SEMI_AUTO_LIVE", proposal_id="P-A", spec=spec, side="LONG",
            quantity=Decimal("100"), entry_price=Decimal("0.07655"),
            stop_loss=Decimal("0.07500"),
            take_profit_targets=[Decimal("0.07800")],
            leverage=3, margin_mode="ISOLATED",
            margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.008"),
            liquidation_price=None, strategy="pullback_long",
        )
        print(f"  → A ({out_a.notional_usdt:.4f} USDT): {out_a.status}")
        assert out_a.status == "filled", f"expected filled, got {out_a.status}"

        # B) Large notional → queue.
        out_b = router.route(
            mode="SEMI_AUTO_LIVE", proposal_id="P-B", spec=spec, side="LONG",
            quantity=Decimal("1100"), entry_price=Decimal("0.07655"),
            stop_loss=Decimal("0.07500"),
            take_profit_targets=[Decimal("0.07800")],
            leverage=3, margin_mode="ISOLATED",
            margin_usdt=Decimal("28"), estimated_fees_usdt=Decimal("0.084"),
            liquidation_price=None, strategy="pullback_long",
        )
        print(f"  → B ({out_b.notional_usdt:.4f} USDT): {out_b.status} "
              f"(rules: {out_b.approval.triggered_rules if out_b.approval else []})")
        assert out_b.status == "queued_for_approval"
        assert out_b.approval is not None

        # C) User approves B; worker fires it.
        store.transition(out_b.approval.approval_id, to="approved", notes="smoke-test approval")
        outs = router.execute_approved_queue(spec_lookup={"FAKE5USDT": spec})
        print(f"  → worker executed {len(outs)} approved item(s)")
        assert len(outs) == 1 and outs[0].status == "filled"
        after = store.find(out_b.approval_id) if hasattr(out_b, "approval_id") else \
                store.find(out_b.approval.approval_id)
        assert after.status == "executed"

    return True


def run_phase6_pipeline() -> bool:
    """Phase 6 end-to-end: simulate three losing closes, observe auto-pause,
    confirm next cycle refuses to trade.
    """
    import tempfile
    from decimal import Decimal
    from pathlib import Path

    from scripts.limits import check_proposal
    from scripts.safety_state import SafetyLimits, SafetyStateManager

    with tempfile.TemporaryDirectory() as td:
        manager = SafetyStateManager(
            risk_state_path=Path(td) / "risk-state.json",
            system_health_path=Path(td) / "system-health.json",
            limits=SafetyLimits(
                daily_loss_limit_usdt=Decimal("1.5"),
                consecutive_loss_limit=3,
                cooldown_minutes_after_consecutive_losses=60,
            ),
        )

        # 3 losses in a row → consecutive-loss breach + cooldown.
        for i in range(3):
            state = manager.record_trade_close(net_pnl_usdt=Decimal("-0.10"))
            print(f"  → after loss {i+1}: consec={state.consecutive_losses} "
                  f"daily_pnl={state.daily_pnl_usdt} paused={state.trading_paused}")
        assert state.trading_paused
        assert "consecutive losses" in (state.paused_reason or "")
        assert state.paused_until_iso is not None

        # check_can_trade returns False with the breach reason.
        s2, can_trade, why = manager.check_can_trade()
        print(f"  → check_can_trade: can={can_trade}, why={why[:60]}")
        assert not can_trade

        # And limits.check_proposal mirrors the same.
        lc = check_proposal(
            state=s2, limits=manager.limits,
            proposed_symbol="DOGEUSDT", open_positions=[], fired_this_cycle=0,
        )
        assert not lc.ok
        assert "paused" in lc.breached or "consecutive_loss_limit" in lc.breached

        # Manual resume → trading allowed again.
        manager.resume()
        s3, can_trade, _ = manager.check_can_trade()
        print(f"  → after manual resume: can_trade={can_trade}, "
              f"consec={s3.consecutive_losses} (counter persists)")
        assert can_trade
        assert s3.consecutive_losses == 3   # counter doesn't reset on manual resume

        # A winning trade resets the consecutive counter.
        s4 = manager.record_trade_close(net_pnl_usdt=Decimal("0.50"))
        print(f"  → after winning trade: consec={s4.consecutive_losses} "
              f"daily_pnl={s4.daily_pnl_usdt}")
        assert s4.consecutive_losses == 0
        assert s4.consecutive_wins == 1

    return True


def main() -> int:
    print("=" * 60)
    print("Phase 2 + 3 + 5 + 6 offline verification")
    print("=" * 60)

    t0 = time.monotonic()
    units_ok = run_unit_tests()

    print("\n--- Phase 2 synthetic pipeline (research → strategy → risk) ---")
    try:
        p2_ok = run_synthetic_pipeline()
    except Exception:
        traceback.print_exc()
        p2_ok = False

    print("\n--- Phase 3 synthetic pipeline (fill → watch → exit → journal → learning) ---")
    try:
        p3_ok = run_phase3_pipeline()
    except Exception:
        traceback.print_exc()
        p3_ok = False

    print("\n--- Phase 5 synthetic pipeline (router: small auto / large queue / worker fires) ---")
    try:
        p5_ok = run_phase5_pipeline()
    except Exception:
        traceback.print_exc()
        p5_ok = False

    print("\n--- Phase 6 synthetic pipeline (3 losses → auto-pause → resume → win → reset) ---")
    try:
        p6_ok = run_phase6_pipeline()
    except Exception:
        traceback.print_exc()
        p6_ok = False

    elapsed = time.monotonic() - t0
    print(f"\ntotal time: {elapsed:.2f}s")
    if units_ok and p2_ok and p3_ok and p5_ok and p6_ok:
        print("ALL GREEN")
        return 0
    print("RED — see failures above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
