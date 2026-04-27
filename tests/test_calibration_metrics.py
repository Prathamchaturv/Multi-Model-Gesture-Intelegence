"""Tests for Phase 2 calibration and metrics modules."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.calibration import CalibrationManager  # noqa: E402
from engine.metrics_manager import MetricsManager  # noqa: E402


def test_calibration_load_save_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / 'calibration.json'
        mgr = CalibrationManager(config_path=cfg)
        mgr.update(gesture_hold_seconds=1.4, stability_frames=9, base_cursor_sensitivity=1.3)
        mgr.save()

        reloaded = CalibrationManager(config_path=cfg)
        assert abs(reloaded.profile.gesture_hold_seconds - 1.4) < 1e-9
        assert reloaded.profile.stability_frames == 9
        assert abs(reloaded.profile.base_cursor_sensitivity - 1.3) < 1e-9


def test_calibration_cursor_sensitivity_changes_with_distance() -> None:
    mgr = CalibrationManager()
    mgr.update(
        min_cursor_sensitivity=0.5,
        max_cursor_sensitivity=1.8,
        near_hand_distance=0.24,
        far_hand_distance=0.08,
    )

    near_value = mgr.cursor_sensitivity_for_distance(0.24)
    far_value = mgr.cursor_sensitivity_for_distance(0.08)

    assert near_value > far_value
    assert 0.5 <= far_value <= 1.8
    assert 0.5 <= near_value <= 1.8


def test_calibration_wizard_completes_and_persists() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / 'calibration.json'
        mgr = CalibrationManager(config_path=cfg)
        step = mgr.start_wizard()
        assert 'baseline' in step.lower()

        msg = ''
        for sample in (0.16, 0.14, 0.12, 0.15):
            msg = mgr.wizard_record_sample(sample)

        assert 'complete' in msg.lower()
        assert cfg.exists()

        with open(cfg, 'r', encoding='utf-8') as fh:
            payload = json.load(fh)
        assert 'near_hand_distance' in payload
        assert 'far_hand_distance' in payload


def test_calibration_gesture_threshold_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / 'calibration.json'
        mgr = CalibrationManager(config_path=cfg)
        mgr.update_gesture_threshold(
            'Open Palm',
            min_confidence=0.72,
            required_stability_frames=8,
            required_hold_seconds=1.3,
        )
        mgr.save()

        reloaded = CalibrationManager(config_path=cfg)
        threshold = reloaded.profile.gesture_thresholds['Open Palm']
        assert abs(threshold.min_confidence - 0.72) < 1e-9
        assert threshold.required_stability_frames == 8
        assert abs(threshold.required_hold_seconds - 1.3) < 1e-9


def test_calibration_detects_pinch_from_landmarks() -> None:
    landmarks = [(0.0, 0.0, 0.0) for _ in range(21)]
    landmarks[4] = (0.10, 0.10, 0.10)   # thumb tip
    landmarks[8] = (0.11, 0.11, 0.10)   # index tip nearby
    assert CalibrationManager.is_pinch_detected(landmarks, threshold=0.03)

    landmarks[8] = (0.30, 0.30, 0.30)
    assert not CalibrationManager.is_pinch_detected(landmarks, threshold=0.03)


def test_metrics_snapshot_computation() -> None:
    metrics = MetricsManager()
    metrics.record_gesture_event(confirmed=True)
    metrics.record_gesture_event(confirmed=False)
    metrics.record_activation_attempt(succeeded=False)
    metrics.record_activation_attempt(succeeded=True)
    metrics.record_latency(15.0)
    metrics.record_latency(25.0)
    metrics.record_mode_switch(timestamp=100.0)

    snap = metrics.snapshot()
    assert snap.total_gestures_detected == 2
    assert snap.correct_predictions == 1
    assert snap.incorrect_predictions == 1
    assert abs(snap.accuracy_pct - 50.0) < 1e-9
    assert abs(snap.gesture_accuracy_pct - 50.0) < 1e-9
    assert abs(snap.false_activation_rate_pct - 50.0) < 1e-9
    assert abs(snap.avg_response_latency_ms - 20.0) < 1e-9


def test_metrics_flush_report_writes_json_line() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / 'metrics.jsonl'
        metrics = MetricsManager(report_path=out)
        metrics.record_gesture_event(confirmed=True)
        metrics.record_latency(12.0)
        _ = metrics.flush_report(force=True)
        assert out.exists()

        line = out.read_text(encoding='utf-8').strip().splitlines()[-1]
        payload = json.loads(line)
        assert 'total_gestures_detected' in payload
        assert 'accuracy_pct' in payload
        assert 'gesture_accuracy_pct' in payload
        assert 'avg_response_latency_ms' in payload


def test_metrics_record_prediction_and_accuracy() -> None:
    metrics = MetricsManager()
    assert metrics.record_prediction('Open Palm', 'Open Palm', confidence=0.91)
    assert not metrics.record_prediction('Fist', 'Open Palm', confidence=0.76)

    assert abs(metrics.calculate_accuracy() - 50.0) < 1e-9
    snap = metrics.snapshot()
    assert snap.total_gestures_detected == 2
    assert snap.correct_predictions == 1
    assert snap.incorrect_predictions == 1


def test_metrics_event_log_csv_and_dashboard_text() -> None:
    with tempfile.TemporaryDirectory() as td:
        events = Path(td) / 'events.csv'
        report = Path(td) / 'report.jsonl'
        metrics = MetricsManager(report_path=report, event_log_path=events, log_format='csv')
        metrics.record_prediction('Two Fingers', 'Two Fingers', confidence=0.88)
        metrics.record_prediction('Three Fingers', 'Four Fingers', confidence=0.52)

        csv_lines = events.read_text(encoding='utf-8').strip().splitlines()
        assert csv_lines[0].startswith('timestamp,predicted_gesture,expected_gesture,is_correct')
        assert len(csv_lines) == 3

        dashboard = metrics.dashboard_text()
        assert 'Gesture Performance Dashboard' in dashboard
        assert 'Total Gestures:' in dashboard
        assert 'Accuracy:' in dashboard
