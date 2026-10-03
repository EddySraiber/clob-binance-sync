from decimal import Decimal

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orderbook import OrderBook


def make_book():
    book = OrderBook("BNBBTC")
    book.load_snapshot(157, [["4.00000000", "431.00000000"]], [["4.00000020", "12.00000000"]])
    return book


def test_load_snapshot():
    book = make_book()
    assert book.last_update_id == 157
    assert book.best_bid() == (Decimal("4.00000000"), Decimal("431.00000000"))
    assert book.best_ask() == (Decimal("4.00000020"), Decimal("12.00000000"))


def test_apply_update_upserts_and_removes():
    book = make_book()
    book.apply_update(
        bids=[["0.00240000", "10.00000000"], ["4.00000000", "0.00000000"]],
        asks=[["0.00260000", "100.00000000"]],
        first_update_id=158,
        final_update_id=160,
    )
    assert book.last_update_id == 160
    assert Decimal("4.00000000") not in book.bids
    assert book.bids[Decimal("0.00240000")] == Decimal("10.00000000")
    assert book.asks[Decimal("4.00000020")] == Decimal("12.00000000")
    assert book.asks[Decimal("0.00260000")] == Decimal("100.00000000")


def test_best_bid_ask_ordering():
    book = OrderBook("TEST")
    book.load_snapshot(1, [["10", "1"], ["12", "1"], ["9", "1"]], [["15", "1"], ["13", "1"], ["14", "1"]])
    assert book.best_bid()[0] == Decimal("12")
    assert book.best_ask()[0] == Decimal("13")


def test_zero_quantity_on_load_is_never_inserted():
    book = OrderBook("TEST")
    book.load_snapshot(1, [["10", "0"]], [])
    assert Decimal("10") not in book.bids


def test_depth_returns_best_first():
    book = OrderBook("TEST")
    book.load_snapshot(1, [["10", "1"], ["12", "1"], ["9", "1"]], [["15", "1"], ["13", "1"], ["14", "1"]])
    bids, asks = book.depth(2)
    assert [p for p, _ in bids] == [Decimal("12"), Decimal("10")]
    assert [p for p, _ in asks] == [Decimal("13"), Decimal("14")]
