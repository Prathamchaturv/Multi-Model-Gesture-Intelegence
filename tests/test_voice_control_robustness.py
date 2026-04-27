"""Robustness tests for noisy-environment voice recognition controls."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.voice_control import VoiceCommandListener  # noqa: E402


def test_effective_confidence_threshold_rises_with_noise_and_failures() -> None:
    listener = VoiceCommandListener(
        enabled=False,
        confidence_threshold=0.6,
        adaptive_confidence_enabled=True,
        noise_gate_rms=10.0,
        confidence_penalty_per_retry=0.1,
    )

    # Seed noisy environment samples.
    for rms in (30.0, 32.0, 35.0, 29.0):
        listener._update_noise_history(rms)
    listener._consecutive_decode_failures = 2

    threshold = listener._effective_confidence_threshold()
    assert threshold > 0.6
    assert threshold <= 0.95


def test_effective_confidence_threshold_static_when_adaptive_disabled() -> None:
    listener = VoiceCommandListener(
        enabled=False,
        confidence_threshold=0.7,
        adaptive_confidence_enabled=False,
    )

    for rms in (40.0, 45.0):
        listener._update_noise_history(rms)
    listener._consecutive_decode_failures = 3

    assert abs(listener._effective_confidence_threshold() - 0.7) < 1e-9


def test_noise_reduction_can_gate_low_rms_signal() -> None:
    np = __import__('numpy')
    listener = VoiceCommandListener(
        enabled=False,
        noise_reduction_enabled=True,
        noise_gate_rms=2000.0,
    )

    # Very small amplitude signal should be treated as noise.
    pcm = np.array([1, -1, 2, -2, 1, -1], dtype=np.int16)
    result = listener._reduce_noise_int16(pcm, 16000)
    assert result is None
