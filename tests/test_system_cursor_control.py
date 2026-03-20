"""
Unit tests for advanced System Mode cursor control helpers.
"""

import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.system_mode_engine import AirMouseController  # noqa: E402


def _landmarks_with_thumb_index_distance(dist: float) -> list[tuple[float, float, float]]:
    """Build synthetic landmarks with configurable thumb-index tip distance."""
    points = [(0.5, 0.5, 0.0)] * 21
    points[4] = (0.4, 0.4, 0.0)          # thumb tip
    points[8] = (0.4 + dist, 0.4, 0.0)   # index tip
    return points


def test_pinch_engages_when_distance_below_threshold() -> None:
    ctrl = AirMouseController.__new__(AirMouseController)
    ctrl._THUMB_LM = 4
    ctrl._INDEX_LM = 8
    ctrl._pinch_threshold = 0.045
    ctrl._pinch_release_threshold = 0.065
    ctrl._pinch_active = False

    assert ctrl._update_pinch_state(_landmarks_with_thumb_index_distance(0.03)) is True


def test_pinch_releases_only_after_release_threshold() -> None:
    ctrl = AirMouseController.__new__(AirMouseController)
    ctrl._THUMB_LM = 4
    ctrl._INDEX_LM = 8
    ctrl._pinch_threshold = 0.045
    ctrl._pinch_release_threshold = 0.065
    ctrl._pinch_active = True

    # Still pinched (hysteresis keeps active)
    assert ctrl._update_pinch_state(_landmarks_with_thumb_index_distance(0.055)) is True
    # Released
    assert ctrl._update_pinch_state(_landmarks_with_thumb_index_distance(0.08)) is False


def test_distance_3d_uses_xyz_components() -> None:
    d = AirMouseController._distance_3d((0.0, 0.0, 0.0), (0.0, 0.3, 0.4))
    assert round(d, 3) == 0.5
