"""binance_position_sync: manual position detection + writer."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import scripts.binance_position_sync as bps
from scripts.account import Account, ExchangePosition
from scripts.binance_position_sync import sync_binance
from scripts.positions_store import Position, PositionsStore, make_position_id


class _FakeAccount:
    def __init__(self, balances, positions):
        self._balances = balances
        self._positions = positions

    def get_balances(self):
        return self._balances

    def get_open_positions(self, symbol: str | None = None):
        return self._positions


class _Bal:
    def __init__(self, asset, wallet, avail, un_pnl=Decimal("0")):
        self.asset = asset
        self.wallet_balance = wallet
        self.available_balance = avail
        self.cross_un_pnl = un_pnl


def _exch(symbol: str, amt: str = "100") -> ExchangePosition:
    return ExchangePosition(
        symbol=symbol, position_amt=Decimal(amt),
        entry_price=Decimal("0.07654"), mark_price=Decimal("0.07700"),
        un_realized_profit=Decimal("0.046"),
        leverage=3, margin_type="isolated",
        isolated_wallet=Decimal("2"),
        liquidation_price=Decimal("0.05100"),
        update_time_ms=0,
    )


def test_no_manual_when_exchange_matches_local(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(bps, "SYNCED_BINANCE", tmp_path / "synced.json")
    monkeypatch.setattr(bps, "MANUAL_POSITIONS", tmp_path / "manual.json")
    store_path = tmp_path / "open.json"
    store = PositionsStore(store_path)
    # Local mirror of one exchange position.
    store.upsert(Position(
        position_id=make_position_id("DOGEUSDT"),
        symbol="DOGEUSDT", side="LONG", status="open",
        entry_price=Decimal("0.07654"),
        quantity=Decimal("100"), initial_quantity=Decimal("100"),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2"), notional_usdt=Decimal("7.654"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        unrealized_pnl=Decimal("0"), realized_pnl=Decimal("0"),
        max_favorable_pnl=Decimal("0"), max_adverse_pnl=Decimal("0"),
        liquidation_price=Decimal("0.05100"),
        fees_paid_usdt=Decimal("0"), funding_paid_usdt=Decimal("0"),
        proposal_id="PROP-1", strategy="pullback_long",
        market_regime="bullish",
        opened_at="2026-05-10T12:00:00Z", updated_at="2026-05-10T12:00:00Z",
        closed_at=None, exit_price=None, exit_reason=None, mode="LIVE",
    ))
    account = _FakeAccount(
        balances=[_Bal("USDT", Decimal("10"), Decimal("8"))],
        positions=[_exch("DOGEUSDT")],
    )
    report = sync_binance(account=account, store=store, notify_telegram=False)
    assert report.sync_status == "success"
    assert report.manual_positions_detected == []
    assert report.new_trades_allowed is True


def test_manual_position_detected_when_local_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(bps, "SYNCED_BINANCE", tmp_path / "synced.json")
    monkeypatch.setattr(bps, "MANUAL_POSITIONS", tmp_path / "manual.json")
    store = PositionsStore(tmp_path / "open.json")     # empty
    account = _FakeAccount(
        balances=[_Bal("USDT", Decimal("10"), Decimal("10"))],
        positions=[_exch("DOGEUSDT")],
    )
    report = sync_binance(account=account, store=store, notify_telegram=False)
    assert report.sync_status == "warning"
    assert report.new_trades_allowed is False
    assert len(report.manual_positions_detected) == 1
    m = report.manual_positions_detected[0]
    assert m["symbol"] == "DOGEUSDT"
    assert m["agency_managed"] is False


def test_manual_first_seen_persists_across_runs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(bps, "SYNCED_BINANCE", tmp_path / "synced.json")
    monkeypatch.setattr(bps, "MANUAL_POSITIONS", tmp_path / "manual.json")
    store = PositionsStore(tmp_path / "open.json")
    account = _FakeAccount(
        balances=[_Bal("USDT", Decimal("10"), Decimal("10"))],
        positions=[_exch("DOGEUSDT")],
    )
    sync_binance(account=account, store=store, notify_telegram=False)
    first = json.loads((tmp_path / "manual.json").read_text())
    first_seen = first["manual_positions"][0]["first_seen_at"]
    # Run again with the same exchange state.
    sync_binance(account=account, store=store, notify_telegram=False)
    second = json.loads((tmp_path / "manual.json").read_text())
    assert second["manual_positions"][0]["first_seen_at"] == first_seen


def test_synced_positions_file_written(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(bps, "SYNCED_BINANCE", tmp_path / "synced.json")
    monkeypatch.setattr(bps, "MANUAL_POSITIONS", tmp_path / "manual.json")
    store = PositionsStore(tmp_path / "open.json")
    account = _FakeAccount(
        balances=[_Bal("USDT", Decimal("12.34"), Decimal("9.99"))],
        positions=[_exch("DOGEUSDT"), _exch("SHIBUSDT", "-50")],
    )
    sync_binance(account=account, store=store, notify_telegram=False)
    data = json.loads((tmp_path / "synced.json").read_text())
    assert data["wallet_balance_usdt"] == "12.34"
    assert data["available_margin_usdt"] == "9.99"
    assert len(data["positions"]) == 2
