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
        assert 'gesture_accuracy_pct' in payload
        assert 'avg_response_latency_ms' in payload
