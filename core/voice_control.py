"""
Voice command listener for MMGI multimodal control.
"""

from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import dataclass

try:
    import speech_recognition as sr  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency at runtime
    sr = None


@dataclass
class VoiceCommandEvent:
    command: str
    transcript: str
    timestamp: float


class VoiceCommandListener:
    """Background speech listener that emits normalized command tokens."""

    def __init__(
        self,
        enabled: bool = True,
        listen_timeout_s: float = 1.2,
        phrase_time_limit_s: float = 2.0,
        poll_sleep_s: float = 0.05,
        energy_threshold: int = 250,
    ) -> None:
        self._enabled = bool(enabled)
        self._listen_timeout_s = float(listen_timeout_s)
        self._phrase_time_limit_s = float(phrase_time_limit_s)
        self._poll_sleep_s = float(poll_sleep_s)
        self._energy_threshold = int(energy_threshold)

        self._events: queue.Queue[VoiceCommandEvent] = queue.Queue(maxsize=32)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ready = False
        self._last_error: str | None = None

    @property
    def is_available(self) -> bool:
        return sr is not None

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self.is_available

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def start(self) -> None:
        if not self.is_enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name='MMGI-VoiceListener')
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None

    def poll_latest(self) -> VoiceCommandEvent | None:
        """Return the newest voice command event currently queued."""
        latest = None
        while True:
            try:
                latest = self._events.get_nowait()
            except queue.Empty:
                return latest

    def _run(self) -> None:
        assert sr is not None
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = self._energy_threshold
        recognizer.dynamic_energy_threshold = True

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.4)
                self._ready = True
                while not self._stop_event.is_set():
                    try:
                        audio = recognizer.listen(
                            source,
                            timeout=self._listen_timeout_s,
                            phrase_time_limit=self._phrase_time_limit_s,
                        )
                    except sr.WaitTimeoutError:
                        continue

                    try:
                        transcript = recognizer.recognize_google(audio)
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as exc:
                        self._last_error = f'Voice API error: {exc}'
                        time.sleep(self._poll_sleep_s)
                        continue

                    command = normalize_voice_command(transcript)
                    if command is None:
                        continue

                    evt = VoiceCommandEvent(
                        command=command,
                        transcript=transcript,
                        timestamp=time.time(),
                    )
                    try:
                        self._events.put_nowait(evt)
                    except queue.Full:
                        _ = self._events.get_nowait()
                        self._events.put_nowait(evt)
        except Exception as exc:  # microphone/device errors
            self._last_error = f'Voice listener unavailable: {exc}'


def normalize_voice_command(transcript: str) -> str | None:
    """Map free-form speech to canonical command tokens."""
    text = re.sub(r'[^a-z0-9\s]', ' ', transcript.lower()).strip()
    text = re.sub(r'\s+', ' ', text)

    if not text:
        return None

    if any(k in text for k in ('play song', 'play music', 'play', 'resume')):
        return 'play_song'
    if any(k in text for k in ('pause song', 'pause music', 'pause', 'stop music')):
        return 'pause'
    if any(k in text for k in ('next track', 'next song', 'skip')):
        return 'next_track'
    if any(k in text for k in ('previous track', 'previous song', 'back track')):
        return 'previous_track'
    if any(k in text for k in ('volume up', 'increase volume', 'louder')):
        return 'volume_up'
    if any(k in text for k in ('volume down', 'decrease volume', 'softer')):
        return 'volume_down'
    if any(k in text for k in ('mute', 'silence')):
        return 'mute'

    return None
