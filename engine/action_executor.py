"""
Module: action_executor.py
Description: Executes system actions resolved by the DecisionEngine — launches
             applications, sends media/volume keyboard events via pyautogui,
             and logs each action with a human-readable label.
Author: Pratham Chaturvedi

engine/action_executor.py - The Action Performer

Actually executes computer actions based on the gesture resolved by
the DecisionEngine:

    - Launch applications  (Brave browser, Apple Music)
    - Media control        (next / previous track, play/pause)
    - Volume control       (up / down / mute)

Uses:
    subprocess  – launch applications
    pyautogui   – send media / volume keyboard events
    os          – expand environment variables in paths

Displays a fading on-screen notification for each action executed.
"""

import os
import sys
import time
import subprocess
import webbrowser
import ctypes
import cv2
from utils.logger import log_runtime_error

try:
    import pyautogui
    pyautogui.FAILSAFE = False   # disable corner-abort for gesture control
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False
    print('[ActionExecutor] Warning: pyautogui not installed — media/volume keys disabled')


class ActionExecutor:
    """Executes system actions and shows brief on-screen feedback."""

    # Human-readable labels for each action ID
    _LABELS: dict[str, str] = {
        'open_brave':        'Launch Brave Browser',
        'open_apple_music':  'Launch Apple Music',
        'open_youtube':      'Open YouTube',
        'close_window':      'Close Window',
        'switch_tab':        'Switch Tab',
        'scroll_down':       'Scroll Down',
        'scroll_up':         'Scroll Up',
        'next_track':        'Next Track',
        'prev_track':        'Previous Track',
        'play_pause':        'Play / Pause',
        'volume_up':         'Volume Up',
        'volume_down':       'Volume Down',
        'mute':              'Mute',
        'left_click':        'Left Click',
        'right_click':       'Right Click',
        'double_click':      'Double Click',
        'seek_forward':      'Seek Forward',
        'seek_backward':     'Seek Backward',
        'switch_apps':       'Switch Apps',
    }

    # pyautogui key names for media / volume actions
    _KEY_MAP: dict[str, str] = {
        'next_track':  'nexttrack',
        'prev_track':  'prevtrack',
        'play_pause':  'playpause',
        'volume_up':   'volumeup',
        'volume_down': 'volumedown',
        'mute':        'volumemute',
    }

    _WIN_MEDIA_VK: dict[str, int] = {
        'next_track':  0xB0,
        'prev_track':  0xB1,
        'play_pause':  0xB3,
        'volume_up':   0xAF,
        'volume_down': 0xAE,
        'mute':        0xAD,
    }

    _FEEDBACK_DURATION: float = 2.5   # seconds to show on-screen notification
    _COOLDOWN:          float = 1.0   # seconds before the same action may fire again
    _GLOBAL_COOLDOWN:   float = 1.0   # minimum gap between any two actions

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._brave_path = os.path.expandvars(
            cfg.get(
                'brave_path',
                r'%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe',
            )
        )
        self._apple_music_aumid = cfg.get(
            'apple_music_aumid',
            'AppleInc.AppleMusicWin_nzyj5cx40ttqa!App',
        )

        self._last_action: str | None = None
        self._last_action_time: float = 0.0
        self._last_global_action_time: float = 0.0
        # Per-action cooldown tracking: action → timestamp of last execution
        self._last_executed: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, action: str) -> None:
        """Execute the named action, subject to per-action cooldown."""
        now = time.time()

        # Global rate-limit across all gestures/actions.
        if now - self._last_global_action_time < self._GLOBAL_COOLDOWN:
            return

        # Rate-limit: skip if this action is still within its cooldown window
        if now - self._last_executed.get(action, 0.0) < self._COOLDOWN:
            return

        self._last_global_action_time = now
        self._last_executed[action] = now
        self._last_action      = action
        self._last_action_time = now

        label = self._LABELS.get(action, action)
        print(f'  [{action}] {label}')
        print(f'  [DEBUG] ActionExecutor.execute() called with: {action}')

        try:
            if action == 'open_brave':
                self._launch(self._brave_path)

            elif action == 'open_apple_music':
                self._launch_store_app(self._apple_music_aumid)

            elif action == 'open_youtube':
                self._open_url('https://www.youtube.com')

            elif action == 'close_window':
                self._hotkey('alt', 'f4')

            elif action == 'switch_tab':
                self._hotkey('ctrl', 'tab')

            elif action == 'scroll_down':
                self._scroll(-420)

            elif action == 'scroll_up':
                self._scroll(420)

            elif action == 'left_click':
                self._click('left')

            elif action == 'right_click':
                self._click('right')

            elif action == 'double_click':
                self._double_click()

            elif action == 'seek_forward':
                self._press('right')

            elif action == 'seek_backward':
                self._press('left')

            elif action == 'switch_apps':
                self._hotkey('alt', 'tab')

            elif action in self._WIN_MEDIA_VK:
                print(f'  [DEBUG] {action} is in WIN_MEDIA_VK, calling _press_media_key()')
                self._press_media_key(action)

            elif action in self._KEY_MAP:
                self._press(self._KEY_MAP[action])

            else:
                print(f'  [ActionExecutor] Unknown action: {action}')
                log_runtime_error(f'Unknown action key: {action}')

        except Exception as exc:
            print(f'  [ActionExecutor] Error executing "{action}": {exc}')
            log_runtime_error(f'Action execution failed for {action}: {exc}')

    def display_action(self, frame):
        """Render a fading action-feedback banner at the bottom of the frame."""
        if not self._last_action:
            return frame

        elapsed = time.time() - self._last_action_time
        if elapsed > self._FEEDBACK_DURATION:
            return frame

        # Alpha fades from 1 → 0 over the display duration
        alpha = max(0.0, 1.0 - (elapsed / self._FEEDBACK_DURATION))
        label = self._LABELS.get(self._last_action, self._last_action)
        text  = f'Action: {label}'

        h, w = frame.shape[:2]
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
        x = (w - tw) // 2
        y = h - 35

        # Background bar
        overlay = frame.copy()
        cv2.rectangle(overlay, (x - 10, y - th - 8), (x + tw + 10, y + 8),
                      (20, 20, 20), -1)
        cv2.addWeighted(overlay, alpha * 0.75, frame, 1 - alpha * 0.75, 0, frame)

        # Text with fade
        intensity = int(255 * alpha)
        cv2.putText(
            frame, text, (x, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.75,
            (intensity, intensity, intensity), 2, cv2.LINE_AA,
        )
        return frame

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _launch(self, path: str) -> None:
        """Launch an application by absolute path."""
        expanded = os.path.expandvars(path)
        if os.path.exists(expanded):
            subprocess.Popen([expanded])
            print(f'  [ActionExecutor] Launched: {expanded}')
        else:
            print(f'  [ActionExecutor] Application not found: {expanded}')

    def _launch_store_app(self, aumid: str) -> None:
        """Launch a Microsoft Store app by its Application User Model ID."""
        subprocess.Popen(['explorer.exe', f'shell:AppsFolder\\{aumid}'])
        print(f'  [ActionExecutor] Launched Store app: {aumid}')

    def _press(self, key: str) -> None:
        """Send a keyboard event via pyautogui. Use only for non-media keys."""
        if _PYAUTOGUI:
            pyautogui.press(key)
        else:
            print(f'  [ActionExecutor] pyautogui unavailable — cannot press "{key}"')

    def _press_media_key(self, action: str) -> None:
        """Send a Windows media key using nircmd, keybd_event, or fallback."""
        vk = self._WIN_MEDIA_VK.get(action)
        print(f'  [ActionExecutor] _press_media_key called: action={action} vk={hex(vk) if vk else None}')
        if vk is None:
            print(f'  [ActionExecutor] ERROR: Action {action} not in WIN_MEDIA_VK')
            return
        
        # Try nircmd approach (most reliable for media control on Windows)
        if sys.platform.startswith('win'):
            nircmd_commands = {
                'mute': 'nircmd.exe muteappvolume 0 toggle',
                'volume_up': 'nircmd.exe changeappvolume 0 5',
                'volume_down': 'nircmd.exe changeappvolume 0 -5',
                'next_track': 'nircmd.exe sendkeys 176',
                'prev_track': 'nircmd.exe sendkeys 177',
                'play_pause': 'nircmd.exe sendkeys 179',
            }
            
            # First check if nircmd is available
            try:
                result = subprocess.run(
                    ['where', 'nircmd.exe'],
                    capture_output=True,
                    timeout=1,
                    check=False,
                )
                nircmd_available = result.returncode == 0
            except:
                nircmd_available = False
            
            if nircmd_available and action in nircmd_commands:
                try:
                    print(f'  [ActionExecutor] Trying nircmd for {action}')
                    result = subprocess.run(
                        nircmd_commands[action],
                        capture_output=True,
                        timeout=2,
                        check=False,
                    )
                    if result.returncode == 0 or result.returncode == 1:  # nircmd returns 1 on success sometimes
                        print(f'  [ActionExecutor] SUCCESS: Media key {action} sent via nircmd')
                        return
                except Exception as exc:
                    print(f'  [ActionExecutor] nircmd failed: {exc}')
            
            # Fallback: Try keybd_event
            try:
                print(f'  [ActionExecutor] Trying keybd_event for {action}')
                print(f'  [ActionExecutor] Sending Windows keybd_event(0x{vk:02X}, press)')
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.05)  # Add small delay between press and release
                print(f'  [ActionExecutor] Sending Windows keybd_event(0x{vk:02X}, release)')
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                print(f'  [ActionExecutor] SUCCESS: Media key {action} sent via Windows keybd_event API')
                return
            except Exception as exc:
                print(f'  [ActionExecutor] Windows keybd_event failed for {action}: {exc}')
        
        if _PYAUTOGUI:
            print(f'  [ActionExecutor] Final fallback: Sending via pyautogui.press({self._KEY_MAP.get(action, action)})')
            pyautogui.press(self._KEY_MAP.get(action, action))
        else:
            print(f'  [ActionExecutor] ERROR: No method available to trigger media key {action}')

    def _hotkey(self, *keys: str) -> None:
        """Send a keyboard shortcut via pyautogui."""
        if _PYAUTOGUI:
            pyautogui.hotkey(*keys)
        else:
            print(f'  [ActionExecutor] pyautogui unavailable — cannot trigger hotkey {keys}')

    def _scroll(self, amount: int) -> None:
        """Send a mouse-wheel scroll event via pyautogui."""
        if _PYAUTOGUI:
            pyautogui.scroll(amount)
        else:
            print(f'  [ActionExecutor] pyautogui unavailable — cannot scroll {amount}')

    def _click(self, button: str) -> None:
        """Send a mouse click via pyautogui."""
        if _PYAUTOGUI:
            pyautogui.click(button=button)
        else:
            print(f'  [ActionExecutor] pyautogui unavailable — cannot click {button}')

    def _double_click(self) -> None:
        """Send a mouse double-click via pyautogui."""
        if _PYAUTOGUI:
            pyautogui.doubleClick()
        else:
            print('  [ActionExecutor] pyautogui unavailable — cannot double-click')

    @staticmethod
    def _open_url(url: str) -> None:
        """Open a URL in the default browser."""
        webbrowser.open(url, new=2)
