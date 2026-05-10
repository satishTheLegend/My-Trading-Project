"""Learning module: parsing + aggregation + insight derivation."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from scripts.learning import (
    DEFAULT_STATISTICAL_FLOOR,
    JournalRejection,
    JournalTrade,
    StrategyStats,
    append_insights_to_memory,
    generate_report,
)


def _write_journal(path: Path, entries: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# trade-journal.md\n\n" + "\n".join(entries), encoding="utf-8")


def _trade_block(idx: int, strategy: str, symbol: str, net_pnl: str,
                 mfe: str = "0.10", mae: str = "-0.05") -> str:
    return "\n".join([
        f"\n## TRADE-20260510-{idx:03d}",
        "",
        f"- proposal_id: PROP-{idx}",
        "- mode: PAPER_TRADING",
        f"- symbol: {symbol}",
        "- side: LONG",
        f"- strategy: {strategy}",
        "- market_regime: bullish",
        "- entry_time: 2026-05-10T10:00:00Z",
        "- entry_price: 0.07654",
        "- quantity: 100",
        "- leverage: 3",
        "- margin_mode: ISOLATED",
        "- margin_usdt: 2",
        "- notional_usdt: 7.654",
        "- stop_loss: 0.07500",
        "- take_profit_targets: [0.07800, 0.08000]",
        "- exit_time: 2026-05-10T11:00:00Z",
        "- exit_price: 0.07700",
        "- exit_reason: full_tp",
        f"- gross_pnl_usdt: {net_pnl}",
        "- fees_usdt: 0.005",
        "- funding_usdt: 0",
        "- slippage_usdt: 0",
        f"- net_pnl_usdt: {net_pnl}",
        f"- max_favorable_pnl_usdt: {mfe}",
        f"- max_adverse_pnl_usdt: {mae}",
        "- mistake_tags: []",
        "- lessons: ",
        "- order_ids: []",
        "",
    ])


def _rejection_block(idx: int, reason: str) -> str:
    return "\n".join([
        f"\n## REJECTED-20260510-{idx:03d}",
        "",
        f"- proposal_id: PROP-{idx}",
        "- mode: PAPER_TRADING",
        "- symbol: DOGEUSDT",
        "- side: LONG",
        "- strategy: long_breakout",
        "- proposed_at: 2026-05-10T09:30:00Z",
        "- rejected_by: risk-manager",
        f"- rejection_reason: {reason}",
        "- market_regime: bullish",
        "- hindsight_outcome: unclear",
        "- hindsight_notes: ",
        "",
    ])


def test_parses_trades_and_aggregates(tmp_path: Path):
    tj = tmp_path / "trade-journal.md"
    rj = tmp_path / "rejected-trades.md"

    blocks = []
    for i in range(5):
        blocks.append(_trade_block(i + 1, "pullback_long", "DOGEUSDT", "0.20"))
    blocks.append(_trade_block(6, "pullback_long", "DOGEUSDT", "-0.15"))
    _write_journal(tj, blocks)
    rj.parent.mkdir(parents=True, exist_ok=True)
    rj.write_text("# rejected-trades.md\n\n", encoding="utf-8")

    report = generate_report(tj, rj, statistical_floor=3)
    assert report.trades_analyzed == 6
    assert report.overall["wins"] == 5
    assert report.overall["losses"] == 1
    pl = next(s for s in report.by_strategy if s.strategy == "pullback_long")
    assert pl.n == 6
    assert pl.win_rate == pytest.approx(5 / 6, abs=0.01)
    # Total = 5 * 0.20 - 0.15 = 0.85
    assert pl.total_pnl_usdt == Decimal("0.85")


def test_rejection_buckets_normalize(tmp_path: Path):
    tj = tmp_path / "trade-journal.md"
    rj = tmp_path / "rejected-trades.md"
    tj.parent.mkdir(parents=True, exist_ok=True)
    tj.write_text("# trade-journal.md\n\n", encoding="utf-8")
    blocks = [
        _rejection_block(1, "MIN_NOTIONAL 5 requires qty>=66, but loss-at-stop too high"),
        _rejection_block(2, "liquidation distance 8.10% < required 30%"),
        _rejection_block(3, "fees consume too much profit"),
        _rejection_block(4, "spread too wide (35 bps > 20 bps)"),
        _rejection_block(5, "thin order book"),
    ]
    rj.write_text("# rejected-trades.md\n\n" + "\n".join(blocks), encoding="utf-8")

    report = generate_report(tj, rj, statistical_floor=DEFAULT_STATISTICAL_FLOOR)
    assert report.rejections_analyzed == 5
    # The buckets must compress to canonical names.
    keys = set(report.by_rejection_reason.keys())
    assert {
        "min_notional incompatible with budget",
        "liquidation distance too close",
        "fees consume profit",
        "spread too wide",
        "liquidity too thin",
    } & keys


def test_insight_floor_blocks_premature_recommendations(tmp_path: Path):
    tj = tmp_path / "trade-journal.md"
    rj = tmp_path / "rejected-trades.md"
    blocks = [_trade_block(i + 1, "short_after_pump", "BNXUSDT", "0.30") for i in range(5)]
    _write_journal(tj, blocks)
    rj.parent.mkdir(parents=True, exist_ok=True)
    rj.write_text("# rejected-trades.md\n\n", encoding="utf-8")

    report = generate_report(tj, rj, statistical_floor=20)
    # n=5 < floor=20 → only observation, no actionable recommendation.
    short_after = [i for i in report.insights if "short_after_pump" in i.observation]
    assert short_after
    assert short_after[0].requires_user_approval is False
    assert "more data" in short_after[0].recommended_change.lower()


def test_persist_appends_dedupes(tmp_path: Path, monkeypatch):
    insights_path = tmp_path / "learning-insights.md"
    monkeypatch.setattr("scripts.learning.LEARNING_INSIGHTS", insights_path)

    tj = tmp_path / "trade-journal.md"
    rj = tmp_path / "rejected-trades.md"
    blocks = [_trade_block(i + 1, "pullback_long", "DOGEUSDT", "0.30") for i in range(25)]
    _write_journal(tj, blocks)
    rj.write_text("# rejected-trades.md\n\n", encoding="utf-8")

    report = generate_report(tj, rj, statistical_floor=20)
    assert report.insights, "should generate at least one insight at n=25 above floor=20"

    appended_first = append_insights_to_memory(report.insights)
    appended_second = append_insights_to_memory(report.insights)
    assert appended_first == len(report.insights)
    assert appended_second == 0          # dedupe by insight_id
    assert insights_path.exists()
