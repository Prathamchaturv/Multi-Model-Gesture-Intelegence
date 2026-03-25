"""
Cursor movement controller with smooth tracking and dead zone filtering.

Handles real-time cursor positioning based on index finger landmarks,
with configurable smoothing and dead zone for noise reduction.
"""

import time
import pyautogui
from pathlib import Path


class CursorController:
    """
    Smooth cursor control based on index finger tip position.
    
    Applies exponential smoothing to reduce jitter, implements dead zone
    for noise filtering, and maintains frame stability thresholds.
    """

    def __init__(
        self,
        smoothing_factor: float = 0.2,
        dead_zone_pixels: int = 5,
        frame_threshold: int = 2,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ):
        """
        Initialize cursor controller.
        
        Args:
            smoothing_factor: Exponential smoothing (0.1-0.5 recommended)
                             Higher = more responsive, Lower = smoother
            dead_zone_pixels: Minimum movement before cursor updates (1-5 recommended)
            frame_threshold: Frames needed before activation (1-3 recommended)
            screen_width: Display width in pixels
            screen_height: Display height in pixels
        """
        self.smoothing_factor = max(0.05, min(0.8, float(smoothing_factor)))
        self.dead_zone_pixels = max(1, int(dead_zone_pixels))
        self.frame_threshold = max(1, int(frame_threshold))
        self.screen_width = max(640, int(screen_width))
        self.screen_height = max(480, int(screen_height))

        # State tracking
        self.prev_x: float | None = None
        self.prev_y: float | None = None
        self.is_active = False
        self.frame_count = 0
        self.last_update_time = 0.0

    def update(self, index_landmark: tuple[float, float] | None) -> bool:
        """
        Update cursor position based on index finger landmark.
        
        Args:
            index_landmark: (x, y) normalized coordinates (0.0-1.0)
                           of index finger tip, or None if hand not visible
        
        Returns:
            True if cursor was updated, False otherwise
        """
        if index_landmark is None:
            # Hand not visible, reset state
            self.is_active = False
            self.frame_count = 0
            self.prev_x = None
            self.prev_y = None
            return False

        self.frame_count += 1

        # Only activate after frame threshold
        if self.frame_count < self.frame_threshold:
            return False

        if not self.is_active:
            self.is_active = True
            # Initialize position on first activation
            norm_x, norm_y = index_landmark
            self.prev_x = norm_x * self.screen_width
            self.prev_y = norm_y * self.screen_height

        # Convert normalized coordinates to screen pixels
        curr_x = index_landmark[0] * self.screen_width
        curr_y = index_landmark[1] * self.screen_height

        # Apply exponential smoothing
        if self.prev_x is not None and self.prev_y is not None:
            smooth_x = self.prev_x + (curr_x - self.prev_x) * self.smoothing_factor
            smooth_y = self.prev_y + (curr_y - self.prev_y) * self.smoothing_factor
        else:
            smooth_x = curr_x
            smooth_y = curr_y

        # Clamp to screen boundaries BEFORE dead zone check
        # Use screen dimensions directly (not -1) to reach full screen including edges
        clamped_x = max(0, min(self.screen_width, int(smooth_x)))
        clamped_y = max(0, min(self.screen_height, int(smooth_y)))

        # Check dead zone (minimum movement threshold)
        prev_clamped_x = max(0, min(self.screen_width, int(self.prev_x or clamped_x)))
        prev_clamped_y = max(0, min(self.screen_height, int(self.prev_y or clamped_y)))
        
        delta_x = abs(clamped_x - prev_clamped_x)
        delta_y = abs(clamped_y - prev_clamped_y)

        if delta_x < self.dead_zone_pixels and delta_y < self.dead_zone_pixels:
            # Movement too small, ignore
            return False

        # Update cursor position
        self.prev_x = smooth_x
        self.prev_y = smooth_y
        self.last_update_time = time.time()

        try:
            pyautogui.moveTo(clamped_x, clamped_y, duration=0)
            return True
        except Exception:
            # pyautogui not available or other error
            return False

    def reset(self):
        """Reset controller state (call when gesture ends)."""
        self.is_active = False
        self.frame_count = 0
        self.prev_x = None
        self.prev_y = None
        self.last_update_time = 0.0
