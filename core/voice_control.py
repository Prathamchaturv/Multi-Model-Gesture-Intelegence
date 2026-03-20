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

try:
    import pyaudio  # type: ignore[import-not-found]
    _HAS_PYAUDIO = True
except Exception:
    _HAS_PYAUDIO = False

try:
    import numpy as np
    import sounddevice as sd
except Exception:  # pragma: no cover - optional dependency at runtime
    np = None
    sd = None


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
        recognition_language: str = 'en-IN',
    ) -> None:
        self._enabled = bool(enabled)
        self._listen_timeout_s = float(listen_timeout_s)
        self._phrase_time_limit_s = float(phrase_time_limit_s)
        self._poll_sleep_s = float(poll_sleep_s)
        self._energy_threshold = int(energy_threshold)
        self._recognition_language = str(recognition_language or 'en-IN')

        self._events: queue.Queue[VoiceCommandEvent] = queue.Queue(maxsize=32)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ready = False
        self._last_error: str | None = None
        self._sounddevice_input_device: int | None = None

    @property
    def is_available(self) -> bool:
        return sr is not None and (_HAS_PYAUDIO or (sd is not None and np is not None))

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self.is_available

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def is_ready(self) -> bool:
        return self._ready

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
            if _HAS_PYAUDIO:
                self._run_with_pyaudio(recognizer)
            elif sd is not None and np is not None:
                self._run_with_sounddevice(recognizer)
            else:
                self._last_error = 'No supported microphone backend available'
        except Exception as exc:  # microphone/device errors
            self._last_error = f'Voice listener unavailable: {exc}'

    def _run_with_pyaudio(self, recognizer) -> None:
        assert sr is not None
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

                self._consume_audio(recognizer, audio)

    def _run_with_sounddevice(self, recognizer) -> None:
        assert sr is not None and sd is not None and np is not None
        self._sounddevice_input_device = self._select_input_device()
        if self._sounddevice_input_device is None:
            self._last_error = 'No input microphone device found'
            return

        try:
            device_info = sd.query_devices(self._sounddevice_input_device, 'input')
            sample_rate = int(device_info.get('default_samplerate') or 16000)
        except Exception:
            sample_rate = 16000
        self._ready = True

        while not self._stop_event.is_set():
            frames = int(max(0.3, self._phrase_time_limit_s) * sample_rate)
            recording = sd.rec(
                frames,
                samplerate=sample_rate,
                channels=1,
                dtype='int16',
                device=self._sounddevice_input_device,
                blocking=True,
            )

            if self._stop_event.is_set():
                break

            if recording is None or recording.size == 0:
                time.sleep(self._poll_sleep_s)
                continue

            if getattr(recording, 'ndim', 1) > 1:
                recording = recording[:, 0]

            # Skip only near-zero silence to avoid dropping low-volume speech.
            rms = float(np.sqrt(np.mean(np.square(recording.astype(np.float32)))))
            if rms < 8.0:
                time.sleep(self._poll_sleep_s)
                continue

            pcm = np.ascontiguousarray(recording).tobytes()
            audio = sr.AudioData(pcm, sample_rate, 2)
            self._consume_audio(recognizer, audio)
            time.sleep(self._poll_sleep_s)

    @staticmethod
    def _select_input_device() -> int | None:
        """Return a best-effort microphone device index for sounddevice."""
        assert sd is not None

        # Prefer default input device when available.
        try:
            default_input, _ = sd.default.device
            if default_input is not None and int(default_input) >= 0:
                info = sd.query_devices(int(default_input))
                if float(info.get('max_input_channels', 0)) > 0:
                    return int(default_input)
        except Exception:
            pass

        # Fallback to first device that supports input channels.
        try:
            devices = sd.query_devices()
            for idx, info in enumerate(devices):
                if float(info.get('max_input_channels', 0)) > 0:
                    return int(idx)
        except Exception:
            return None

        return None

    def _consume_audio(self, recognizer, audio) -> None:
        assert sr is not None
        transcript = None
        languages: list[str] = []
        primary = self._recognition_language.strip() if self._recognition_language else ''
        if primary:
            languages.append(primary)
        if 'en-US' not in languages:
            languages.append('en-US')

        for lang in languages:
            try:
                transcript = recognizer.recognize_google(audio, language=lang)
                break
            except sr.UnknownValueError:
                continue
            except sr.RequestError as exc:
                self._last_error = f'Voice API error: {exc}'
                time.sleep(self._poll_sleep_s)
                return

        if not transcript:
            return

        command = normalize_voice_command(transcript)
        if command is None:
            command = '__unmapped__'

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


def normalize_voice_command(transcript: str) -> str | None:
    """Map free-form speech to canonical command tokens."""
    text = re.sub(r'[^a-z0-9\s]', ' ', transcript.lower()).strip()
    text = re.sub(r'\s+', ' ', text)
    words = set(text.split())

    if not text:
        return None

    def _has_prefix(*prefixes: str) -> bool:
        return any(any(w.startswith(p) for p in prefixes) for w in words)

    if (
        any(v in words for v in ('open', 'launch', 'start'))
        and ('brave' in words or _has_prefix('brav', 'grave') or 'browser' in words)
    ):
        return 'open_brave'

    if (
        any(v in words for v in ('open', 'launch', 'start'))
        and ('youtube' in words or 'you tube' in text or _has_prefix('youtub'))
    ):
        return 'open_youtube'

    if any(k in text for k in (
        'open brave',
        'open brave browser',
        'open browser',
        'launch brave',
        'start brave',
    )):
        return 'open_brave'

    if any(k in text for k in (
        'open apple music',
        'open music',
        'launch apple music',
        'start music',
    )):
        return 'open_apple_music'

    if any(k in text for k in (
        'open youtube',
        'launch youtube',
        'start youtube',
    )):
        return 'open_youtube'

    if any(k in text for k in (
        'close window',
        'close this window',
        'close app',
    )):
        return 'close_window'
    if (
        any(v in words for v in ('close', 'shut', 'exit'))
        and any(t in words for t in ('window', 'app', 'application'))
    ):
        return 'close_window'

    if any(k in text for k in (
        'switch tab',
        'next tab',
        'change tab',
    )):
        return 'switch_tab'
    if 'tab' in words and any(v in words for v in ('switch', 'next', 'change', 'move')):
        return 'switch_tab'

    if any(k in text for k in (
        'scroll down',
        'page down',
        'move down',
    )):
        return 'scroll_down'
    if 'down' in words and any(v in words for v in ('scroll', 'page', 'move')):
        return 'scroll_down'

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
