import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sync_manager import SyncManager, SyncState

SNAPSHOT = {
    "lastUpdateId": 157,
    "bids": [["4.00000000", "431.00000000"]],
    "asks": [["4.00000020", "12.00000000"]],
}

EVENT = {
    "e": "depthUpdate", "E": 1, "s": "BNBBTC",
    "U": 158, "u": 160,
    "b": [["0.00240000", "10.00000000"], ["4.00000000", "0.00000000"]],
    "a": [["0.00260000", "100.00000000"]],
}


def make_manager():
    return SyncManager("bnbbtc")


def test_bootstrap_applies_overlapping_buffered_event():
    manager = make_manager()
    manager._buffer.append(EVENT)
    with patch.object(manager, "fetch_snapshot", return_value=SNAPSHOT):
        manager.bootstrap()
    assert manager.state == SyncState.LIVE
    assert manager.book.last_update_id == 160


def test_bootstrap_discards_stale_events():
    manager = make_manager()
    stale_event = {**EVENT, "U": 100, "u": 150}  # u <= lastUpdateId(157) -> stale
    manager._buffer.append(stale_event)
    with patch.object(manager, "fetch_snapshot", return_value=SNAPSHOT):
        manager.bootstrap()
    assert manager.state == SyncState.BUFFERING
    assert manager.book.last_update_id == 157


def test_gap_detection_triggers_resync():
    manager = make_manager()
    manager._buffer.append(EVENT)
    with patch.object(manager, "fetch_snapshot", return_value=SNAPSHOT):
        manager.bootstrap()
    assert manager.state == SyncState.LIVE

    bad_event = {**EVENT, "U": 999, "u": 1000}
    result = manager.handle_event(bad_event)
    assert result is False
    assert manager.metrics.gaps_detected == 1
    assert manager.state == SyncState.SYNCING


def test_contiguous_event_applied_live():
    manager = make_manager()
    manager._buffer.append(EVENT)
    with patch.object(manager, "fetch_snapshot", return_value=SNAPSHOT):
        manager.bootstrap()
    next_event = {**EVENT, "U": 161, "u": 162, "b": [], "a": [["1.0", "5.0"]]}
    result = manager.handle_event(next_event)
    assert result is True
    assert manager.book.last_update_id == 162
