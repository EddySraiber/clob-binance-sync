"""
Prints the order book before and after applying one diff-depth update,
using a small fixed example so the output is independently verifiable
without a live Binance connection.

Run: python demo.py
"""
import json

from orderbook import OrderBook

INITIAL_SNAPSHOT = {
    "lastUpdateId": 157,
    "bids": [["4.00000000", "431.00000000"]],
    "asks": [["4.00000020", "12.00000000"]],
}

UPDATE_EVENT = {
    "e": "depthUpdate",
    "E": 1672515782136,
    "s": "BNBBTC",
    "U": 158,
    "u": 160,
    "b": [
        ["0.00240000", "10.00000000"],
        ["4.00000000", "0.00000000"],
    ],
    "a": [
        ["0.00260000", "100.00000000"],
    ],
}


def main() -> None:
    book = OrderBook("BNBBTC")
    book.load_snapshot(INITIAL_SNAPSHOT["lastUpdateId"], INITIAL_SNAPSHOT["bids"], INITIAL_SNAPSHOT["asks"])

    print("=== BEFORE UPDATE ===")
    print(json.dumps(book.snapshot_dict(), indent=2))

    book.apply_update(UPDATE_EVENT["b"], UPDATE_EVENT["a"], UPDATE_EVENT["U"], UPDATE_EVENT["u"])

    print("\n=== APPLIED EVENT ===")
    print(json.dumps(UPDATE_EVENT, indent=2))

    print("\n=== AFTER UPDATE ===")
    print(json.dumps(book.snapshot_dict(), indent=2))


if __name__ == "__main__":
    main()
