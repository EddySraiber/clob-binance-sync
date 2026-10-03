"""
Core order book state.

Price levels are kept in bintrees.RBTree — an actual red-black tree
(https://pypi.org/project/bintrees/), giving O(log n) insert/update/
delete, and in-order traversal for best bid/ask.

Bids and asks are each their own tree, always ascending internally by
price; best bid = max key, best ask = min key.
"""
from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from bintrees import RBTree

PriceQty = Tuple[str, str]


class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.last_update_id: int = 0
        self.bids: "RBTree[Decimal, Decimal]" = RBTree()
        self.asks: "RBTree[Decimal, Decimal]" = RBTree()

    @staticmethod
    def _upsert(side: "RBTree[Decimal, Decimal]", price_str: str, qty_str: str) -> None:
        price = Decimal(price_str)
        qty = Decimal(qty_str)
        if qty == 0:
            side.pop(price, None)
        else:
            side[price] = qty

    def load_snapshot(self, last_update_id: int, bids: Iterable[PriceQty], asks: Iterable[PriceQty]) -> None:
        """Replace current state with a REST snapshot."""
        self.last_update_id = last_update_id
        self.bids.clear()
        self.asks.clear()
        for price, qty in bids:
            self._upsert(self.bids, price, qty)
        for price, qty in asks:
            self._upsert(self.asks, price, qty)

    def apply_update(
        self,
        bids: Iterable[PriceQty],
        asks: Iterable[PriceQty],
        first_update_id: int,
        final_update_id: int,
    ) -> None:
        """Apply one diff-depth event. Caller is responsible for having
        already validated event ordering/continuity (see SyncManager)."""
        for price, qty in bids:
            self._upsert(self.bids, price, qty)
        for price, qty in asks:
            self._upsert(self.asks, price, qty)
        self.last_update_id = final_update_id

    def best_bid(self) -> Optional[Tuple[Decimal, Decimal]]:
        if not self.bids:
            return None
        return self.bids.max_item()

    def best_ask(self) -> Optional[Tuple[Decimal, Decimal]]:
        if not self.asks:
            return None
        return self.asks.min_item()

    def depth(self, n: int = 10) -> Tuple[List[Tuple[Decimal, Decimal]], List[Tuple[Decimal, Decimal]]]:
        """Top-n levels on each side, best price first."""
        bid_items = list(self.bids.items())[-n:][::-1]
        ask_items = list(self.asks.items())[:n]
        return bid_items, ask_items

    def snapshot_dict(self) -> dict:
        """Render current state in the same shape as Binance's REST snapshot,
        for printing/logging/comparison."""
        return {
            "lastUpdateId": self.last_update_id,
            "bids": [[str(p), str(q)] for p, q in reversed(list(self.bids.items()))],
            "asks": [[str(p), str(q)] for p, q in self.asks.items()],
        }
