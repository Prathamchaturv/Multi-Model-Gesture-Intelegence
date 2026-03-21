"""Lightweight runtime metrics manager for MMGI Phase 2."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import time


@dataclass
class MetricsSnapshot:
    gesture_accuracy_pct: float
    false_activation_rate_pct: float
    avg_response_latency_ms: float
    mode_switches_per_min: float


class MetricsManager:
    """Tracks core runtime metrics with minimal overhead."""

    def __init__(self, report_path: str | Path | None = None) -> None:
        if report_path is None:
            report_path = Path(__file__).parent.parent / 'logs' / 'metrics_report.jsonl'
        self._report_path = Path(report_path)

        self._gesture_events = 0
        self._gesture_confirmed = 0
        self._activation_attempts = 0
        self._false_activations = 0
        self._latencies = deque(maxlen=300)
        self._mode_switch_timestamps = deque(maxlen=240)
        self._last_flush_ts = 0.0

    def record_gesture_event(self, confirmed: bool) -> None:
        self._gesture_events += 1
        if confirmed:
            self._gesture_confirmed += 1

    def record_activation_attempt(self, succeeded: bool) -> None:
        self._activation_attempts += 1
        if not succeeded:
            self._false_activations += 1

    def record_latency(self, latency_ms: float) -> None:
        self._latencies.append(float(latency_ms))

    def record_mode_switch(self, timestamp: float | None = None) -> None:
        self._mode_switch_timestamps.append(time.time() if timestamp is None else float(timestamp))

    def snapshot(self) -> MetricsSnapshot:
        now = time.time()
        one_minute_ago = now - 60.0
        while self._mode_switch_timestamps and self._mode_switch_timestamps[0] < one_minute_ago:
            self._mode_switch_timestamps.popleft()

        gesture_accuracy = 0.0
        if self._gesture_events > 0:
            gesture_accuracy = (self._gesture_confirmed / self._gesture_events) * 100.0

        false_activation_rate = 0.0
        if self._activation_attempts > 0:
            false_activation_rate = (self._false_activations / self._activation_attempts) * 100.0

        avg_latency = 0.0
        if self._latencies:
            avg_latency = sum(self._latencies) / len(self._latencies)

        return MetricsSnapshot(
            gesture_accuracy_pct=round(gesture_accuracy, 2),
            false_activation_rate_pct=round(false_activation_rate, 2),
            avg_response_latency_ms=round(avg_latency, 2),
            mode_switches_per_min=float(len(self._mode_switch_timestamps)),
        )

    def flush_report(self, force: bool = False) -> MetricsSnapshot:
        now = time.time()
        if not force and (now - self._last_flush_ts) < 5.0:
            return self.snapshot()

        snap = self.snapshot()
        payload = {
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'gesture_accuracy_pct': snap.gesture_accuracy_pct,
            'false_activation_rate_pct': snap.false_activation_rate_pct,
            'avg_response_latency_ms': snap.avg_response_latency_ms,
            'mode_switches_per_min': snap.mode_switches_per_min,
        }

        self._report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._report_path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(payload) + '\n')

        self._last_flush_ts = now
        return snap
