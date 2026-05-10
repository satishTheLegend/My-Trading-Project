"""Walk-forward backtester.

Replay historical Binance candles bar-by-bar to evaluate the agency's
strategy + risk + exit chain. Produces aggregate stats the Learning Agent
consumes.

Approach
--------
For a given symbol and timeframe (default 1h):

  1. Fetch ``lookback_bars`` candles ending now.
  2. For every bar i in [warmup, lookback_bars):
        - Build a synthetic ``TokenResearchReport`` from the prefix candles[:i]
          (multi-timeframe summaries collapsed onto the entry timeframe to
          keep the backtest self-contained).
        - Run strategy_scoring.rank_strategies → best.
        - If a position is open: feed candles[i] to exit_simulator.
        - If flat and a setup exists: paper-execute at candles[i].close,
          open the position, record proposal_id.
  3. Aggregate per-strategy / per-symbol stats.

Limitations (honest)
--------------------
- Single timeframe only — we don't currently fetch lower TFs from history,
  so the multi-TF research collapses onto the backtest interval. This biases
  results slightly toward "trade what you can see" — fine for relative
  comparisons, less reliable for absolute PnL.
- No funding/borrow simulation. Phase 4 will add it for live testnet.
- No multiple-position handling per symbol.
- Order-book slippage is approximated via a flat bps cost (default 5 bps);
  real depth-aware backtesting requires historical L2 which Binance doesn't
  expose for free.

Phase 5+ swaps in a higher-fidelity engine if needed.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Sequence

from .exit_simulator import (
    DECISION_HOLD,
    ExitConfig,
    apply_decision,
    decide_from_candle,
)
from .indicators import (
    SRLevels,
    atr,
    ema,
    pct_change,
    realized_volatility_pct,
    rsi,
    support_resistance,
)
from .market_data import Candle, MarketData
from .positions_store import Position, make_position_id
from .risk_engine import (
    DEFAULT_TAKER_FEE,
    RiskConfig,
    evaluate_proposal,
)
from .strategy_scoring import StrategyRanking, rank_strategies
from .symbol_filters import SymbolSpec, round_price
from .token_research import (
    LiquidityProfile,
    StructureFlags,
    TimeframeSnapshot,
    TokenResearchReport,
)


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass
class BacktestTrade:
    proposal_id: str
    symbol: str
    side: str
    strategy: str
    entry_bar: int
    entry_time_ms: int
    entry_price: Decimal
    exit_bar: int | None
    exit_time_ms: int | None
    exit_price: Decimal | None
    exit_reason: str | None
    realized_pnl: Decimal
    fees: Decimal
    quantity: Decimal
    margin_usdt: Decimal
    leverage: int
    max_favorable_pnl: Decimal
    max_adverse_pnl: Decimal
    bars_held: int

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "side": self.side,
            "strategy": self.strategy,
            "entry_bar": self.entry_bar,
            "entry_time_ms": self.entry_time_ms,
            "entry_price": str(self.entry_price),
            "exit_bar": self.exit_bar,
            "exit_time_ms": self.exit_time_ms,
            "exit_price": str(self.exit_price) if self.exit_price is not None else None,
            "exit_reason": self.exit_reason,
            "realized_pnl": str(self.realized_pnl),
            "fees": str(self.fees),
            "quantity": str(self.quantity),
            "margin_usdt": str(self.margin_usdt),
            "leverage": self.leverage,
            "max_favorable_pnl": str(self.max_favorable_pnl),
            "max_adverse_pnl": str(self.max_adverse_pnl),
            "bars_held": self.bars_held,
        }


@dataclass
class BacktestResult:
    symbol: str
    interval: str
    bars_examined: int
    warmup_bars: int
    proposals_generated: int
    proposals_approved: int
    trades: list[BacktestTrade]
    aggregate: dict[str, Any]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "bars_examined": self.bars_examined,
            "warmup_bars": self.warmup_bars,
            "proposals_generated": self.proposals_generated,
            "proposals_approved": self.proposals_approved,
            "trades": [t.to_jsonable() for t in self.trades],
            "aggregate": self.aggregate,
        }


# ----------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------


def backtest_symbol(
    market: MarketData,
    spec: SymbolSpec,
    *,
    interval: str = "1h",
    lookback_bars: int = 500,
    warmup_bars: int = 100,
    risk_cfg: RiskConfig | None = None,
    exit_cfg: ExitConfig | None = None,
    fee_rate: Decimal = DEFAULT_TAKER_FEE,
) -> BacktestResult:
    """Run a single-symbol walk-forward backtest.

    The risk_cfg defaults are tuned for the user's 10-USDT-wallet reality
    (2 USDT margin, 8% max-loss budget) so the backtest reflects the same
    constraints the live agency operates under.
    """
    risk_cfg = risk_cfg or RiskConfig(
        default_margin_per_trade_usdt=Decimal("2"),
        max_margin_per_trade_usdt=Decimal("2"),
        default_leverage=3,
        max_leverage=5,
        max_planned_loss_pct_of_margin=Decimal("0.08"),
    )
    exit_cfg = exit_cfg or ExitConfig()

    candles = market.get_klines(spec.symbol, interval, limit=lookback_bars)
    if len(candles) < warmup_bars + 5:
        return BacktestResult(
            symbol=spec.symbol, interval=interval, bars_examined=len(candles),
            warmup_bars=warmup_bars, proposals_generated=0, proposals_approved=0,
            trades=[], aggregate={"error": "insufficient candles"},
        )

    return backtest_candles(
        spec, candles,
        interval=interval,
        warmup_bars=warmup_bars,
        risk_cfg=risk_cfg,
        exit_cfg=exit_cfg,
        fee_rate=fee_rate,
    )


def backtest_candles(
    spec: SymbolSpec,
    candles: Sequence[Candle],
    *,
    interval: str = "1h",
    warmup_bars: int = 100,
    risk_cfg: RiskConfig | None = None,
    exit_cfg: ExitConfig | None = None,
    fee_rate: Decimal = DEFAULT_TAKER_FEE,
) -> BacktestResult:
    """Run the backtest loop on an in-memory candle list. The unit-tested
    surface — keeps offline tests fast and deterministic.
    """
    risk_cfg = risk_cfg or RiskConfig()
    exit_cfg = exit_cfg or ExitConfig()

    open_pos: Position | None = None
    open_entry_bar: int = -1
    trades: list[BacktestTrade] = []
    proposals_generated = 0
    proposals_approved = 0
    seq = 0

    for i in range(warmup_bars, len(candles)):
        prefix = candles[: i + 1]
        bar = candles[i]

        # ---- 1) Manage open position first ----
        if open_pos is not None:
            atr_series = atr(prefix, period=14)
            atr_v: Decimal | None = None
            if atr_series and atr_series[-1] == atr_series[-1]:
                atr_v = Decimal(str(atr_series[-1]))
            open_pos.update_pnl(bar.close)
            decision = decide_from_candle(
                open_pos, bar, cfg=exit_cfg, atr_value=atr_v,
            )
            apply_decision(open_pos, decision, fee_rate=fee_rate)

            if open_pos.status == "closed":
                trades.append(BacktestTrade(
                    proposal_id=open_pos.proposal_id,
                    symbol=open_pos.symbol,
                    side=open_pos.side,
                    strategy=open_pos.strategy,
                    entry_bar=open_entry_bar,
                    entry_time_ms=int(candles[open_entry_bar].close_time_ms),
                    entry_price=open_pos.entry_price,
                    exit_bar=i,
                    exit_time_ms=int(bar.close_time_ms),
                    exit_price=open_pos.exit_price,
                    exit_reason=open_pos.exit_reason,
                    realized_pnl=open_pos.realized_pnl,
                    fees=open_pos.fees_paid_usdt,
                    quantity=open_pos.initial_quantity,
                    margin_usdt=open_pos.margin_usdt,
                    leverage=open_pos.leverage,
                    max_favorable_pnl=open_pos.max_favorable_pnl,
                    max_adverse_pnl=open_pos.max_adverse_pnl,
                    bars_held=i - open_entry_bar,
                ))
                open_pos = None
                open_entry_bar = -1
            # If not closed, skip new-trade scan this bar.
            if open_pos is not None:
                continue

        # ---- 2) Look for a new setup on this bar ----
        report = _build_research_report_from_prefix(spec, prefix, interval)
        ranking = rank_strategies(report)
        if ranking.best is None:
            continue
        proposals_generated += 1

        best = ranking.best
        if not best.entry_zone or best.invalidation is None or not best.take_profit_targets:
            continue

        entry_mid = (best.entry_zone[0] + best.entry_zone[1]) / Decimal("2")
        entry = round_price(spec, entry_mid, mode="down")
        if entry <= 0:
            continue
        stop = round_price(
            spec, best.invalidation,
            mode="down" if best.side == "LONG" else "up",
        )
        tp1 = round_price(
            spec, best.take_profit_targets[0],
            mode="down" if best.side == "LONG" else "up",
        )

        seq += 1
        proposal_id = f"BT-{spec.symbol}-{i:04d}-{seq:03d}"
        approval = evaluate_proposal(
            proposal_id=proposal_id,
            spec=spec,
            side=best.side,
            entry_price=entry,
            stop_price=stop,
            take_profit_price=tp1,
            cfg=risk_cfg,
            fee_rate_per_side=fee_rate,
        )
        if approval.risk_decision != "approved" or approval.sizing is None:
            continue
        proposals_approved += 1

        # Open the paper position at this bar's close. Exit logic kicks in
        # next bar onward.
        sizing = approval.sizing
        open_pos = Position(
            position_id=make_position_id(spec.symbol, seq=seq),
            symbol=spec.symbol,
            side=best.side,
            status="open",
            entry_price=entry,
            quantity=sizing.quantity,
            initial_quantity=sizing.quantity,
            leverage=sizing.leverage,
            margin_mode="ISOLATED",
            margin_usdt=sizing.margin_usdt,
            notional_usdt=sizing.notional_usdt,
            stop_loss=stop,
            take_profit_targets=[round_price(
                spec, t,
                mode="down" if best.side == "LONG" else "up",
            ) for t in best.take_profit_targets],
            unrealized_pnl=Decimal("0"),
            realized_pnl=-sizing.estimated_fees_usdt / Decimal("2"),  # entry fee
            max_favorable_pnl=Decimal("0"),
            max_adverse_pnl=Decimal("0"),
            liquidation_price=approval.liquidation.liquidation_price if approval.liquidation else None,
            fees_paid_usdt=sizing.estimated_fees_usdt / Decimal("2"),
            funding_paid_usdt=Decimal("0"),
            proposal_id=proposal_id,
            strategy=best.strategy,
            market_regime="backtest",
            opened_at=_iso(int(bar.close_time_ms)),
            updated_at=_iso(int(bar.close_time_ms)),
            closed_at=None,
            exit_price=None,
            exit_reason=None,
            mode="BACKTEST",
        )
        open_entry_bar = i

    # If a position is still open at the end of the window, mark-to-market
    # close it for accounting.
    if open_pos is not None:
        last = candles[-1]
        pnl_per_unit = (last.close - open_pos.entry_price) if open_pos.side == "LONG" \
            else (open_pos.entry_price - last.close)
        gross = pnl_per_unit * open_pos.quantity
        exit_fees = (last.close * open_pos.quantity) * fee_rate
        open_pos.realized_pnl += gross - exit_fees
        open_pos.fees_paid_usdt += exit_fees
        open_pos.exit_price = last.close
        open_pos.exit_reason = "backtest_window_end"
        open_pos.closed_at = _iso(int(last.close_time_ms))
        open_pos.status = "closed"
        trades.append(BacktestTrade(
            proposal_id=open_pos.proposal_id,
            symbol=open_pos.symbol,
            side=open_pos.side,
            strategy=open_pos.strategy,
            entry_bar=open_entry_bar,
            entry_time_ms=int(candles[open_entry_bar].close_time_ms),
            entry_price=open_pos.entry_price,
            exit_bar=len(candles) - 1,
            exit_time_ms=int(last.close_time_ms),
            exit_price=open_pos.exit_price,
            exit_reason=open_pos.exit_reason,
            realized_pnl=open_pos.realized_pnl,
            fees=open_pos.fees_paid_usdt,
            quantity=open_pos.initial_quantity,
            margin_usdt=open_pos.margin_usdt,
            leverage=open_pos.leverage,
            max_favorable_pnl=open_pos.max_favorable_pnl,
            max_adverse_pnl=open_pos.max_adverse_pnl,
            bars_held=len(candles) - 1 - open_entry_bar,
        ))

    aggregate = _aggregate(trades)
    return BacktestResult(
        symbol=spec.symbol,
        interval=interval,
        bars_examined=len(candles),
        warmup_bars=warmup_bars,
        proposals_generated=proposals_generated,
        proposals_approved=proposals_approved,
        trades=trades,
        aggregate=aggregate,
    )


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _build_research_report_from_prefix(
    spec: SymbolSpec, prefix: Sequence[Candle], interval: str
) -> TokenResearchReport:
    """Collapse a single-timeframe prefix into a TokenResearchReport.

    For the backtest we only have one TF of candles, so the multi-TF view
    becomes the same TF repeated three times. That's a known limitation —
    callers should treat backtest stats as a relative comparison between
    strategies, not an absolute PnL forecast.
    """
    closes = [c.close for c in prefix]
    last_close = closes[-1]

    ema_fast = ema(closes, 9)
    ema_slow = ema(closes, 21)
    fast_v = ema_fast[-1] if ema_fast and ema_fast[-1] == ema_fast[-1] else float(last_close)
    slow_v = ema_slow[-1] if ema_slow and ema_slow[-1] == ema_slow[-1] else float(last_close)
    if fast_v > slow_v * 1.0015:
        trend = "up"
    elif fast_v < slow_v * 0.9985:
        trend = "down"
    else:
        trend = "flat"

    rsi_v = rsi(closes, 14)[-1] if len(closes) >= 15 else 50.0

    atr_series = atr(prefix, period=14)
    atr_pct = float("nan")
    if atr_series and atr_series[-1] == atr_series[-1] and last_close > 0:
        atr_pct = atr_series[-1] / float(last_close) * 100.0

    rv_pct = realized_volatility_pct(closes, 20)

    sr = support_resistance(prefix, left=3, right=3, cluster_tol_pct=0.3, max_levels_per_side=4)
    pct_from_r = pct_change(float(last_close), float(sr.resistances[0])) if sr.resistances else None
    pct_from_s = pct_change(float(last_close), float(sr.supports[0])) if sr.supports else None

    last_three = []
    for j in range(max(len(prefix) - 3, 1), len(prefix)):
        if j == 0:
            continue
        last_three.append(pct_change(float(prefix[j - 1].close), float(prefix[j].close)))
    while len(last_three) < 3:
        last_three.insert(0, 0.0)

    quote_vols = [float(c.quote_volume) for c in prefix[-50:]]
    avg_qv = sum(quote_vols) / len(quote_vols) if quote_vols else 0.0
    last_qv = quote_vols[-1] if quote_vols else 0.0
    vol_ratio = last_qv / avg_qv if avg_qv > 0 else 1.0

    snap = TimeframeSnapshot(
        interval=interval, candles_examined=len(prefix), last_close=last_close,
        ema_fast=fast_v, ema_slow=slow_v, ema_trend=trend, rsi_14=rsi_v,
        atr_pct=atr_pct, realized_vol_pct=rv_pct, sr=sr,
        pct_from_nearest_resistance=pct_from_r, pct_from_nearest_support=pct_from_s,
        last_three_close_changes_pct=(last_three[0], last_three[1], last_three[2]),
        avg_volume_quote=avg_qv, last_volume_quote=last_qv, volume_ratio=vol_ratio,
    )
    timeframes = {"4h": snap, "1h": snap, "15m": snap, "5m": snap}

    # Structural flags inferred from the same TF view.
    pump = sum(last_three) > 4.0
    dump = sum(last_three) < -4.0
    structure = StructureFlags(
        is_in_uptrend_1h=trend == "up",
        is_in_downtrend_1h=trend == "down",
        is_overextended_long=rsi_v >= 75,
        is_overextended_short=rsi_v <= 25,
        has_recent_pump=pump,
        has_recent_dump=dump,
        failed_breakout_long=False,
        failed_breakout_short=False,
        pct_from_24h_high=pct_change(float(max(c.high for c in prefix[-24:])), float(last_close)) if len(prefix) >= 24 else 0.0,
        pct_from_24h_low=pct_change(float(min(c.low for c in prefix[-24:])), float(last_close)) if len(prefix) >= 24 else 0.0,
    )
    # Liquidity: in the backtest we don't have depth, so assume "ok" if recent
    # quote volume looks healthy.
    liq = LiquidityProfile(
        spread_bps=5.0,
        bid_depth_within_0_5pct_usdt=avg_qv * 0.001,
        ask_depth_within_0_5pct_usdt=avg_qv * 0.001,
        bid_depth_within_2pct_usdt=avg_qv * 0.005,
        ask_depth_within_2pct_usdt=avg_qv * 0.005,
        is_liquid_for_small_position=avg_qv > 100_000,
    )

    return TokenResearchReport(
        symbol=spec.symbol,
        is_decimal_priced=spec.is_decimal_priced,
        last_price=last_close,
        mark_price=last_close,
        funding_rate_8h=Decimal("0"),
        next_funding_in_minutes=240,
        open_interest_base=Decimal("0"),
        open_interest_quote_usdt=Decimal("0"),
        ticker_24h={
            "open": str(prefix[-24].open if len(prefix) >= 24 else prefix[0].open),
            "high": str(max(c.high for c in prefix[-24:])) if len(prefix) >= 24 else str(prefix[-1].high),
            "low": str(min(c.low for c in prefix[-24:])) if len(prefix) >= 24 else str(prefix[-1].low),
            "last": str(last_close),
            "change_pct": "0",
            "quote_volume_usdt": str(sum(c.quote_volume for c in prefix[-24:])) if len(prefix) >= 24 else "0",
            "trades": sum(c.trades for c in prefix[-24:]) if len(prefix) >= 24 else 0,
        },
        timeframes=timeframes,
        structure=structure,
        liquidity=liq,
        no_trade_reasons=tuple(),
        spec=spec,
    )


def _aggregate(trades: list[BacktestTrade]) -> dict[str, Any]:
    if not trades:
        return {
            "trades": 0, "wins": 0, "losses": 0, "win_rate": None,
            "gross_pnl_usdt": "0", "fees_usdt": "0", "net_pnl_usdt": "0",
            "best_trade_pnl": None, "worst_trade_pnl": None,
            "by_strategy": {}, "by_exit_reason": {},
        }
    wins = sum(1 for t in trades if t.realized_pnl > 0)
    losses = sum(1 for t in trades if t.realized_pnl <= 0)
    net = sum((t.realized_pnl for t in trades), Decimal("0"))
    gross = sum((t.realized_pnl + t.fees for t in trades), Decimal("0"))
    fees = sum((t.fees for t in trades), Decimal("0"))

    by_strategy: dict[str, dict[str, Any]] = {}
    for t in trades:
        s = by_strategy.setdefault(t.strategy, {"n": 0, "wins": 0, "net": Decimal("0")})
        s["n"] += 1
        if t.realized_pnl > 0:
            s["wins"] += 1
        s["net"] += t.realized_pnl
    by_strategy_serializable = {
        name: {
            "n": v["n"],
            "wins": v["wins"],
            "win_rate": round(v["wins"] / v["n"], 3) if v["n"] else None,
            "net_pnl_usdt": str(v["net"]),
        } for name, v in by_strategy.items()
    }

    by_exit: dict[str, int] = {}
    for t in trades:
        by_exit[t.exit_reason or "unknown"] = by_exit.get(t.exit_reason or "unknown", 0) + 1

    best = max(trades, key=lambda t: t.realized_pnl)
    worst = min(trades, key=lambda t: t.realized_pnl)

    return {
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(trades), 3),
        "gross_pnl_usdt": str(gross),
        "fees_usdt": str(fees),
        "net_pnl_usdt": str(net),
        "best_trade_pnl": str(best.realized_pnl),
        "worst_trade_pnl": str(worst.realized_pnl),
        "by_strategy": by_strategy_serializable,
        "by_exit_reason": by_exit,
    }


def _iso(ms: int) -> str:
    return dt.datetime.utcfromtimestamp(ms / 1000.0).isoformat(timespec="seconds") + "Z"


__all__ = [
    "BacktestTrade",
    "BacktestResult",
    "backtest_symbol",
    "backtest_candles",
]
