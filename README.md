# Binance Local Order Book (CLOB)

Maintains a live, locally-synced replica of a Binance trading pair's
order book via the diff-depth WebSocket stream, following Binance's
documented procedure for a correct local order book (see
`sync_manager.py` for the sync algorithm and `DESIGN.md` for the full
design write-up).

## Quickstart (Docker, recommended)

No local Python setup needed. The image build also runs the full test
suite — a successful build is already a tested build.

```bash
docker build -t clob .
docker run --rm clob                          # demo: book before/after an update (no network)
docker run --rm clob pytest tests/ -v         # tests
docker run --rm clob python main.py btcusdt   # live against real Binance (needs network)
```

Or via `run.sh`: `./run.sh docker`, `./run.sh ddemo`, `./run.sh dtest`, `./run.sh dlive`.

## Local (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
pytest tests/ -v
python demo.py
python main.py btcusdt
```

Or via `run.sh`: `./run.sh setup`, `./run.sh test`, `./run.sh demo`, `./run.sh live`.

See the comment block at the top of `run.sh` for what each command does.

## Project layout

| File | Purpose |
|---|---|
| `orderbook.py` | Core order book state (bid/ask price levels, red-black trees) |
| `sync_manager.py` | Binance sync algorithm + state machine (SYNCING → BUFFERING → LIVE) |
| `metrics.py` | In-memory monitoring counters (snapshots, updates, gaps, staleness) |
| `demo.py` | Prints the book before/after an update, using a fixed example |
| `main.py` | Live entrypoint, connects to real Binance feeds |
| `Dockerfile` | Container build (runs tests at build time) |
| `run.sh` | Shortcuts for setup/test/demo/live, venv and Docker |
| `tests/` | Unit tests for the order book and the sync/gap-handling logic |

See `DESIGN.md` for architecture, trade-offs, scalability, persistence &
recovery, and the testing/monitoring plan.
