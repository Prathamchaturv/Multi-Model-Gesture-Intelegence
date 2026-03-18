"""
Module: hand_tracking.py
Description: MediaPipe HandLandmarker wrapper — detects hands in video frames,
             extracts 21 3-D landmarks, draws the hand skeleton overlay, and
             determines per-finger extension states.
Author: Pratham Chaturvedi

core/hand_tracking.py - The Hand Detective

Uses MediaPipe AI technology (Tasks API, mediapipe >= 0.10.0) to:
- Find hands in camera frames via the HandLandmarker task
- Identify 21 landmark points (fingertips, knuckles, wrist, etc.)
- Draw the hand skeleton visualisation (manual cv2 render)
- Determine which fingers are up or down
- Distinguish between left and right hands
- Support up to 2 hands simultaneously

Requires: hand_landmarker.task model file in the project root.
Download: https://storage.googleapis.com/mediapipe-models/hand_landmarker/
          hand_landmarker/float16/1/hand_landmarker.task
"""

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from pathlib import Path


# Hand skeleton connection pairs (MediaPipe landmark index pairs)
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),           # index
    (5, 9), (9, 10), (10, 11), (11, 12),      # middle
    (9, 13), (13, 14), (14, 15), (15, 16),    # ring
    (13, 17), (17, 18), (18, 19), (19, 20),   # pinky
    (0, 17),                                   # palm base
]

# Landmark colours by finger group (BGR)
_LANDMARK_COLOURS = {
    'thumb':  (255, 100,   0),
    'index':  (  0, 255,   0),
    'middle': (255, 255,   0),
    'ring':   (  0, 150, 255),
    'pinky':  (255,   0, 200),
    'wrist':  (200, 200, 200),
}

_TIP_GROUPS = {
    'thumb':  [1, 2, 3, 4],
    'index':  [5, 6, 7, 8],
    'middle': [9, 10, 11, 12],
    'ring':   [13, 14, 15, 16],
    'pinky':  [17, 18, 19, 20],
    'wrist':  [0],
}


class HandTracker:
    """
    Wraps the MediaPipe Tasks HandLandmarker to provide hand detection,
    landmark extraction, finger-state analysis, and on-screen drawing.
    """

    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        model_path: str | None = None,
    ):
        # Resolve model file
        if model_path is None:
            model_path = str(Path(__file__).parent.parent / 'hand_landmarker.task')

        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_tracking_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._detector = mp_vision.HandLandmarker.create_from_options(options)
        self._frame_ts: int = 0   # monotonic timestamp in ms

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_hands(self, frame):
        """
        Run MediaPipe inference on a BGR frame.
        Returns the raw HandLandmarkerResult object.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._frame_ts += 33   # ~30 fps heartbeat (must be strictly increasing)
        result = self._detector.detect_for_video(mp_image, self._frame_ts)
        return result

    def get_hands_info(self, results) -> dict:
        """
        Parse HandLandmarkerResult into a structured dict:
        {
            'count': int,
            'left':  hand_data | None,
            'right': hand_data | None,
        }

        Each hand_data dict has:
            'landmarks'    : list of (x, y, z) normalised coords
            'finger_states': dict of finger→bool (True = extended)
            'handedness'   : 'Left' | 'Right'
            'confidence'   : handedness score (0.0-1.0)
        """
        info: dict = {'count': 0, 'left': None, 'right': None}

        if not results.hand_landmarks:
            return info

        for lm_list, handedness_list in zip(
            results.hand_landmarks, results.handedness
        ):
            label: str = handedness_list[0].category_name  # 'Left' or 'Right'
            finger_states = self._get_finger_states(lm_list)
            landmarks_tuple = [(lm.x, lm.y, lm.z) for lm in lm_list]

            hand_data = {
                'landmarks':     landmarks_tuple,
                'finger_states': finger_states,
                'handedness':    label,
                'confidence':    float(getattr(handedness_list[0], 'score', 0.0) or 0.0),
            }

            info['count'] += 1
            if label == 'Right':
                info['right'] = hand_data
            else:
                info['left'] = hand_data

        return info

    # ------------------------------------------------------------------
    # Finger state detection
    # ------------------------------------------------------------------

    def _get_finger_states(self, lm_list) -> dict:
        """
        Determine which fingers are extended (True) or curled (False).

        Thumb  : extended when x-distance tip→wrist > ip→wrist
        Others : extended when tip.y < pip.y (tip is higher on screen)
        """
        states: dict = {}

        # --- Thumb ---
        wrist     = lm_list[0]
        thumb_tip = lm_list[4]
        thumb_ip  = lm_list[3]
        states['thumb'] = abs(thumb_tip.x - wrist.x) > abs(thumb_ip.x - wrist.x)

        # --- Index, Middle, Ring, Pinky ---
        for name, tip_id, pip_id in [
            ('index',  8,  6),
            ('middle', 12, 10),
            ('ring',   16, 14),
            ('pinky',  20, 18),
        ]:
            states[name] = lm_list[tip_id].y < lm_list[pip_id].y

        return states

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def draw_landmarks(self, frame, results):
        """Draw hand skeleton connections and coloured landmark dots."""
        if not results.hand_landmarks:
            return frame

        h, w = frame.shape[:2]

        for lm_list in results.hand_landmarks:
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in lm_list]

            # Connections
            for a, b in _HAND_CONNECTIONS:
                cv2.line(frame, pts[a], pts[b], (180, 180, 180), 1, cv2.LINE_AA)

            # Landmark dots coloured by finger group
            for group, ids in _TIP_GROUPS.items():
                colour = _LANDMARK_COLOURS[group]
                for idx in ids:
                    cv2.circle(frame, pts[idx], 5, colour, -1, cv2.LINE_AA)
                    cv2.circle(frame, pts[idx], 5, (255, 255, 255), 1, cv2.LINE_AA)

        return frame

    def display_hand_detection(self, frame, hands_info: dict):
        """Render hand count badge in the top-right corner."""
        h, w = frame.shape[:2]
        text = f"Hands: {hands_info['count']}"
        cv2.putText(
            frame, text, (w - 150, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2, cv2.LINE_AA,
        )
        for key, colour in [('right', (0, 255, 100)), ('left', (100, 200, 255))]:
            if hands_info.get(key):
                lms = hands_info[key]['landmarks']
                wx = int(lms[0][0] * w)
                wy = int(lms[0][1] * h) + 20
                cv2.putText(
                    frame, key.upper(), (wx - 20, wy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2, cv2.LINE_AA,
                )
        return frame

    def display_finger_states(self, frame, finger_states: dict):
        """Render finger up/down states in the bottom-left corner."""
        h = frame.shape[0]
        y = h - 150
        for name, up in finger_states.items():
            colour = (0, 255, 0) if up else (0, 0, 220)
            label  = f'{name}: {"UP" if up else "DOWN"}'
            cv2.putText(
                frame, label, (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, colour, 1, cv2.LINE_AA,
            )
            y += 26
        return frame

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._detector.close()
