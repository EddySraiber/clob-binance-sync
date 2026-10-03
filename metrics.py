"""
Minimal in-memory metrics for observability/monitoring.
In a real deployment, `as_dict()` would be exported to Prometheus/StatsD/etc.
on an interval instead of just being readable in-process.
"""
import time
from dataclasses import dataclass, field


@dataclass
class Metrics:
    snapshots_loaded: int = 0
    updates_applied: int = 0
    gaps_detected: int = 0
    last_event_ts: float = field(default_factory=time.time)

    def record_snapshot(self) -> None:
        self.snapshots_loaded += 1
        self.last_event_ts = time.time()

    def record_update(self, event: dict) -> None:
        self.updates_applied += 1
        self.last_event_ts = time.time()

    def record_gap(self) -> None:
        self.gaps_detected += 1

    def staleness_seconds(self) -> float:
        return time.time() - self.last_event_ts

    def as_dict(self) -> dict:
        return {
            "snapshots_loaded": self.snapshots_loaded,
            "updates_applied": self.updates_applied,
            "gaps_detected": self.gaps_detected,
            "staleness_seconds": round(self.staleness_seconds(), 3),
        }
