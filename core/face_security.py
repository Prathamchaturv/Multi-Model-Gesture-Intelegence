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
import mediapipe as mp
import numpy as np


@dataclass
class FaceAuthResult:
    """Result payload for one face-security evaluation."""

    is_authorized: bool
    status_text: str
    face_detected: bool
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
    ) -> None:
        self._enabled = bool(enabled)
        self._similarity_threshold = float(similarity_threshold)
        self._eval_interval_s = max(0.0, float(eval_interval_s))

        root = Path(__file__).parent.parent
        self._authorized_image_path = Path(authorized_image_path)
        if not self._authorized_image_path.is_absolute():
            self._authorized_image_path = root / self._authorized_image_path

        self._authorized_encoding_path = Path(authorized_encoding_path)
        if not self._authorized_encoding_path.is_absolute():
            self._authorized_encoding_path = root / self._authorized_encoding_path

        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=float(min_detection_confidence),
        )

        self._reference_encoding: np.ndarray | None = self._load_or_build_reference()

        self._last_eval_ts: float = 0.0
        self._last_result = FaceAuthResult(
            is_authorized=not self._enabled,
            status_text='Face security disabled' if not self._enabled else 'No face detected',
            face_detected=False,
            similarity=None,
        )

    def evaluate(self, frame_bgr) -> FaceAuthResult:
        """Evaluate face authorization for the current camera frame."""
        if not self._enabled:
            self._last_result = FaceAuthResult(True, 'User Recognized [Face Security Disabled]', False, None)
            return self._last_result

        now = time.time()
        if self._eval_interval_s > 0 and (now - self._last_eval_ts) < self._eval_interval_s:
            return self._last_result
        self._last_eval_ts = now

        if self._reference_encoding is None:
            self._last_result = FaceAuthResult(False, 'Unknown User X (No Authorized Face Registered)', False, None)
            return self._last_result

        face_bbox = self._detect_face_bbox(frame_bgr)
        if face_bbox is None:
            self._last_result = FaceAuthResult(False, 'Unknown User X (No Face Detected)', False, None)
            return self._last_result

        encoding = self._encode_face(frame_bgr, face_bbox)
        if encoding is None:
            self._last_result = FaceAuthResult(False, 'Unknown User X (Face Encoding Failed)', True, None)
            return self._last_result

        similarity = self._cosine_similarity(encoding, self._reference_encoding)
        if similarity >= self._similarity_threshold:
            self._last_result = FaceAuthResult(True, 'User Recognized OK', True, similarity)
        else:
            self._last_result = FaceAuthResult(False, 'Unknown User X', True, similarity)
        return self._last_result

    def close(self) -> None:
        """Release detector resources."""
        try:
            self._detector.close()
        except Exception:
            pass

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
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        detections = result.detections if result is not None else None
        if not detections:
            return None

        h, w = frame_bgr.shape[:2]
        best = max(
            detections,
            key=lambda d: float(d.score[0]) if d.score else 0.0,
        )
        rel = best.location_data.relative_bounding_box
        x1 = max(0, int(rel.xmin * w))
        y1 = max(0, int(rel.ymin * h))
        x2 = min(w, int((rel.xmin + rel.width) * w))
        y2 = min(h, int((rel.ymin + rel.height) * h))
        if x2 <= x1 or y2 <= y1:
            return None
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
