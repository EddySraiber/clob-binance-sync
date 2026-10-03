# Design — Binance Local Order Book (CLOB)

## Overview

This project maintains a local, real-time replica of a Binance trading
pair's order book — a Central Limit Order Book (CLOB) — kept in sync via
Binance's WebSocket diff-depth stream, with correct handling of stream
gaps/desyncs. It does not include order matching or execution; it only
maintains an accurate live mirror of Binance's book.

---

## 1. Architecture & Design

### 1a. Data structure

Each side of the book (bids, asks) is a **red-black tree**, using
`bintrees.RBTree`. Keys are price levels, values are quantities. This
gives O(log n) insert, update, delete, and ordered traversal, so best
bid/ask and top-N depth are always cheap to read. Bids and asks are two
separate trees; best bid = max key of the bid tree, best ask = min key
of the ask tree.

### 1b. Key design decisions & trade-offs

- **Library RB tree vs. hand-rolled**: using `bintrees` instead of
  writing a red-black tree from scratch. Trade-off: faster to build
  correctly and battle-tested, at the cost of not demonstrating a
  from-scratch balancing implementation.
- **In-memory only, no persistence**: state lives in process memory
  only. Trade-off: simpler and fast, but a restart requires a full
  re-sync from Binance (acceptable since Binance is always the source of
  truth — see "Persistence & Recovery" below).
- **Single-threaded event application per symbol**: one event loop
  applies updates to a given symbol's trees, avoiding concurrency bugs
  on the tree at the cost of parallel throughput within a single symbol.
- **Decimal, not float, for prices/quantities**: avoids floating-point
  rounding errors on financial data, at a small performance cost.

### 1c. Out of scope / limitations & future improvements

**Out of scope:**
- Order matching/execution engine (mirrors the book only, doesn't match trades).
- Authentication/authorization.
- Multiple exchanges (Binance only).
- Historical replay/backtesting.
- Persistent database of book history.

**Future improvements:**
- Periodic snapshot persistence to reduce resync latency after a restart.
- Multi-exchange adapters (see "Scalability" below).
- A query API (REST/gRPC) exposing the live book to other services.

### 1d. Scale considerations

See "Scalability" below.

---

## 2. The Local Order Book Algorithm

Implemented in `sync_manager.py`, following Binance's documented
procedure for maintaining a correct local order book:

1. Open the diff-depth WebSocket stream and **buffer every event**
   (don't apply yet).
2. Fetch a REST depth snapshot (`lastUpdateId`).
3. Discard any buffered event where `u <= lastUpdateId` (older than snapshot).
4. Find the first remaining buffered event where
   `U <= lastUpdateId + 1 <= u`. Apply it, then apply every subsequent
   buffered event in order.
5. For every new event after that, verify `U == previous_event's_u + 1`.
   If this fails, the stream has desynced: discard the book and restart
   from step 1.
6. **Applying an event**: for each `[price, quantity]` pair in `b` (bids)
   or `a` (asks) — if `quantity == "0"`, remove that price level;
   otherwise upsert it.

This is modeled as an explicit state machine in `SyncManager`:
`SYNCING → BUFFERING → LIVE`, with any detected gap sending it back to
`SYNCING` to trigger a fresh snapshot fetch.

A worked example of this (snapshot → event → resulting book) is in
`demo.py` and in `tests/test_orderbook.py`.

---

## 3. Implementation

### 3a. Bootstrapping from a snapshot

`SyncManager.fetch_snapshot()` calls Binance's REST
`GET /api/v3/depth` endpoint for the symbol, returning `lastUpdateId`,
`bids`, `asks`. `OrderBook.load_snapshot()` loads this into the two
red-black trees. `main.py` opens the WebSocket stream *before* calling
this, per Binance's docs, so no events are missed in between.

### 3b. Applying stream updates

`SyncManager.handle_event()` / `_apply_event()` apply each diff-depth
event's `b`/`a` arrays to the trees via `OrderBook.apply_update()`,
exactly as in step 6 above.

### 3c. Handling gaps

`SyncManager.handle_event()` checks `event["U"] == last_applied_u + 1`
on every live event; on mismatch it logs a warning, increments a gap
metric, and calls `resync()` (drops state, returns to `SYNCING`) so the
caller re-bootstraps from a fresh snapshot. Covered by
`tests/test_sync_manager.py::test_gap_detection_triggers_resync`.

---

## 4. Testing & Monitoring Plan

### Testing (see `tests/`)

- **Unit tests**: tree insert/update/delete-on-zero-quantity, best
  bid/ask retrieval, snapshot application (`test_orderbook.py`).
- **Gap/resync tests**: bootstrap from a buffered overlapping event,
  discarding stale buffered events, detecting a non-contiguous `U`,
  applying a correctly contiguous event (`test_sync_manager.py`).
- **Integration test** (manual, needs network): connect to Binance's
  live feed for a real symbol, periodically re-fetch an independent REST
  snapshot, and assert it matches the locally maintained book — validates
  timely, correct execution.
- **Fault injection** (manual/future): simulate dropped events,
  out-of-order events, and WebSocket disconnects; assert correct resync
  rather than silent corruption — validates persistency.

### Monitoring (`metrics.py`)

Tracked: snapshots loaded, updates applied, gaps detected, staleness
(seconds since last applied event). In production these would be
exported to Prometheus/StatsD on an interval instead of read in-process.
Anomaly detection: alert if resync frequency exceeds a threshold, or if
staleness exceeds a few seconds (feed has silently stalled).

---

## 5. Core Principles & Assumptions

- The book always reflects Binance's state exactly — the system never
  originates its own prices/quantities, only mirrors them.
- **Assumption**: Binance's `U`/`u` update-ID sequence is strictly
  contiguous and non-decreasing per symbol when no events are dropped —
  this is the basis for the gap-detection check in 3c.
- **Assumption**: a single REST snapshot plus the diff-depth stream is
  sufficient to reconstruct a consistent book (per Binance's own
  documented guarantee) — no additional reconciliation source is used.

## 6. Efficiency

- **Latency**: each event is applied as soon as it's read off the
  WebSocket, synchronously, with no batching — update-to-apply latency
  is bounded by tree operation cost (O(log n)) plus event-loop scheduling.
- **Complexity**: insert/update/remove of a price level are all
  O(log n) via the red-black tree; retrieving best bid/ask is O(log n)
  (tree min/max); top-N depth is O(N + log n).

## 7. Scalability

- **Multiple trading pairs**: one `SyncManager` + `OrderBook` instance
  per symbol — naturally shardable since symbols don't interact with
  each other. N symbols can run on N async tasks in one process, or be
  distributed across multiple processes/machines.
- **Additional data feeds**: the REST-fetch and WebSocket-connect logic
  are isolated inside `SyncManager`; a new exchange would mean writing a
  new adapter with the same interface (`fetch_snapshot`/`handle_event`),
  not touching the order book or tree logic.

## 8. Persistence & Recovery

- If an event is missed (gap detected), the system discards its state
  and re-syncs from a fresh REST snapshot — Binance is always the source
  of truth, so there's no need to reconstruct missed state manually.
- **Trade-off**: keeping this lightweight (no persistence, always
  re-sync on gap/restart) is simpler and always correct, but causes
  brief staleness windows during resync. Adding periodic snapshotting to
  disk would reduce resync latency at the cost of complexity and
  potential staleness if the persisted copy itself is stale.

## 9. Future Scalability — Open Design Gaps

9.1 Partial / progressive depth loading

Right now bootstrap loads the entire REST snapshot into the tree before going LIVE. For wide books this is wasted work: trading activity concentrates near the touch, and deep levels are rarely queried. An alternative: bootstrap only the top N levels needed to answer best_bid/best_ask/shallow depth() calls immediately, and lazily materialize deeper levels from the snapshot in the background (or on first request for that depth). The risk is exactly what you flagged — a lazily-loaded deep level is "phantom": it reflects a point-in-time snapshot and may already be gone by the time it's materialized. This only matters if something actually reads that level, so the design should make the trade-off explicit rather than silent (see 9.4).

9.2 Snapshot depth is capped — it's never "the whole book"

Worth stating as fact, not assumption: Binance's REST snapshot endpoint doesn't return the full book at all — limit is capped to one of {5, 10, 20, 50, 100, 500, 1000, 5000}, default 100, max 5000, and request weight scales with the limit chosen (e.g. limit=5000 costs far more than limit=100). So "full depth" in this system already means "the top 5000 levels," not literally everything in Binance's matching engine. This should be called out as an explicit assumption/limitation, and the chosen limit should be a config knob traded off against REST weight budget and how deep the consumer actually needs to see.

9.3 Parallelization strategy

Per-symbol state must stay single-writer (Section 1b), but parallelism is still available at other levels: (a) across symbols — each SyncManager is independent, so N symbols can run on N tasks/processes with no shared state; (b) within the pipeline — WebSocket read, JSON parsing, and tree application can be split into stages connected by a bounded queue, so a slow tree-apply doesn't block the socket read (this also sets up 9.5); (c) read parallelism — multiple readers can safely query best_bid/depth() concurrently if the tree is wrapped with a reader-writer lock, since reads vastly outnumber writes in most consumption patterns.

9.4 Tiered freshness / staleness budget by depth

Formalize what 9.1 implies: define an explicit SLA where top-of-book (say, top 10-20 levels) must be within some bound (e.g. <100ms) of the live stream, while deeper levels are "best-effort" and may lag further behind. This turns an implicit risk (stale deep levels) into a stated guarantee consumers can design around, and justifies only aggressively re-syncing/validating the shallow part of the book on a tight loop.

9.5 Backpressure & slow-consumer handling

If tree-apply (or a downstream consumer, see 9.7) can't keep up with the WebSocket's event rate, events pile up somewhere. Needs an explicit policy: bounded in-memory queue with a max size, and on overflow either (a) drop and force a resync (safe, loses no correctness, costs a REST call), or (b) block the socket read (safe but risks the connection timing out server-side). Silently growing an unbounded buffer is the one option that's never acceptable — it masks the problem until it OOMs.

9.6 Memory bounds & long-tail price-level eviction

Under extreme volatility (flash crash, thin altcoin book), the tree can accumulate many far-from-touch price levels that will plausibly never trade. Worth capping total tracked levels per side (e.g. keep only the nearest 5000 to the touch, matching 9.2's snapshot cap) and evicting beyond that, rather than letting the tree grow unbounded during a volatile period.

9.7 Fan-out to multiple consumers

If more than one downstream service needs this book (a pricing service, a risk engine, a UI), each shouldn't open its own Binance connection — that multiplies exchange-side connection/rate-limit pressure for no benefit, since they'd all converge on the same state anyway. Better: one SyncManager per symbol publishes book deltas (or periodic snapshots) to an internal pub/sub layer (Kafka, Redis Streams, etc.), and consumers subscribe there instead of each re-implementing the Binance sync dance.

9.8 Connection resiliency beyond gap detection

Gap detection (Section 3c) catches missed events, but not a degraded connection — e.g. a socket that's alive but delivering events with growing latency, which won't trip the U/u continuity check. Worth adding: a staleness watchdog (already tracked in metrics.py) that forces a reconnect if no event has arrived within an expected interval, and for high-availability symbols, a secondary WebSocket connection run in parallel so a primary disconnect doesn't cause a visible gap.

9.9 Continuous integrity verification

Currently the book is only checked against Binance's source of truth reactively — when a gap is detected. For a stronger guarantee, periodically (e.g. every few minutes) fetch an independent REST snapshot and diff it against the live-maintained book even when no gap was detected, to catch silent corruption from a logic bug rather than just stream desync. This is strictly a monitoring addition (alert on mismatch), not a correctness mechanism — it should never be relied on to fix state, only to detect when something's wrong.
