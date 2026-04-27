"""User feedback capture for gesture/action validation."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
import threading

from engine.metrics_manager import MetricsManager


@dataclass
class FeedbackEntry:
    timestamp: str
    action: str
    is_correct: bool
    source: str = 'gesture'
    predicted_gesture: str | None = None
    expected_gesture: str | None = None


class FeedbackManager:
    """Collects post-action user feedback and persists it to JSON."""

    def __init__(
        self,
        metrics: MetricsManager,
        feedback_path: str | Path | None = None,
    ) -> None:
        self._metrics = metrics
        if feedback_path is None:
            feedback_path = Path(__file__).parent.parent / 'logs' / 'action_feedback.json'
        self._feedback_path = Path(feedback_path)
        self._lock = threading.Lock()

    def ask_feedback_console(self, action: str) -> bool | None:
        """Prompt user in console to mark action as correct or incorrect."""
        prompt = f"Action '{action}' -> Was this correct? [c=correct, i=incorrect, s=skip]: "
        try:
            while True:
                answer = input(prompt).strip().lower()
                if answer in {'c', 'correct', 'y', 'yes'}:
                    return True
                if answer in {'i', 'incorrect', 'n', 'no'}:
                    return False
                if answer in {'s', 'skip', ''}:
                    return None
                print('Please enter c, i, or s.')
        except (EOFError, KeyboardInterrupt):
            return None

    def record_feedback(
        self,
        *,
        action: str,
        is_correct: bool,
        source: str = 'gesture',
        predicted_gesture: str | None = None,
        expected_gesture: str | None = None,
    ) -> FeedbackEntry:
        """Persist one feedback item and update metrics."""
        entry = FeedbackEntry(
            timestamp=datetime.now().isoformat(timespec='seconds'),
            action=str(action),
            is_correct=bool(is_correct),
            source=str(source),
            predicted_gesture=predicted_gesture,
            expected_gesture=expected_gesture,
        )

        with self._lock:
            items = self._load_existing()
            items.append(asdict(entry))
            self._feedback_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._feedback_path, 'w', encoding='utf-8') as fh:
                json.dump(items, fh, indent=2)

        self._metrics.record_feedback_result(entry.is_correct)
        return entry

    def ask_and_record(
        self,
        *,
        action: str,
        source: str = 'gesture',
        predicted_gesture: str | None = None,
        expected_gesture: str | None = None,
    ) -> FeedbackEntry | None:
        """Ask for feedback from console and persist when provided."""
        answer = self.ask_feedback_console(action)
        if answer is None:
            return None
        return self.record_feedback(
            action=action,
            is_correct=answer,
            source=source,
            predicted_gesture=predicted_gesture,
            expected_gesture=expected_gesture,
        )

    def _load_existing(self) -> list[dict]:
        if not self._feedback_path.exists():
            return []
        try:
            with open(self._feedback_path, 'r', encoding='utf-8') as fh:
                payload = json.load(fh)
            if isinstance(payload, list):
                return payload
        except Exception:
            return []
        return []
