"""Lightweight runtime metrics manager for MMGI Phase 2."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import time
import csv


@dataclass
class MetricsSnapshot:
    total_gestures_detected: int
    correct_predictions: int
    incorrect_predictions: int
    accuracy_pct: float
    gesture_accuracy_pct: float
    false_activation_rate_pct: float
    avg_response_latency_ms: float
    mode_switches_per_min: float


class MetricsManager:
    """Tracks core runtime metrics with minimal overhead."""

    def __init__(
        self,
        report_path: str | Path | None = None,
        event_log_path: str | Path | None = None,
        log_format: str = 'jsonl',
    ) -> None:
        if report_path is None:
            report_path = Path(__file__).parent.parent / 'logs' / 'metrics_report.jsonl'
        self._report_path = Path(report_path)
        self._log_format = str(log_format).strip().lower()
        if self._log_format not in {'jsonl', 'csv'}:
            self._log_format = 'jsonl'
        if event_log_path is None:
            suffix = 'jsonl' if self._log_format == 'jsonl' else 'csv'
            event_log_path = Path(__file__).parent.parent / 'logs' / f'gesture_prediction_events.{suffix}'
        self._event_log_path = Path(event_log_path)
        self._csv_header_written = False

        self._gesture_events = 0
        self._gesture_confirmed = 0
        self._total_gestures_detected = 0
        self._correct_predictions = 0
        self._incorrect_predictions = 0
        self._activation_attempts = 0
        self._false_activations = 0
        self._latencies = deque(maxlen=300)
        self._mode_switch_timestamps = deque(maxlen=240)
        self._last_flush_ts = 0.0

    def record_gesture_event(
        self,
        confirmed: bool,
        gesture: str | None = None,
        confidence: float | None = None,
    ) -> None:
        self._gesture_events += 1
        self._total_gestures_detected += 1
        if confirmed:
            self._gesture_confirmed += 1
            self._correct_predictions += 1
        else:
            self._incorrect_predictions += 1

        self._log_prediction_event(
            predicted_gesture=gesture or 'Unknown',
            expected_gesture=None,
            is_correct=bool(confirmed),
            confidence=confidence,
        )

    def record_prediction(
        self,
        predicted_gesture: str,
        expected_gesture: str,
        confidence: float | None = None,
        timestamp: float | None = None,
    ) -> bool:
        """Record one labeled prediction and return whether it was correct."""
        predicted = str(predicted_gesture)
        expected = str(expected_gesture)
        is_correct = predicted == expected

        self._gesture_events += 1
        self._total_gestures_detected += 1
        if is_correct:
            self._gesture_confirmed += 1
            self._correct_predictions += 1
        else:
            self._incorrect_predictions += 1

        self._log_prediction_event(
            predicted_gesture=predicted,
            expected_gesture=expected,
            is_correct=is_correct,
            confidence=confidence,
            timestamp=timestamp,
        )
        return is_correct

    def calculate_accuracy(self) -> float:
        """Return prediction accuracy as percentage in [0, 100]."""
        if self._total_gestures_detected <= 0:
            return 0.0
        return (self._correct_predictions / self._total_gestures_detected) * 100.0

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

        accuracy = self.calculate_accuracy()

        return MetricsSnapshot(
            total_gestures_detected=self._total_gestures_detected,
            correct_predictions=self._correct_predictions,
            incorrect_predictions=self._incorrect_predictions,
            accuracy_pct=round(accuracy, 2),
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
            'total_gestures_detected': snap.total_gestures_detected,
            'correct_predictions': snap.correct_predictions,
            'incorrect_predictions': snap.incorrect_predictions,
            'accuracy_pct': snap.accuracy_pct,
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

    def dashboard_text(self) -> str:
        """Render a simple console dashboard string for quick monitoring."""
        snap = self.snapshot()
        lines = [
            '=== Gesture Performance Dashboard ===',
            f"Total Gestures:     {snap.total_gestures_detected}",
            f"Correct Predictions:{snap.correct_predictions}",
            f"Incorrect Predictions:{snap.incorrect_predictions}",
            f"Accuracy:           {snap.accuracy_pct:.2f}%",
            f"False Activations:  {snap.false_activation_rate_pct:.2f}%",
            f"Avg Latency:        {snap.avg_response_latency_ms:.2f} ms",
            f"Mode Switches/min:  {snap.mode_switches_per_min:.0f}",
        ]
        return '\n'.join(lines)

    def print_dashboard(self) -> None:
        print(self.dashboard_text())

    def _log_prediction_event(
        self,
        *,
        predicted_gesture: str,
        expected_gesture: str | None,
        is_correct: bool,
        confidence: float | None,
        timestamp: float | None = None,
    ) -> None:
        payload = {
            'timestamp': datetime.fromtimestamp(
                time.time() if timestamp is None else float(timestamp)
            ).isoformat(timespec='milliseconds'),
            'predicted_gesture': str(predicted_gesture),
            'expected_gesture': expected_gesture,
            'is_correct': bool(is_correct),
            'confidence': None if confidence is None else round(float(confidence), 4),
            'running_total': self._total_gestures_detected,
            'running_correct': self._correct_predictions,
            'running_incorrect': self._incorrect_predictions,
            'running_accuracy_pct': round(self.calculate_accuracy(), 2),
        }

        self._event_log_path.parent.mkdir(parents=True, exist_ok=True)
        if self._log_format == 'csv':
            self._write_prediction_csv(payload)
        else:
            with open(self._event_log_path, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(payload) + '\n')

    def _write_prediction_csv(self, payload: dict) -> None:
        write_header = not self._csv_header_written
        if not self._event_log_path.exists() or self._event_log_path.stat().st_size == 0:
            write_header = True

        fields = [
            'timestamp',
            'predicted_gesture',
            'expected_gesture',
            'is_correct',
            'confidence',
            'running_total',
            'running_correct',
            'running_incorrect',
            'running_accuracy_pct',
        ]

        with open(self._event_log_path, 'a', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            if write_header:
                writer.writeheader()
                self._csv_header_written = True
            writer.writerow(payload)
