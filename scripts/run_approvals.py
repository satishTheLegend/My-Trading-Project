"""CLI: manage the SEMI_AUTO_LIVE approval queue.

The execution router writes proposals that need human approval into
``data/pending-approvals.json``. This CLI is how you say yes / no.

Usage::

    # See what's waiting:
    python -m scripts.run_approvals --list

    # Approve one (worker fires next live cycle):
    python -m scripts.run_approvals --approve APRV-20260510-143000-DOGEUSDT-001

    # Reject one with a note:
    python -m scripts.run_approvals --reject APRV-20260510-143000-DOGEUSDT-001 \
                                    --reason "BTC just dumped 2% — abort"

    # Interactive: walk every pending entry, prompt y/N inline:
    python -m scripts.run_approvals --inline

    # Sweep stale entries (past their deadline → expired):
    python -m scripts.run_approvals --expire

    # Drop terminal entries (executed/rejected/expired/cancelled), keep latest 50:
    python -m scripts.run_approvals --prune
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal

from .pending_approvals import PendingApprovalsStore


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Manage SEMI_AUTO_LIVE approval queue")
    p.add_argument("--list", action="store_true",
                   help="show all pending approvals")
    p.add_argument("--all", action="store_true",
                   help="with --list, show every entry (incl. terminal)")
    p.add_argument("--approve", metavar="APPROVAL_ID",
                   help="mark a pending approval as approved")
    p.add_argument("--reject", metavar="APPROVAL_ID",
                   help="mark a pending approval as rejected")
    p.add_argument("--cancel", metavar="APPROVAL_ID",
                   help="cancel a pending approval (no live order)")
    p.add_argument("--reason", default="", help="reason recorded with --reject/--cancel")
    p.add_argument("--inline", action="store_true",
                   help="interactive: prompt y/n for each pending entry")
    p.add_argument("--expire", action="store_true",
                   help="sweep pending entries past their deadline → expired")
    p.add_argument("--prune", action="store_true",
                   help="drop terminal entries (keeps latest 50)")
    args = p.parse_args(argv)

    store = PendingApprovalsStore()

    if args.expire:
        n = store.expire_overdue()
        print(json.dumps({"expired_count": n}, indent=2))
        return 0

    if args.prune:
        n = store.prune_terminal(keep_last_n=50)
        print(json.dumps({"removed_terminal_count": n}, indent=2))
        return 0

    if args.list:
        if args.all:
            entries = store.load_all()
        else:
            entries = store.load_pending()
        print(json.dumps({
            "count": len(entries),
            "approvals": [a.to_jsonable() for a in entries],
        }, indent=2, default=str))
        return 0

    if args.approve:
        a = store.transition(args.approve, to="approved",
                             notes=args.reason or "approved via CLI")
        if a is None:
            print(json.dumps({"error": f"no approval with id {args.approve}"}))
            return 1
        print(json.dumps({"transitioned": a.to_jsonable()}, indent=2, default=str))
        return 0

    if args.reject:
        if not args.reason:
            print(json.dumps({"error": "--reject requires --reason"}))
            return 2
        a = store.transition(args.reject, to="rejected", notes=args.reason)
        if a is None:
            print(json.dumps({"error": f"no approval with id {args.reject}"}))
            return 1
        print(json.dumps({"transitioned": a.to_jsonable()}, indent=2, default=str))
        return 0

    if args.cancel:
        a = store.transition(args.cancel, to="cancelled",
                             notes=args.reason or "cancelled via CLI")
        if a is None:
            print(json.dumps({"error": f"no approval with id {args.cancel}"}))
            return 1
        print(json.dumps({"transitioned": a.to_jsonable()}, indent=2, default=str))
        return 0

    if args.inline:
        return _inline(store)

    p.print_help()
    return 0


def _inline(store: PendingApprovalsStore) -> int:
    pending = store.load_pending()
    if not pending:
        print(json.dumps({"message": "no pending approvals"}, indent=2))
        return 0

    decisions: list[dict[str, object]] = []
    for a in pending:
        # Skip ones already past deadline.
        if a.is_expired():
            store.transition(a.approval_id, to="expired",
                             notes="deadline passed before user reached this prompt")
            decisions.append({"approval_id": a.approval_id, "decision": "expired"})
            continue
        print()
        print(_format_for_prompt(a))
        try:
            ans = input("Approve this trade? [y/N/r=reject/c=cancel] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\naborted — remaining entries left as pending")
            break
        if ans in ("y", "yes"):
            store.transition(a.approval_id, to="approved", notes="interactive yes")
            decisions.append({"approval_id": a.approval_id, "decision": "approved"})
        elif ans in ("r", "reject"):
            try:
                why = input("reason: ").strip()
            except (EOFError, KeyboardInterrupt):
                why = "rejected"
            store.transition(a.approval_id, to="rejected", notes=why or "rejected")
            decisions.append({"approval_id": a.approval_id, "decision": "rejected"})
        elif ans in ("c", "cancel"):
            store.transition(a.approval_id, to="cancelled", notes="user cancelled")
            decisions.append({"approval_id": a.approval_id, "decision": "cancelled"})
        else:
            decisions.append({"approval_id": a.approval_id, "decision": "no_change_left_pending"})

    print(json.dumps({"decisions": decisions}, indent=2, default=str))
    return 0


def _format_for_prompt(a) -> str:
    return (
        f"  approval_id: {a.approval_id}\n"
        f"  proposal_id: {a.proposal_id}\n"
        f"  symbol:      {a.symbol}   side: {a.side}   strategy: {a.strategy}\n"
        f"  entry:       {a.entry_price}    stop: {a.stop_loss}    "
        f"TPs: {[str(t) for t in a.take_profit_targets]}\n"
        f"  qty:         {a.quantity}    leverage: {a.leverage}x   "
        f"margin: {a.margin_usdt} USDT   notional: {a.notional_usdt} USDT\n"
        f"  liquidation: {a.liquidation_price}    est. fees: {a.estimated_fees_usdt}\n"
        f"  reason:      {a.requires_approval_reason}\n"
        f"  rules:       {a.triggered_rules}\n"
        f"  created:     {a.created_at}    deadline: {a.deadline_at}"
    )


if __name__ == "__main__":
    sys.exit(main())
