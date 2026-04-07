"""
Voice command listener for MMGI multimodal control.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

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
    confidence: float = 1.0


DEFAULT_COMMAND_GROUPS: dict[str, list[str]] = {
    'open_brave': [
        'open brave',
        'open brave browser',
        'launch brave',
        'start brave',
        'open browser',
    ],
    'open_apple_music': [
        'open apple music',
        'open music',
        'launch apple music',
        'start music',
    ],
    'open_youtube': [
        'open youtube',
        'launch youtube',
        'start youtube',
    ],
    'close_window': [
        'close window',
        'close this window',
        'close app',
        'exit app',
        'shut window',
    ],
    'switch_tab': [
        'switch tab',
        'next tab',
        'change tab',
        'move tab',
    ],
    'scroll_down': [
        'scroll down',
        'go down',
        'move down',
        'page down',
    ],
    'play_song': [
        'play song',
        'play music',
        'play',
        'resume',
    ],
    'pause': [
        'pause song',
        'pause music',
        'pause',
        'stop music',
    ],
    'next_track': [
        'next track',
        'next song',
        'skip',
        'skip track',
    ],
    'previous_track': [
        'previous track',
        'previous song',
        'back track',
        'go back track',
    ],
    'volume_up': [
        'volume up',
        'increase volume',
        'raise volume',
        'louder',
    ],
    'volume_down': [
        'volume down',
        'decrease volume',
        'lower volume',
        'softer',
    ],
    'mute': [
        'mute',
        'silence',
        'mute audio',
    ],
}


def _normalize_text(raw: str) -> str:
    text = re.sub(r'[^a-z0-9\s]', ' ', raw.lower()).strip()
    return re.sub(r'\s+', ' ', text)


class VoiceCommandMapper:
    """Fast, configurable voice-command mapper with grouped phrase aliases."""

    def __init__(
        self,
        command_groups: dict[str, list[str]] | None = None,
        config_path: str | Path | None = None,
        reload_interval_s: float = 0.5,
    ) -> None:
        self._config_path = Path(config_path) if config_path is not None else None
        self._reload_interval_s = max(0.1, float(reload_interval_s))
        self._last_reload_check_ts = 0.0
        self._last_mtime: float | None = None

        self._groups = dict(DEFAULT_COMMAND_GROUPS)
        if command_groups:
            self._merge_groups(command_groups)

        self._exact_alias_to_command: dict[str, str] = {}
        self._token_entries: list[tuple[str, frozenset[str], int]] = []
        self._rebuild_indexes()

        if self._config_path is not None:
            self._reload_from_file(force=True)

    def reload_if_needed(self) -> bool:
        if self._config_path is None:
            return False
        now = time.time()
        if (now - self._last_reload_check_ts) < self._reload_interval_s:
            return False
        self._last_reload_check_ts = now
        return self._reload_from_file(force=False)

    def map_command(self, transcript: str) -> tuple[str | None, float]:
        text = _normalize_text(transcript)
        if not text:
            return None, 0.0

        if text in self._exact_alias_to_command:
            return self._exact_alias_to_command[text], 1.0

        words = set(text.split())
        if not words:
            return None, 0.0

        best_command: str | None = None
        best_score = 0.0

        # Lightweight token-subset scoring for phrase variations.
        for command, tokens, token_count in self._token_entries:
            if token_count == 0:
                continue
            overlap = len(words.intersection(tokens))
            if overlap == 0:
                continue
            score = overlap / token_count
            if score > best_score:
                best_score = score
                best_command = command

        return best_command, best_score

    def _merge_groups(self, updates: dict[str, list[str]]) -> None:
        for command, aliases in updates.items():
            if not isinstance(aliases, list):
                continue
            normalized_aliases = [a for a in aliases if isinstance(a, str) and a.strip()]
            if not normalized_aliases:
                continue
            base = self._groups.get(command, [])
            self._groups[command] = list(dict.fromkeys(base + normalized_aliases))

    def _rebuild_indexes(self) -> None:
        exact: dict[str, str] = {}
        token_entries: list[tuple[str, frozenset[str], int]] = []
        for command, aliases in self._groups.items():
            for alias in aliases:
                normalized = _normalize_text(alias)
                if not normalized:
                    continue
                exact[normalized] = command
                token_set = frozenset(normalized.split())
                token_entries.append((command, token_set, len(token_set)))

        self._exact_alias_to_command = exact
        self._token_entries = token_entries

    def _reload_from_file(self, force: bool) -> bool:
        assert self._config_path is not None
        try:
            mtime = self._config_path.stat().st_mtime
        except FileNotFoundError:
            return False

        if not force and self._last_mtime is not None and mtime == self._last_mtime:
            return False

        try:
            with open(self._config_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception:
            return False

        if not isinstance(data, dict):
            return False

        raw_groups = data.get('command_groups', {})
        groups = dict(DEFAULT_COMMAND_GROUPS)
        if isinstance(raw_groups, dict):
            for command, aliases in raw_groups.items():
                if not isinstance(command, str) or not isinstance(aliases, list):
                    continue
                valid_aliases = [a for a in aliases if isinstance(a, str) and a.strip()]
                if valid_aliases:
                    groups[command] = list(dict.fromkeys(valid_aliases))

        self._groups = groups
        self._rebuild_indexes()
        self._last_mtime = mtime
        return True


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
        confidence_threshold: float = 0.6,
        command_groups: dict[str, list[str]] | None = None,
        command_config_path: str | Path | None = None,
    ) -> None:
        self._enabled = bool(enabled)
        self._listen_timeout_s = float(listen_timeout_s)
        self._phrase_time_limit_s = float(phrase_time_limit_s)
        self._poll_sleep_s = float(poll_sleep_s)
        self._energy_threshold = int(energy_threshold)
        self._recognition_language = str(recognition_language or 'en-IN')
        self._confidence_threshold = max(0.0, min(1.0, float(confidence_threshold)))
        self._mapper = VoiceCommandMapper(
            command_groups=command_groups,
            config_path=command_config_path,
        )

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

        self._mapper.reload_if_needed()
        command, confidence = self._mapper.map_command(transcript)
        if command is None or confidence < self._confidence_threshold:
            command = '__unmapped__'

        evt = VoiceCommandEvent(
            command=command,
            transcript=transcript,
            timestamp=time.time(),
            confidence=confidence,
        )
        try:
            self._events.put_nowait(evt)
        except queue.Full:
            _ = self._events.get_nowait()
            self._events.put_nowait(evt)


def normalize_voice_command(transcript: str) -> str | None:
    """Map free-form speech to canonical command tokens."""
    mapper = VoiceCommandMapper()
    command, confidence = mapper.map_command(transcript)
    if command is None or confidence < 0.5:
        return None
    return command
