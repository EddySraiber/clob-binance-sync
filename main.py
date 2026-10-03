"""
Live entrypoint: connects to Binance and maintains a local order book
for the given symbol (default btcusdt). Requires network access to
api.binance.com / stream.binance.com.

Run: python main.py [symbol]
"""
import asyncio
import logging
import sys

from sync_manager import SyncManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "btcusdt"
    manager = SyncManager(symbol)
    logging.info("Starting sync for %s", symbol)
    await manager.run()


if __name__ == "__main__":
    asyncio.run(main())
