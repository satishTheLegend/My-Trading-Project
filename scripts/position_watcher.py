"""Position watcher — alias for the watcher module.

The actual implementation lives in `scripts/watcher.py` (single-tick
monitoring) and `scripts/run_watch_positions.py` (CLI loop). This file is
the literal name from the upgrade-prompt folder layout, re-exporting the
public surface so both names work::

    from scripts.position_watcher import watch_open_positions, WatcherTickReport
    # equivalent to:
    from scripts.watcher import watch_open_positions, WatcherTickReport
"""

from __future__ import annotations

from .watcher import (
    WatcherTickReport,
    watch_open_positions,
)


__all__ = ["WatcherTickReport", "watch_open_positions"]
