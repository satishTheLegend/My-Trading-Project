"""Learning & Optimization — aggregate the journal into per-strategy stats and
generate insights.

Reads:
  - memory/trade-journal.md          (executed paper trades)
  - memory/rejected-trades.md        (proposals the Risk Manager turned down)

Produces:
  - structured `LearningReport` (returned to caller / JSON-emitted by the CLI)
  - appended insights in `memory/learning-insights.md` (only if user asked
    via --persist)

Hard rules from agency/learning-policy.md:
  - Never auto-raise leverage / max-loss / wider stops.
  - Never re-enable a paused symbol without user approval.
  - Insights below the statistical floor (default n>=20) are emitted as
    "observations only" — no recommendation attached.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from .journal_writer import REJECTED_TRADES, TRADE_JOURNAL


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEARNING_INSIGHTS = _PROJECT_ROOT / "memory" / "learning-insights.md"

DEFAULT_STATISTICAL_FLOOR = 20


# ----------------------------------------------------------------------------
# Parsed journal entry types
# ----------------------------------------------------------------------------


@dataclass
class JournalTrade:
    trade_id: str
    proposal_id: str
    mode: str
    symbol: str
    side: str
    strategy: str
    market_regime: str
    entry_time: str
    exit_time: str
    exit_reason: str
    net_pnl_usdt: Decimal
    fees_usdt: Decimal
    margin_usdt: Decimal
    max_favorable_pnl_usdt: Decimal
    max_adverse_pnl_usdt: Decimal


@dataclass
class JournalRejection:
    rejection_id: str
    proposal_id: str
    symbol: str
    side: str
    strategy: str
    rejected_by: str
    rejection_reason: str
    market_regime: str
    proposed_at: str


# ----------------------------------------------------------------------------
# Stats / report types
# ----------------------------------------------------------------------------


@dataclass
class StrategyStats:
    strategy: str
    n: int
    wins: int
    losses: int
    win_rate: float | None
    avg_pnl_usdt: Decimal
    total_pnl_usdt: Decimal
    avg_pnl_pct_of_margin: float | None
    largest_win_usdt: Decimal
    largest_loss_usdt: Decimal
    avg_mfe_usdt: Decimal
    avg_mae_usdt: Decimal
    profit_factor: float | None              # gross_profit / |gross_loss|
    expectancy_per_trade_usdt: Decimal       # net_pnl / n

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "n": self.n, "wins": self.wins, "losses": self.losses,
            "win_rate": self.win_rate,
            "avg_pnl_usdt": str(self.avg_pnl_usdt),
            "total_pnl_usdt": str(self.total_pnl_usdt),
            "avg_pnl_pct_of_margin": self.avg_pnl_pct_of_margin,
            "largest_win_usdt": str(self.largest_win_usdt),
            "largest_loss_usdt": str(self.largest_loss_usdt),
            "avg_mfe_usdt": str(self.avg_mfe_usdt),
            "avg_mae_usdt": str(self.avg_mae_usdt),
            "profit_factor": self.profit_factor,
            "expectancy_per_trade_usdt": str(self.expectancy_per_trade_usdt),
        }


@dataclass
class Insight:
    insight_id: str
    category: str                 # screening | strategy | risk | execution | exit | reporting
    observation: str
    evidence: dict[str, Any]      # at least: sample_size, win_rate, avg_pnl, regime
    recommended_change: str
    requires_user_approval: bool
    safety_impact: str            # none | low | medium | high
    created_at: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "category": self.category,
            "observation": self.observation,
            "evidence": self.evidence,
            "recommended_change": self.recommended_change,
            "requires_user_approval": self.requires_user_approval,
            "safety_impact": self.safety_impact,
            "created_at": self.created_at,
        }


@dataclass
class LearningReport:
    period_start: str
    period_end: str
    trades_analyzed: int
    rejections_analyzed: int
    overall: dict[str, Any]
    by_strategy: list[StrategyStats]
    by_symbol: dict[str, dict[str, Any]]
    by_exit_reason: dict[str, int]
    by_rejection_reason: dict[str, int]
    insights: list[Insight]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "trades_analyzed": self.trades_analyzed,
            "rejections_analyzed": self.rejections_analyzed,
            "overall": self.overall,
            "by_strategy": [s.to_jsonable() for s in self.by_strategy],
            "by_symbol": self.by_symbol,
            "by_exit_reason": self.by_exit_reason,
            "by_rejection_reason": self.by_rejection_reason,
            "insights": [i.to_jsonable() for i in self.insights],
        }


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


def generate_report(
    trade_journal: Path | None = None,
    rejected: Path | None = None,
    *,
    statistical_floor: int = DEFAULT_STATISTICAL_FLOOR,
    since_iso: str | None = None,
) -> LearningReport:
    trade_journal = trade_journal or TRADE_JOURNAL
    rejected = rejected or REJECTED_TRADES

    trades = list(_parse_trades(trade_journal))
    rejections = list(_parse_rejections(rejected))

    if since_iso:
        trades = [t for t in trades if (t.exit_time or "") >= since_iso]
        rejections = [r for r in rejections if (r.proposed_at or "") >= since_iso]

    overall = _overall_stats(trades)
    by_strategy = _per_strategy(trades)
    by_symbol = _per_symbol(trades)
    by_exit_reason = _count_by(trades, lambda t: t.exit_reason or "unknown")
    by_rejection_reason = _count_by(rejections, lambda r: _normalize_reason(r.rejection_reason))

    insights = _derive_insights(by_strategy, by_rejection_reason, trades, statistical_floor)

    period_start = min((t.entry_time for t in trades), default="") or ""
    period_end = max((t.exit_time for t in trades), default="") or ""

    return LearningReport(
        period_start=period_start,
        period_end=period_end,
        trades_analyzed=len(trades),
        rejections_analyzed=len(rejections),
        overall=overall,
        by_strategy=by_strategy,
        by_symbol=by_symbol,
        by_exit_reason=by_exit_reason,
        by_rejection_reason=by_rejection_reason,
        insights=insights,
    )


def append_insights_to_memory(insights: Iterable[Insight]) -> int:
    """Append each insight to memory/learning-insights.md under "Pending User Approval".

    Returns the count appended. Safe to call repeatedly — duplicates by
    `insight_id` are skipped.
    """
    LEARNING_INSIGHTS.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if LEARNING_INSIGHTS.exists():
        existing = LEARNING_INSIGHTS.read_text(encoding="utf-8")

    appended = 0
    new_blocks: list[str] = []
    for ins in insights:
        if f"## {ins.insight_id}" in existing:
            continue
        new_blocks.append(_render_insight_block(ins))
        appended += 1
    if not new_blocks:
        return 0

    if not existing:
        header = (
            "# Learning Insights\n\n"
            "Recommendations from the Learning & Optimization Agent.\n"
        )
        LEARNING_INSIGHTS.write_text(header, encoding="utf-8")
        existing = header

    with LEARNING_INSIGHTS.open("a", encoding="utf-8") as f:
        for block in new_blocks:
            f.write("\n" + block)
    return appended


# ----------------------------------------------------------------------------
# Parsing — markdown is human-friendly but not free; keep parser tolerant.
# ----------------------------------------------------------------------------

# Anchored-at-line-start "## " followed by ID up to next "## " or EOF.
_BLOCK_RE = re.compile(r"^##\s+([A-Z][A-Z0-9\-]+)\s*$", re.MULTILINE)


def _parse_blocks(path: Path) -> list[tuple[str, dict[str, str]]]:
    """Generic parser: returns list of (block_id, {key: value}) tuples.

    Keys come from "- key: value" lines. Lists "- key: [a, b, c]" are kept
    as the literal string — callers that care about list shape parse them.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    matches = list(_BLOCK_RE.finditer(text))
    blocks: list[tuple[str, dict[str, str]]] = []
    for i, m in enumerate(matches):
        block_id = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        kv: dict[str, str] = {}
        for line in body.splitlines():
            s = line.strip()
            if not s.startswith("- "):
                continue
            try:
                k, v = s[2:].split(":", 1)
            except ValueError:
                continue
            kv[k.strip()] = v.strip()
        blocks.append((block_id, kv))
    return blocks


def _D(s: str | None, default: Decimal = Decimal("0")) -> Decimal:
    if s is None or s in ("", "null", "pending"):
        return default
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return default


def _parse_trades(path: Path) -> Iterable[JournalTrade]:
    for block_id, kv in _parse_blocks(path):
        if not block_id.startswith("TRADE-"):
            continue
        # Skip "pending" entries (Phase 2 placeholders, no realized PnL).
        if kv.get("net_pnl_usdt") in (None, "pending"):
            continue
        yield JournalTrade(
            trade_id=block_id,
            proposal_id=kv.get("proposal_id", ""),
            mode=kv.get("mode", ""),
            symbol=kv.get("symbol", ""),
            side=kv.get("side", ""),
            strategy=kv.get("strategy", ""),
            market_regime=kv.get("market_regime", "unknown"),
            entry_time=kv.get("entry_time", ""),
            exit_time=kv.get("exit_time", ""),
            exit_reason=kv.get("exit_reason", "unknown"),
            net_pnl_usdt=_D(kv.get("net_pnl_usdt")),
            fees_usdt=_D(kv.get("fees_usdt")),
            margin_usdt=_D(kv.get("margin_usdt")),
            max_favorable_pnl_usdt=_D(kv.get("max_favorable_pnl_usdt")),
            max_adverse_pnl_usdt=_D(kv.get("max_adverse_pnl_usdt")),
        )


def _parse_rejections(path: Path) -> Iterable[JournalRejection]:
    for block_id, kv in _parse_blocks(path):
        if not block_id.startswith("REJECTED-"):
            continue
        yield JournalRejection(
            rejection_id=block_id,
            proposal_id=kv.get("proposal_id", ""),
            symbol=kv.get("symbol", ""),
            side=kv.get("side", ""),
            strategy=kv.get("strategy", ""),
            rejected_by=kv.get("rejected_by", ""),
            rejection_reason=kv.get("rejection_reason", ""),
            market_regime=kv.get("market_regime", "unknown"),
            proposed_at=kv.get("proposed_at", ""),
        )


# ----------------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------------


def _overall_stats(trades: list[JournalTrade]) -> dict[str, Any]:
    if not trades:
        return {"n": 0, "wins": 0, "losses": 0, "win_rate": None,
                "net_pnl_usdt": "0", "fees_usdt": "0", "expectancy_per_trade_usdt": "0"}
    wins = sum(1 for t in trades if t.net_pnl_usdt > 0)
    losses = len(trades) - wins
    net = sum((t.net_pnl_usdt for t in trades), Decimal("0"))
    fees = sum((t.fees_usdt for t in trades), Decimal("0"))
    return {
        "n": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(trades), 3),
        "net_pnl_usdt": str(net),
        "fees_usdt": str(fees),
        "expectancy_per_trade_usdt": str(net / Decimal(len(trades))),
    }


def _per_strategy(trades: list[JournalTrade]) -> list[StrategyStats]:
    grouped: dict[str, list[JournalTrade]] = {}
    for t in trades:
        grouped.setdefault(t.strategy or "unknown", []).append(t)
    out: list[StrategyStats] = []
    for strategy, ts in grouped.items():
        wins = sum(1 for t in ts if t.net_pnl_usdt > 0)
        losses = len(ts) - wins
        gross_win = sum((t.net_pnl_usdt for t in ts if t.net_pnl_usdt > 0), Decimal("0"))
        gross_loss = sum((t.net_pnl_usdt for t in ts if t.net_pnl_usdt < 0), Decimal("0"))
        total = sum((t.net_pnl_usdt for t in ts), Decimal("0"))
        avg = total / Decimal(len(ts))
        avg_pct = None
        margin_ts = [t for t in ts if t.margin_usdt > 0]
        if margin_ts:
            avg_pct = float(sum((t.net_pnl_usdt / t.margin_usdt for t in margin_ts), Decimal("0")) / Decimal(len(margin_ts)) * Decimal("100"))
        largest_win = max((t.net_pnl_usdt for t in ts), default=Decimal("0"))
        largest_loss = min((t.net_pnl_usdt for t in ts), default=Decimal("0"))
        avg_mfe = sum((t.max_favorable_pnl_usdt for t in ts), Decimal("0")) / Decimal(len(ts))
        avg_mae = sum((t.max_adverse_pnl_usdt for t in ts), Decimal("0")) / Decimal(len(ts))
        pf: float | None = None
        if gross_loss < 0:
            pf = float(gross_win / abs(gross_loss))
        elif gross_win > 0:
            pf = float("inf")
        out.append(StrategyStats(
            strategy=strategy, n=len(ts), wins=wins, losses=losses,
            win_rate=round(wins / len(ts), 3) if ts else None,
            avg_pnl_usdt=avg, total_pnl_usdt=total,
            avg_pnl_pct_of_margin=avg_pct,
            largest_win_usdt=largest_win, largest_loss_usdt=largest_loss,
            avg_mfe_usdt=avg_mfe, avg_mae_usdt=avg_mae,
            profit_factor=pf, expectancy_per_trade_usdt=avg,
        ))
    out.sort(key=lambda s: s.total_pnl_usdt, reverse=True)
    return out


def _per_symbol(trades: list[JournalTrade]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[JournalTrade]] = {}
    for t in trades:
        grouped.setdefault(t.symbol or "unknown", []).append(t)
    out: dict[str, dict[str, Any]] = {}
    for sym, ts in grouped.items():
        wins = sum(1 for t in ts if t.net_pnl_usdt > 0)
        net = sum((t.net_pnl_usdt for t in ts), Decimal("0"))
        out[sym] = {
            "n": len(ts), "wins": wins,
            "win_rate": round(wins / len(ts), 3),
            "net_pnl_usdt": str(net),
        }
    return dict(sorted(out.items(), key=lambda kv: Decimal(kv[1]["net_pnl_usdt"]), reverse=True))


def _count_by(items: Iterable, key) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        k = key(it) or "unknown"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


# ----------------------------------------------------------------------------
# Insight derivation — strict, conservative rules.
# ----------------------------------------------------------------------------


def _derive_insights(
    by_strategy: list[StrategyStats],
    by_rejection_reason: dict[str, int],
    trades: list[JournalTrade],
    statistical_floor: int,
) -> list[Insight]:
    insights: list[Insight] = []
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Per-strategy insights — only above floor.
    for s in by_strategy:
        if s.n < statistical_floor:
            insights.append(_observation_only(s, now, statistical_floor))
            continue
        wr = s.win_rate or 0.0
        if wr >= 0.55 and s.expectancy_per_trade_usdt > 0:
            insights.append(Insight(
                insight_id=_insight_id("strategy-good", s.strategy, now),
                category="strategy",
                observation=f"{s.strategy} shows {wr:.0%} win rate over {s.n} trades, "
                            f"net {s.total_pnl_usdt} USDT.",
                evidence={
                    "sample_size": s.n,
                    "win_rate": wr,
                    "avg_pnl": str(s.avg_pnl_usdt),
                    "regime": "all",
                    "profit_factor": s.profit_factor,
                },
                recommended_change=(
                    f"Consider raising the screener priority for setups matching "
                    f"{s.strategy}. DO NOT auto-raise leverage or max-loss budget."
                ),
                requires_user_approval=True,
                safety_impact="low",
                created_at=now,
            ))
        elif wr <= 0.35 or (s.expectancy_per_trade_usdt <= 0 and s.n >= statistical_floor * 1.5):
            insights.append(Insight(
                insight_id=_insight_id("strategy-bad", s.strategy, now),
                category="strategy",
                observation=f"{s.strategy} underperforms: {wr:.0%} win rate over {s.n} trades, "
                            f"net {s.total_pnl_usdt} USDT.",
                evidence={
                    "sample_size": s.n,
                    "win_rate": wr,
                    "avg_pnl": str(s.avg_pnl_usdt),
                    "regime": "all",
                    "profit_factor": s.profit_factor,
                },
                recommended_change=(
                    f"Suggest raising MIN_CONFIDENCE for {s.strategy} or pausing it "
                    f"until conditions change. Requires user approval."
                ),
                requires_user_approval=True,
                safety_impact="none",
                created_at=now,
            ))

    # Rejection-pattern insights.
    if by_rejection_reason:
        # Most common rejection — useful diagnostic for the screener config.
        top_reason, top_count = next(iter(by_rejection_reason.items()))
        if top_count >= statistical_floor:
            insights.append(Insight(
                insight_id=_insight_id("rejection-pattern", top_reason, now),
                category="screening",
                observation=f"Most common rejection: {top_reason} ({top_count} times). "
                            f"Likely the screener is finding too many setups that hit "
                            f"this risk gate.",
                evidence={
                    "sample_size": sum(by_rejection_reason.values()),
                    "win_rate": None,
                    "avg_pnl": None,
                    "regime": "all",
                    "top_reason_count": top_count,
                },
                recommended_change=(
                    "Tighten the screener filter that produces these proposals upstream "
                    "rather than relying on the Risk Manager to gate them. User decides."
                ),
                requires_user_approval=True,
                safety_impact="none",
                created_at=now,
            ))

    return insights


def _observation_only(s: StrategyStats, now: str, floor: int) -> Insight:
    return Insight(
        insight_id=_insight_id("observation", s.strategy, now),
        category="strategy",
        observation=f"{s.strategy} sample size {s.n} below floor {floor}; not yet actionable. "
                    f"Provisional win rate {s.win_rate}, net {s.total_pnl_usdt} USDT.",
        evidence={
            "sample_size": s.n,
            "win_rate": s.win_rate,
            "avg_pnl": str(s.avg_pnl_usdt),
            "regime": "all",
        },
        recommended_change="No change recommended — gather more data.",
        requires_user_approval=False,
        safety_impact="none",
        created_at=now,
    )


def _insight_id(kind: str, key: str, now: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", key)[:40]
    return f"INSIGHT-{now[:10].replace('-', '')}-{kind}-{safe}".upper()


def _normalize_reason(reason: str) -> str:
    """Collapse risk-reason strings into reusable buckets."""
    reason = reason.lower()
    if "min_notional" in reason or "min notional" in reason:
        return "min_notional incompatible with budget"
    if "liquidation" in reason:
        return "liquidation distance too close"
    if "fee" in reason and "consume" in reason:
        return "fees consume profit"
    if "spread" in reason:
        return "spread too wide"
    if "thin" in reason or "liquidity" in reason:
        return "liquidity too thin"
    if "no strategy" in reason or "min_confidence" in reason:
        return "no high-confidence setup"
    return reason[:80]


def _render_insight_block(ins: Insight) -> str:
    ev = ins.evidence
    lines = [
        f"## {ins.insight_id}",
        "",
        f"- insight_id: {ins.insight_id}",
        f"- category: {ins.category}",
        f"- observation: {ins.observation}",
        f"- evidence:",
        f"    sample_size: {ev.get('sample_size')}",
        f"    win_rate: {ev.get('win_rate')}",
        f"    avg_pnl: {ev.get('avg_pnl')}",
        f"    regime: {ev.get('regime')}",
        f"- recommended_change: {ins.recommended_change}",
        f"- requires_user_approval: {str(ins.requires_user_approval).lower()}",
        f"- safety_impact: {ins.safety_impact}",
        f"- created_at: {ins.created_at}",
        f"- status: pending",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "JournalTrade",
    "JournalRejection",
    "StrategyStats",
    "Insight",
    "LearningReport",
    "DEFAULT_STATISTICAL_FLOOR",
    "generate_report",
    "append_insights_to_memory",
]
