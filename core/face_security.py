"""
Module: face_security.py
Description: Face-based authorization gate for System Mode.

Uses MediaPipe face detection to find a face ROI, builds a lightweight
deterministic face encoding from grayscale texture features, and compares it
with a stored authorized reference encoding.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class FaceAuthResult:
    """Result payload for one face-security evaluation."""

    is_authorized: bool
    status_text: str
    face_detected: bool
    user_present: bool
    system_paused: bool
    similarity: float | None = None


class FaceSecurityManager:
    """Evaluates whether the current camera face matches the authorized user."""

    def __init__(
        self,
        enabled: bool = True,
        authorized_image_path: str = 'config/authorized_face.jpg',
        authorized_encoding_path: str = 'config/authorized_face_encoding.json',
        similarity_threshold: float = 0.84,
        min_detection_confidence: float = 0.6,
        eval_interval_s: float = 0.08,
        away_delay_s: float = 2.5,
        return_confirm_s: float = 0.7,
    ) -> None:
        self._enabled = bool(enabled)
        self._similarity_threshold = float(similarity_threshold)
        self._eval_interval_s = max(0.0, float(eval_interval_s))
        self._away_delay_s = max(0.5, float(away_delay_s))
        self._return_confirm_s = max(0.1, float(return_confirm_s))

        root = Path(__file__).parent.parent
        self._authorized_image_path = Path(authorized_image_path)
        if not self._authorized_image_path.is_absolute():
            self._authorized_image_path = root / self._authorized_image_path

        self._authorized_encoding_path = Path(authorized_encoding_path)
        if not self._authorized_encoding_path.is_absolute():
            self._authorized_encoding_path = root / self._authorized_encoding_path

        # OpenCV Haar detector keeps runtime dependency lightweight and stable.
        self._face_detector_conf = float(min_detection_confidence)
        cascade_path = Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'
        self._face_cascade = cv2.CascadeClassifier(str(cascade_path))

        self._reference_encoding: np.ndarray | None = self._load_or_build_reference()
        self._last_face_seen_ts: float | None = None
        self._first_return_face_ts: float | None = None
        self._is_present_confirmed: bool = True

        self._last_eval_ts: float = 0.0
        self._last_result = FaceAuthResult(
            is_authorized=not self._enabled,
            status_text='Face security disabled' if not self._enabled else 'No face detected',
            face_detected=False,
            user_present=True,
            system_paused=False,
            similarity=None,
        )

    def evaluate(self, frame_bgr) -> FaceAuthResult:
        """Evaluate face authorization for the current camera frame."""
        if not self._enabled:
            self._last_result = FaceAuthResult(
                True,
                'User Detected - System Active [Face Security Disabled]',
                False,
                True,
                False,
                None,
            )
            return self._last_result

        now = time.time()
        if self._eval_interval_s > 0 and (now - self._last_eval_ts) < self._eval_interval_s:
            return self._last_result
        self._last_eval_ts = now

        if self._reference_encoding is None:
            self._last_result = FaceAuthResult(
                False,
                'Unknown User X (No Authorized Face Registered)',
                False,
                self._is_present_confirmed,
                not self._is_present_confirmed,
                None,
            )
            return self._last_result

        face_bbox = self._detect_face_bbox(frame_bgr)
        self._update_presence(face_bbox is not None, now)

        if not self._is_present_confirmed:
            self._last_result = FaceAuthResult(
                False,
                'User Away - System Paused',
                face_bbox is not None,
                False,
                True,
                None,
            )
            return self._last_result

        if face_bbox is None:
            self._last_result = FaceAuthResult(
                False,
                'Unknown User X (No Face Detected)',
                False,
                True,
                False,
                None,
            )
            return self._last_result

        encoding = self._encode_face(frame_bgr, face_bbox)
        if encoding is None:
            self._last_result = FaceAuthResult(
                False,
                'Unknown User X (Face Encoding Failed)',
                True,
                True,
                False,
                None,
            )
            return self._last_result

        similarity = self._cosine_similarity(encoding, self._reference_encoding)
        if similarity >= self._similarity_threshold:
            self._last_result = FaceAuthResult(
                True,
                'User Detected - System Active',
                True,
                True,
                False,
                similarity,
            )
        else:
            self._last_result = FaceAuthResult(
                False,
                'Unknown User X',
                True,
                True,
                False,
                similarity,
            )
        return self._last_result

    def _update_presence(self, face_visible: bool, now: float) -> None:
        if face_visible:
            self._last_face_seen_ts = now
            if self._is_present_confirmed:
                self._first_return_face_ts = None
                return

            if self._first_return_face_ts is None:
                self._first_return_face_ts = now
                return

            if (now - self._first_return_face_ts) >= self._return_confirm_s:
                self._is_present_confirmed = True
                self._first_return_face_ts = None
            return

        self._first_return_face_ts = None
        if self._last_face_seen_ts is None:
            self._last_face_seen_ts = now

        if (now - self._last_face_seen_ts) >= self._away_delay_s:
            self._is_present_confirmed = False

    def close(self) -> None:
        """Release detector resources."""
        return None

    def _load_or_build_reference(self) -> np.ndarray | None:
        from_file = self._load_reference_from_file()
        if from_file is not None:
            return from_file

        if not self._authorized_image_path.exists():
            return None

        ref_image = cv2.imread(str(self._authorized_image_path))
        if ref_image is None:
            return None

        bbox = self._detect_face_bbox(ref_image)
        if bbox is None:
            return None

        encoding = self._encode_face(ref_image, bbox)
        if encoding is None:
            return None

        self._save_reference_to_file(encoding)
        return encoding

    def _load_reference_from_file(self) -> np.ndarray | None:
        if not self._authorized_encoding_path.exists():
            return None
        try:
            with open(self._authorized_encoding_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            vec = np.asarray(data.get('encoding', []), dtype=np.float32)
            if vec.size == 0:
                return None
            return self._normalize(vec)
        except Exception:
            return None

    def _save_reference_to_file(self, encoding: np.ndarray) -> None:
        try:
            self._authorized_encoding_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                'version': 1,
                'encoding': encoding.astype(float).tolist(),
            }
            with open(self._authorized_encoding_path, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh, indent=2)
        except Exception:
            pass

    def _detect_face_bbox(self, frame_bgr) -> tuple[int, int, int, int] | None:
        if self._face_cascade.empty():
            return None

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(40, 40),
        )
        if len(faces) == 0:
            return None

        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = int(x + w)
        y2 = int(y + h)
        return x1, y1, x2, y2

    def _encode_face(self, frame_bgr, bbox: tuple[int, int, int, int]) -> np.ndarray | None:
        x1, y1, x2, y2 = bbox
        roi = frame_bgr[y1:y2, x1:x2]
        if roi is None or roi.size == 0:
            return None

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if gray.shape[0] < 24 or gray.shape[1] < 24:
            return None

        gray = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA)
        gray = cv2.equalizeHist(gray)

        hist = cv2.calcHist([gray], [0], None, [48], [0, 256]).flatten().astype(np.float32)
        hist = self._normalize(hist)

        small = cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32).flatten()
        small = self._normalize(small)

        edges = cv2.Canny(gray, 50, 120)
        edge_hist = cv2.calcHist([edges], [0], None, [16], [0, 256]).flatten().astype(np.float32)
        edge_hist = self._normalize(edge_hist)

        vec = np.concatenate([hist, small, edge_hist]).astype(np.float32)
        return self._normalize(vec)

    @staticmethod
    def _normalize(vec: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vec))
        if norm < 1e-8:
            return vec
        return vec / norm

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))
