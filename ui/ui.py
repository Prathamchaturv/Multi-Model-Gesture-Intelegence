"""
Module: ui.py
Description: Consolidated PyQt6 dashboard — contains the QSS stylesheet,
             ActivityLog, Sidebar, VisionPanel, SystemPanel and MainWindow;
             wires all panels to SharedState signals for live updates.
Author: Pratham Chaturvedi

ui/ui.py - MMGI PyQt6 Dashboard (consolidated UI module)

Contains all UI components:
  - Colour tokens & global QSS  (formerly styles.py)
  - ActivityLog widget           (formerly activity_log.py)
  - Sidebar widget               (formerly sidebar.py)
  - VisionPanel widget           (formerly vision_panel.py)
  - SystemCard / ModeCard / PerformanceCard / SystemPanel  (formerly system_panel.py)
  - MainWindow                   (formerly main_window.py)

Entry point:
    from ui.ui import MainWindow
"""

from __future__ import annotations

import json
from pathlib import Path
import time

# ===========================================================================
# Colour tokens & global QSS  (was ui/styles.py)
# ===========================================================================

BG_DEEP   = '#0B1220'
BG_CARD   = '#121A2D'
BG_HOVER  = '#1A2640'
BORDER    = '#274061'
ACCENT    = '#38DDF8'
ACCENT_SOFT = '#7BE9FF'
ACTIVE    = '#33E6A8'
WARNING   = '#F7C559'
INACTIVE  = '#FF6B87'
TEXT_PRI  = '#E9F2FF'
TEXT_SEC  = '#B6C6DE'
TEXT_HINT = '#788CAB'

MODE_APP    = '#22D3EE'
MODE_MEDIA  = '#60A5FA'
MODE_SYSTEM = '#F59E0B'

GLOBAL_QSS = f"""
QMainWindow, QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT_PRI};
    font-family: "Inter", "SF Pro Text", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QScrollBar:vertical {{
    background: {BG_CARD}; width: 8px; margin: 0; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: #36507C; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_CARD}; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #36507C; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QFrame#card {{
    background-color: rgba(18, 26, 45, 0.84);
    border: 1px solid rgba(123, 233, 255, 0.14);
    border-radius: 16px;
}}
QLabel#section_title {{ color: {ACCENT}; font-size: 11px; font-weight: 600; letter-spacing: 2px; }}
QLabel#value_large   {{ color: {TEXT_PRI}; font-size: 28px; font-weight: 700; }}
QLabel#value_small   {{ color: {TEXT_SEC}; font-size: 12px; }}
QPushButton#toggle_btn {{
    background-color: {INACTIVE}; color: {BG_DEEP}; border: none; border-radius: 20px;
    padding: 8px 24px; font-size: 13px; font-weight: 700; letter-spacing: 1px;
}}
QPushButton#toggle_btn:hover {{ background-color: #ff6680; }}
QPushButton#toggle_btn[active="true"] {{ background-color: {ACTIVE}; }}
QPushButton#toggle_btn[active="true"]:hover {{ background-color: #33ffaa; }}
QPushButton#nav_btn {{
    background: transparent; color: {TEXT_SEC}; border: none; border-radius: 10px;
    padding: 10px 16px; text-align: left; font-size: 13px;
}}
QPushButton#nav_btn:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRI}; }}
QPushButton#nav_btn[selected="true"] {{
    background-color: rgba(56,221,248,0.16);
    color: {ACCENT_SOFT};
    font-weight: 700;
    border: 1px solid rgba(123,233,255,0.34);
}}
QProgressBar {{
    background-color: {BORDER}; border-radius: 4px; border: none; height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 4px; }}
QProgressBar#stability_bar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACTIVE}, stop:1 {ACCENT});
}}
QToolTip {{
    background-color: {BG_CARD}; color: {TEXT_PRI}; border: 1px solid #35527D;
    border-radius: 6px; padding: 4px 8px;
}}
"""


# ===========================================================================
# Imports for widgets
# ===========================================================================

from PyQt6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QSize, pyqtSlot, QTimer
from PyQt6.QtGui     import QIcon, QFont, QImage, QPixmap, QCloseEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QScrollArea,
    QSizePolicy, QSpacerItem, QMainWindow, QMessageBox,
    QComboBox, QStackedWidget, QLineEdit, QListWidget, QListWidgetItem,
    QCheckBox, QSlider,
)

from ui.shared_state  import SharedState
from ui.worker_thread import WorkerThread
from ui.pipeline_lifecycle import PipelineLifecycleManager
from utils.config     import Config
from core.calibration import CalibrationManager
from core.config_manager import ConfigManager
from core.adaptive_gesture_learning import (
    CustomGestureStore,
    GestureRecorder,
    GestureDataError,
)

# ---------------------------------------------------------------------------
# Gesture-map config helpers (shared across panels)
# ---------------------------------------------------------------------------

_GESTURE_MAP_PATH = Path(__file__).parent.parent / 'config' / 'gesture_map.json'
_FACE_SECURITY_PATH = Path(__file__).parent.parent / 'config' / 'face_security.json'

# Human-readable labels for action keys (mirrors ActionExecutor._LABELS)
_ACTION_DISPLAY_LABELS: dict[str, str] = {
    'open_brave':        'Open Browser',
    'open_apple_music':  'Open Music',
    'open_youtube':      'Open YouTube',
    'close_window':      'Close Window',
    'switch_tab':        'Switch Tab',
    'scroll_down':       'Scroll Down',
    'left_click':        'Left Click',
    'right_click':       'Right Click',
    'double_click':      'Double Click',
    'next_track':        'Next Track',
    'prev_track':        'Prev Track',
    'play_pause':        'Play / Pause',
    'volume_up':         'Volume Up',
    'volume_down':       'Volume Down',
    'mute':              'Mute',
    'next_mode':         'Cycle Mode',
}

_ACTION_KEY_FROM_LABEL = {v: k for k, v in _ACTION_DISPLAY_LABELS.items()}

_CUSTOM_ACTION_DISPLAY_LABELS: dict[str, str] = {
    key: label
    for key, label in _ACTION_DISPLAY_LABELS.items()
    if key != 'next_mode'
}
_CUSTOM_ACTION_KEY_FROM_LABEL = {v: k for k, v in _CUSTOM_ACTION_DISPLAY_LABELS.items()}


def _load_gesture_map() -> dict:
    """Load gesture_map.json, returning an empty dict on any error."""
    try:
        with open(_GESTURE_MAP_PATH, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _load_face_security_config() -> dict:
    defaults = {
        'enabled': True,
        'authorized_image_path': 'config/authorized_face.jpg',
        'authorized_encoding_path': 'config/authorized_face_encoding.json',
        'similarity_threshold': 0.84,
        'min_detection_confidence': 0.6,
        'eval_interval_s': 0.08,
        'away_delay_s': 2.5,
        'return_confirm_s': 0.7,
    }
    try:
        with open(_FACE_SECURITY_PATH, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            defaults.update(raw)
    except Exception:
        pass
    return defaults


def _save_face_security_config(data: dict) -> None:
    _FACE_SECURITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_FACE_SECURITY_PATH, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)


# ===========================================================================
# ActivityLog  (was ui/activity_log.py)
# ===========================================================================

MAX_EVENTS = 200

_CATEGORY_STYLE = {
    'ACTION': (ACCENT,    'rgba(56,221,248,0.13)'),
    'MODE':   (ACTIVE,    'rgba(51,230,168,0.13)'),
    'SYSTEM': (TEXT_SEC,  'rgba(182,198,222,0.13)'),
    'ERROR':  (INACTIVE,  'rgba(255,107,135,0.13)'),
    'WARNING': (WARNING,  'rgba(247,197,89,0.15)'),
}
_DEFAULT_STYLE = (TEXT_SEC, 'rgba(138,138,160,0.12)')

_CATEGORY_ICON = {
    'ACTION': '▶',
    'MODE': '◈',
    'SYSTEM': '●',
    'ERROR': '✕',
    'WARNING': '▲',
}


def _pill_colour(category: str) -> tuple[str, str]:
    return _CATEGORY_STYLE.get(category.upper(), _DEFAULT_STYLE)


class EventPill(QFrame):
    def __init__(self, timestamp: str, category: str, description: str) -> None:
        super().__init__()
        colour, bg = _pill_colour(category)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cat_key = category.upper()
        icon = _CATEGORY_ICON.get(cat_key, '•')
        self.setStyleSheet(
            f'QFrame {{ background-color: {bg}; border: 1px solid {colour}33; border-radius: 14px; }}'
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        dot = QLabel(icon)
        dot.setStyleSheet(f'color: {colour}; font-size: 10px; background: transparent; border: none;')
        cat_lbl = QLabel(category.upper())
        cat_lbl.setStyleSheet(
            f'color: {colour}; font-size: 10px; font-weight: 700; letter-spacing: 1px; background: transparent; border: none;'
        )
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(f'color: {TEXT_PRI}; font-size: 12px; background: transparent; border: none;')

        lay.addWidget(dot)
        lay.addWidget(cat_lbl)
        lay.addWidget(desc_lbl)
        self.setToolTip(f'{timestamp}  |  {category.upper()}')
        self.adjustSize()


class ActivityLog(QWidget):
    def __init__(self, state: SharedState, compact: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state  = state
        self._compact = compact
        self._count  = 0
        self._pills: list[EventPill] = []
        self._last_event_signature: tuple[str, str] | None = None
        self._last_event_ts: float = 0.0
        self._duplicate_suppression_window_s = 20.0
        self._build()
        state.log_event.connect(self._on_log_event)

    def _build(self) -> None:
        if self._compact:
            self.setFixedHeight(90)
        self.setStyleSheet(
            f'background-color: rgba(18, 26, 45, 0.65); border-top: 1px solid rgba(123,233,255,0.16);'
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 6, 20, 6)
        outer.setSpacing(4)

        title_row = QHBoxLayout()
        title = QLabel('ACTIVITY LOG')
        title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 600; letter-spacing: 2px; background: transparent; border: none;'
        )
        self._count_lbl = QLabel('0 events')
        self._count_lbl.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; background: transparent; border: none;')
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self._count_lbl)
        outer.addLayout(title_row)

        self._scroll = QScrollArea()
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        self._inner = QWidget()
        self._inner.setStyleSheet('background: transparent;')
        self._pills_lay = QVBoxLayout(self._inner)
        self._pills_lay.setContentsMargins(0, 0, 0, 0)
        self._pills_lay.setSpacing(6)
        self._pills_lay.addStretch()

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

    @pyqtSlot(str, str, str)
    def _on_log_event(self, timestamp: str, category: str, description: str) -> None:
        # Suppress rapid duplicate events that would otherwise flood the log strip.
        signature = (category.strip().upper(), description.strip())
        now = time.time()
        if (
            self._last_event_signature == signature
            and (now - self._last_event_ts) <= self._duplicate_suppression_window_s
        ):
            return
        self._last_event_signature = signature
        self._last_event_ts = now

        if len(self._pills) >= MAX_EVENTS:
            old = self._pills.pop(0)
            self._pills_lay.removeWidget(old)
            old.deleteLater()

        pill = EventPill(timestamp, category, description)
        insert_idx = self._pills_lay.count() - 1
        self._pills_lay.insertWidget(insert_idx, pill)
        self._pills.append(pill)

        self._count += 1
        self._count_lbl.setText(f'{self._count} event{"s" if self._count != 1 else ""}')
        QTimer.singleShot(30, self._scroll_bottom)

    def _scroll_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())


# ===========================================================================
# Sidebar  (was ui/sidebar.py)
# ===========================================================================

EXPANDED_W  = 220
COLLAPSED_W = 56
ANIM_MS     = 200

_TABS = [
    ('vision',   'VI', 'Vision'),
    ('gestures', 'GE', 'Gestures'),
    ('mode',     'MO', 'Modes'),
    ('logs',     'LG', 'Logs'),
    ('settings', 'ST', 'Settings'),
]


class Sidebar(QWidget):
    tab_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collapsed  = False
        self._active_tab = 'vision'
        self._nav_btns: dict[str, QPushButton] = {}
        self.setFixedWidth(EXPANDED_W)
        self._build_ui()
        self._select_tab('vision')

    def _build_ui(self) -> None:
        self.setStyleSheet(f'QWidget {{ background-color: {BG_CARD}; border-right: 1px solid {BORDER}; }}')
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet(f'background: transparent; border-bottom: 1px solid {BORDER};')
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 0, 8, 0)
        self._logo_label = QLabel('MMGI')
        self._logo_label.setStyleSheet(
            f'color: {ACCENT}; font-size: 16px; font-weight: 700; letter-spacing: 3px; border: none;'
        )
        self._collapse_btn = QPushButton('◄')
        self._collapse_btn.setFixedSize(30, 30)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setToolTip('Collapse sidebar')
        self._collapse_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_SEC}; border: none; font-size: 12px; border-radius: 6px; }}
            QPushButton:hover {{ background: {BG_HOVER}; color: {ACCENT}; }}
        """)
        self._collapse_btn.clicked.connect(self.toggle_collapse)
        h_lay.addWidget(self._logo_label)
        h_lay.addStretch()
        h_lay.addWidget(self._collapse_btn)
        root.addWidget(header)

        # Nav buttons
        nav_container = QWidget()
        nav_container.setStyleSheet('background: transparent; border: none;')
        nav_lay = QVBoxLayout(nav_container)
        nav_lay.setContentsMargins(8, 12, 8, 0)
        nav_lay.setSpacing(4)
        for tab_id, icon, label in _TABS:
            btn = QPushButton(f'{icon}  {label}')
            btn.setObjectName('nav_btn')
            btn.setFixedHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty('selected', False)
            btn.setStyleSheet(self._nav_btn_style())
            btn.clicked.connect(lambda checked, tid=tab_id: self._select_tab(tid))
            nav_lay.addWidget(btn)
            self._nav_btns[tab_id] = btn
        nav_lay.addStretch()
        root.addWidget(nav_container, stretch=1)

        # Footer
        footer = QLabel('v0.3  Smart Mode')
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFixedHeight(36)
        footer.setStyleSheet(
            f'color: {TEXT_HINT}; font-size: 11px; border-top: 1px solid {BORDER}; background: transparent;'
        )
        self._footer = footer
        root.addWidget(footer)

    def _select_tab(self, tab_id: str) -> None:
        self._active_tab = tab_id
        for tid, btn in self._nav_btns.items():
            selected = (tid == tab_id)
            btn.setStyleSheet(self._nav_btn_style(selected=selected))
        self.tab_selected.emit(tab_id)

    def toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        target_w = COLLAPSED_W if self._collapsed else EXPANDED_W
        arrow    = '►' if self._collapsed else '◄'

        anim = QPropertyAnimation(self, b'minimumWidth', self)
        anim.setDuration(ANIM_MS)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
        anim.setStartValue(self.width())
        anim.setEndValue(target_w)
        anim.start()
        self._anim = anim

        anim2 = QPropertyAnimation(self, b'maximumWidth', self)
        anim2.setDuration(ANIM_MS)
        anim2.setEasingCurve(QEasingCurve.Type.InOutQuart)
        anim2.setStartValue(self.width())
        anim2.setEndValue(target_w)
        anim2.start()
        self._anim2 = anim2

        self._collapse_btn.setText(arrow)
        self._logo_label.setVisible(not self._collapsed)
        self._footer.setVisible(not self._collapsed)
        for tab_id, icon, label in _TABS:
            btn = self._nav_btns[tab_id]
            btn.setText(icon if self._collapsed else f'{icon}  {label}')

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        if self._collapsed:
            self.toggle_collapse()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if not self._collapsed:
            self.toggle_collapse()

    @staticmethod
    def _nav_btn_style(selected: bool = False) -> str:
        if selected:
            return (
                f'QPushButton {{ background-color: rgba(34,211,238,0.14); color: {ACCENT}; font-weight: 700; '
                f'border: none; border-radius: 10px; padding: 10px 16px; text-align: left; font-size: 13px; }}'
            )
        return (
            f'QPushButton {{ background: transparent; color: {TEXT_SEC}; border: none; border-radius: 10px; '
            f'padding: 10px 16px; text-align: left; font-size: 13px; }}'
            f'QPushButton:hover {{ background-color: {BG_HOVER}; color: {TEXT_PRI}; }}'
        )


# ===========================================================================
# VisionPanel  (was ui/vision_panel.py)
# ===========================================================================

_MODE_ACCENT = {
    'App Mode':    MODE_APP,
    'Media Mode':  MODE_MEDIA,
    'System Mode': MODE_SYSTEM,
}


class VisionPanel(QWidget):
    def __init__(self, state: SharedState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._current_mode = 'App Mode'
        self._current_user_state = 'open'
        self._build_ui()
        self._connect_state()

    def _build_ui(self) -> None:
        self.setStyleSheet(f'background-color: {BG_DEEP};')
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        # ── Camera frame ──────────────────────────────────────────────
        self._cam_frame = QFrame()
        self._cam_frame.setObjectName('cam_frame')
        self._cam_frame.setMinimumHeight(240)
        self._cam_frame.setMaximumHeight(620)
        self._cam_frame.setStyleSheet(
            f'QFrame#cam_frame {{ background-color: #000000; border: 2px solid {BORDER}; border-radius: 16px; }}'
        )
        cam_lay = QVBoxLayout(self._cam_frame)
        cam_lay.setContentsMargins(8, 8, 8, 8)

        self._video_label = QLabel()
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_label.setMinimumSize(320, 180)
        self._video_label.setText('⬤  Waiting for camera…')
        self._video_label.setStyleSheet(f'color: {TEXT_HINT}; font-size: 16px; background: transparent; border: none;')
        cam_lay.addWidget(self._video_label)
        root.addWidget(self._cam_frame, stretch=2)
        root.addSpacing(10)

        # ── Mode change banner (hidden until a mode switch fires) ─────
        self._mode_banner = QLabel('')
        self._mode_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mode_banner.setFixedHeight(32)
        self._mode_banner.setStyleSheet(
            f'background-color: rgba(0,229,255,0.15); color: {ACCENT}; '
            f'border: 1px solid {ACCENT}; border-radius: 8px; '
            f'font-size: 13px; font-weight: 700; letter-spacing: 2px;'
        )
        self._mode_banner.setVisible(False)
        root.addWidget(self._mode_banner)

        self._gesture_flash = QLabel('GESTURE DETECTED')
        self._gesture_flash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gesture_flash.setFixedHeight(28)
        self._gesture_flash.setVisible(False)
        self._gesture_flash.setStyleSheet(
            f'background-color: rgba(56,221,248,0.12); color: {ACCENT_SOFT}; '
            f'border: 1px solid rgba(123,233,255,0.45); border-radius: 10px; '
            f'font-size: 11px; font-weight: 700; letter-spacing: 1px;'
        )
        root.addWidget(self._gesture_flash)

        # ── Active mode indicator buttons ─────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_btns: dict[str, QPushButton] = {}
        for mode_id, short_lbl in [('App Mode', 'APP MODE'), ('Media Mode', 'MEDIA MODE'), ('System Mode', 'SYSTEM MODE')]:
            btn = QPushButton(short_lbl)
            btn.setFixedHeight(28)
            btn.setStyleSheet(self._mode_btn_style(mode_id, active=False))
            btn.setEnabled(False)   # visual indicator only
            self._mode_btns[mode_id] = btn
            mode_row.addWidget(btn)
        # Highlight initial mode
        self._mode_btns['App Mode'].setStyleSheet(self._mode_btn_style('App Mode', active=True))
        root.addLayout(mode_row)

        # Persistent current-mode label (always visible)
        self._current_mode_label = QLabel('Current Mode: APP MODE')
        self._current_mode_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._current_mode_label.setStyleSheet(
            f'color: {MODE_APP}; font-size: 12px; font-weight: 700; letter-spacing: 1px; '
            f'background: transparent; border: none;'
        )
        root.addWidget(self._current_mode_label)

        # ── Gesture detection feedback ────────────────────────────────
        feedback_frame = QFrame()
        feedback_frame.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        fb_lay = QGridLayout(feedback_frame)
        fb_lay.setContentsMargins(14, 14, 14, 14)
        fb_lay.setHorizontalSpacing(10)
        fb_lay.setVerticalSpacing(10)

        chip_1, self._gesture_detected_val = self._make_status_chip('DETECTED GESTURE', TEXT_PRI)
        chip_2, self._action_executed_val = self._make_status_chip('FINAL ACTION', ACTIVE)
        chip_3, self._gesture_state_val = self._make_status_chip('GESTURE STATE', INACTIVE)
        chip_4, self._voice_command_val = self._make_status_chip('VOICE COMMAND', MODE_MEDIA)
        chip_5, self._activation_lock_val = self._make_status_chip('AUTH CONTROL', INACTIVE)
        chip_6, self._face_auth_val = self._make_status_chip('FACE AUTH', TEXT_SEC)
        chip_7, self._failsafe_state_val = self._make_status_chip('FAIL-SAFE STATE', ACTIVE)
        chip_8, self._failsafe_feedback_val = self._make_status_chip('FAIL-SAFE FEEDBACK', TEXT_SEC)
        chip_9, self._runtime_state_val = self._make_status_chip('RUNTIME STATE', MODE_MEDIA)

        fb_lay.addWidget(chip_1, 0, 0)
        fb_lay.addWidget(chip_2, 0, 1)
        fb_lay.addWidget(chip_3, 0, 2)
        fb_lay.addWidget(chip_4, 1, 0)
        fb_lay.addWidget(chip_5, 1, 1)
        fb_lay.addWidget(chip_6, 1, 2)
        fb_lay.addWidget(chip_7, 2, 0)
        fb_lay.addWidget(chip_8, 2, 1)
        fb_lay.addWidget(chip_9, 2, 2)
        fb_lay.setRowStretch(0, 1)
        fb_lay.setRowStretch(1, 1)
        fb_lay.setRowStretch(2, 1)
        fb_lay.setColumnStretch(0, 1)
        fb_lay.setColumnStretch(1, 1)
        fb_lay.setColumnStretch(2, 1)
        root.addWidget(feedback_frame)

        quick_controls = QFrame()
        quick_controls.setStyleSheet(
            f'QFrame {{ background: rgba(18, 26, 45, 0.84); border: 1px solid rgba(123,233,255,0.14); border-radius: 12px; }}'
        )
        qc_lay = QHBoxLayout(quick_controls)
        qc_lay.setContentsMargins(16, 8, 16, 8)
        qc_lay.setSpacing(8)

        self._face_lock_btn = QPushButton('Face Lock: ON')
        self._face_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._face_lock_btn.setStyleSheet(
            f'QPushButton {{ background: rgba(51,230,168,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE}; border-radius: 9px; padding: 6px 10px; font-size: 11px; font-weight: 700; }}'
            f'QPushButton:hover {{ background: rgba(51,230,168,0.24); }}'
        )
        self._face_lock_btn.clicked.connect(self._toggle_face_lock)

        self._reset_tracking_btn = QPushButton('Reset Tracking')
        self._reset_tracking_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_tracking_btn.setStyleSheet(
            f'QPushButton {{ background: rgba(56,221,248,0.12); color: {ACCENT}; border: 1px solid {ACCENT}; border-radius: 9px; padding: 6px 10px; font-size: 11px; font-weight: 700; }}'
            f'QPushButton:hover {{ background: rgba(56,221,248,0.24); }}'
        )
        self._reset_tracking_btn.clicked.connect(self._reset_tracking_state)

        self._gesture_btn = QPushButton('Gestures: ON')
        self._gesture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gesture_btn.setStyleSheet(
            f'QPushButton {{ background: rgba(51,230,168,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE}; border-radius: 9px; padding: 6px 10px; font-size: 11px; font-weight: 700; }}'
            f'QPushButton:hover {{ background: rgba(51,230,168,0.24); }}'
        )
        self._gesture_btn.clicked.connect(self._toggle_gestures)

        qc_lay.addWidget(self._face_lock_btn)
        qc_lay.addWidget(self._reset_tracking_btn)
        qc_lay.addWidget(self._gesture_btn)
        root.addWidget(quick_controls)

        # ── Mode-switch stability bar ─────────────────────────────────
        stab_lbl = QLabel('MODE SWITCH HOLD')
        stab_lbl.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px;')

        self._stability_bar = QProgressBar()
        self._stability_bar.setObjectName('stability_bar')
        self._stability_bar.setRange(0, 100)
        self._stability_bar.setValue(0)
        self._stability_bar.setFixedHeight(8)
        self._stability_bar.setTextVisible(False)
        self._stability_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: {BORDER}; border-radius: 4px; border: none; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACTIVE}, stop:1 {ACCENT});
                border-radius: 4px;
            }}
        """)

        root.addWidget(stab_lbl)
        root.addWidget(self._stability_bar)

        # Defer first sizing pass until layout metrics are available.
        QTimer.singleShot(0, self._sync_camera_frame_size)

    def _sync_camera_frame_size(self) -> None:
        panel_w = max(self.width(), 1)
        panel_h = max(self.height(), 1)
        window_h = max(self.window().height() if self.window() else panel_h, panel_h)

        screen = self.screen()
        screen_h = screen.availableGeometry().height() if screen else window_h

        if screen_h < 800:
            min_h, max_h = 180, 300
        elif screen_h < 1050:
            min_h, max_h = 210, 390
        else:
            min_h, max_h = 250, 500

        content_w = max(panel_w - 56, 320)
        by_aspect = int((content_w * 9) / 16) + 16
        by_panel = int(min(panel_h, window_h) * 0.40)
        target_h = max(min_h, min(max_h, min(by_aspect, by_panel)))

        self._cam_frame.setMinimumHeight(min_h)
        self._cam_frame.setMaximumHeight(max_h)
        self._cam_frame.setFixedHeight(target_h)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_camera_frame_size()

    @staticmethod
    def _mode_btn_style(mode: str, active: bool = False) -> str:
        colour = _MODE_ACCENT.get(mode, ACCENT)
        if active:
            return (
                f'QPushButton {{ background: {colour}; color: {BG_DEEP}; '
                f'border: 2px solid {colour}; border-radius: 8px; '
                f'font-size: 10px; font-weight: 800; letter-spacing: 1px; padding: 0 10px; }}'
            )
        return (
            f'QPushButton {{ background: transparent; color: {TEXT_HINT}; '
            f'border: 1px solid {BORDER}; border-radius: 8px; '
            f'font-size: 10px; letter-spacing: 1px; padding: 0 10px; }}'
        )

    @staticmethod
    def _compact_text(value: str, max_len: int = 26) -> str:
        text = (value or '').strip()
        if not text:
            return '—'
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + '…'

    @staticmethod
    def _make_status_chip(title: str, value_colour: str) -> tuple[QFrame, QLabel]:
        chip = QFrame()
        chip.setFixedHeight(76)
        chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        chip.setStyleSheet(
            f'QFrame {{ background: rgba(138,138,160,0.08); border: 1px solid {BORDER}; border-radius: 10px; }}'
        )
        lay = QVBoxLayout(chip)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(5)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f'color: {TEXT_HINT}; font-size: 10px; font-weight: 600; letter-spacing: 1px; '
            f'background: transparent; border: none;'
        )
        title_lbl.setFixedHeight(14)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        value_lbl = QLabel('—')
        value_lbl.setStyleSheet(
            f'color: {value_colour}; font-size: 11px; font-weight: 700; background: transparent; border: none;'
        )
        value_lbl.setWordWrap(False)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        value_lbl.setMinimumHeight(20)
        value_lbl.setMaximumHeight(20)
        value_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay.addWidget(title_lbl)
        lay.addWidget(value_lbl)
        return chip, value_lbl

    def _connect_state(self) -> None:
        s = self._state
        s.mode_changed.connect(self._on_mode_changed)
        s.gesture_changed.connect(self._on_gesture_changed)
        s.mode_stability_changed.connect(self._on_stability_changed)
        s.system_active_changed.connect(self._on_active_changed)
        s.action_executed.connect(self._on_action_executed)
        s.face_auth_changed.connect(self._on_face_auth_changed)
        s.voice_command_changed.connect(self._on_voice_command_changed)
        s.gesture_status_changed.connect(self._on_gesture_status_changed)
        s.adaptive_auth_feedback_changed.connect(self._on_auth_feedback_changed)
        s.user_state_changed.connect(self._on_user_state_changed)
        s.fail_safe_state_changed.connect(self._on_fail_safe_state_changed)
        s.runtime_state_changed.connect(self._on_runtime_state_changed)
        s.face_security_enabled_changed.connect(self._on_face_lock_state)
        s.gesture_control_enabled_changed.connect(self._on_gesture_control_state)

    @pyqtSlot(QImage)
    def update_frame(self, image: QImage) -> None:
        lbl_w = self._video_label.width()
        lbl_h = self._video_label.height()
        if lbl_w < 4 or lbl_h < 4:
            return
        pix = QPixmap.fromImage(image).scaled(
            lbl_w, lbl_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._video_label.setPixmap(pix)
        self._video_label.setStyleSheet('background: transparent; border: none;')

    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str) -> None:
        colour = _MODE_ACCENT.get(mode, ACCENT)
        short  = mode.replace(' Mode', '').upper() + ' MODE'

        # Flash the mode change banner for 1.8 s
        self._mode_banner.setText(f'MODE CHANGED  →  {short}')
        self._mode_banner.setStyleSheet(
            f'background-color: rgba(0,229,255,0.15); color: {colour}; '
            f'border: 2px solid {colour}; border-radius: 8px; '
            f'font-size: 13px; font-weight: 800; letter-spacing: 2px;'
        )
        self._mode_banner.setVisible(True)
        QTimer.singleShot(1800, lambda: self._mode_banner.setVisible(False))

        # Highlight the active mode button
        for m, btn in self._mode_btns.items():
            btn.setStyleSheet(self._mode_btn_style(m, active=(m == mode)))

        self._current_mode_label.setText(f'Current Mode: {short}')
        self._current_mode_label.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 700; letter-spacing: 1px; '
            f'background: transparent; border: none;'
        )

        # Update camera frame border colour
        self._cam_frame.setStyleSheet(
            f'QFrame#cam_frame {{ background-color: #000000; border: 2px solid {colour}; border-radius: 16px; }}'
        )
        self._current_mode = mode

    @pyqtSlot(str)
    def _on_gesture_changed(self, gesture: str) -> None:
        text = gesture if gesture else '—'
        self._gesture_detected_val.setText(self._compact_text(text, 18))
        self._gesture_detected_val.setToolTip(text)
        if gesture:
            self._gesture_flash.setText(f'GESTURE DETECTED  •  {self._compact_text(gesture, 18).upper()}')
            self._gesture_flash.setVisible(True)
            QTimer.singleShot(650, lambda: self._gesture_flash.setVisible(False))

    @pyqtSlot(str)
    def _on_action_executed(self, action: str) -> None:
        label = _ACTION_DISPLAY_LABELS.get(action, action)
        text = label if label else '—'
        self._action_executed_val.setText(self._compact_text(text, 18))
        self._action_executed_val.setToolTip(text)
        self._activation_lock_val.setText('Executed')
        self._activation_lock_val.setStyleSheet(
            f'color: {ACTIVE}; font-size: 12px; font-weight: 700; background: transparent; border: none;'
        )

    @pyqtSlot(str)
    def _on_voice_command_changed(self, command_text: str) -> None:
        text = command_text if command_text else '—'
        self._voice_command_val.setText(self._compact_text(text, 18))
        self._voice_command_val.setToolTip(text)

    @pyqtSlot(bool, str)
    def _on_face_auth_changed(self, authorized: bool, status_text: str) -> None:
        full = status_text if status_text else 'Face Auth: Idle'
        self._face_auth_val.setText(self._compact_text(full, 22))
        self._face_auth_val.setToolTip(full)
        neutral = 'system mode only' in full.lower()
        colour = TEXT_SEC if neutral else (ACTIVE if authorized else INACTIVE)
        self._face_auth_val.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 700; background: transparent; border: none;'
        )

    @pyqtSlot(float)
    def _on_stability_changed(self, progress: float) -> None:
        self._stability_bar.setValue(int(progress * 100))

    @pyqtSlot(str)
    def _on_gesture_status_changed(self, status: str) -> None:
        text = status if status else 'Not Detected'
        self._gesture_state_val.setText(self._compact_text(text, 18))
        self._gesture_state_val.setToolTip(text)
        status_lower = (status or '').lower()
        if status_lower == 'stable':
            colour = ACTIVE
        elif status_lower == 'disabled':
            colour = TEXT_HINT
        else:
            colour = INACTIVE
        self._gesture_state_val.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 600; background: transparent; border: none;'
        )

    @pyqtSlot(bool, str)
    def _on_activation_lock_changed(self, locked: bool, reason: str) -> None:
        text = 'LOCKED' if locked else 'READY'
        details = reason if reason else ('Actions blocked' if locked else 'Ready')
        colour = INACTIVE if locked else ACTIVE
        self._activation_lock_val.setText(text)
        self._activation_lock_val.setToolTip(details)
        self._activation_lock_val.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 700; background: transparent; border: none;'
        )

    @pyqtSlot(str)
    def _on_auth_feedback_changed(self, feedback: str) -> None:
        normalized = (feedback or '').strip() or 'Executed'
        colour = {
            'Executed': ACTIVE,
            'Stabilizing...': MODE_MEDIA,
            'Hold to Confirm': MODE_SYSTEM,
            'Access Controlled': INACTIVE,
        }.get(normalized, TEXT_SEC)
        self._activation_lock_val.setText(self._compact_text(normalized, 18))
        self._activation_lock_val.setToolTip(f'{normalized} | User State: {self._current_user_state}')
        self._activation_lock_val.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 700; background: transparent; border: none;'
        )

    @pyqtSlot(str)
    def _on_user_state_changed(self, state: str) -> None:
        self._current_user_state = (state or 'open').lower()

    @pyqtSlot(str, str)
    def _on_fail_safe_state_changed(self, state_key: str, message: str) -> None:
        state = (state_key or 'READY').upper()
        feedback = message or 'System ready'
        colour_by_state = {
            'LOW_CONFIDENCE': MODE_SYSTEM,
            'NO_FACE_DETECTED': INACTIVE,
            'AUTH_REQUIRED': INACTIVE,
            'COOLDOWN_ACTIVE': MODE_MEDIA,
            'READY': ACTIVE,
        }
        label_by_state = {
            'LOW_CONFIDENCE': 'LOW CONFIDENCE',
            'NO_FACE_DETECTED': 'NO FACE DETECTED',
            'AUTH_REQUIRED': 'AUTH REQUIRED',
            'COOLDOWN_ACTIVE': 'COOLDOWN ACTIVE',
            'READY': 'READY',
        }

        colour = colour_by_state.get(state, TEXT_SEC)
        state_label = label_by_state.get(state, state)

        self._failsafe_state_val.setText(state_label)
        self._failsafe_state_val.setToolTip(feedback)
        self._failsafe_state_val.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 700; background: transparent; border: none;'
        )

        self._failsafe_feedback_val.setText(self._compact_text(feedback, 30))
        self._failsafe_feedback_val.setToolTip(feedback)
        self._failsafe_feedback_val.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 600; background: transparent; border: none;'
        )

    @pyqtSlot(str, str)
    def _on_runtime_state_changed(self, state: str, reason: str) -> None:
        runtime_state = (state or 'PAUSED').upper()
        colour = {
            'RUNNING': ACTIVE,
            'PAUSED': MODE_MEDIA,
            'ERROR': INACTIVE,
        }.get(runtime_state, TEXT_SEC)
        self._runtime_state_val.setText(runtime_state)
        self._runtime_state_val.setToolTip(reason or runtime_state)
        self._runtime_state_val.setStyleSheet(
            f'color: {colour}; font-size: 12px; font-weight: 700; background: transparent; border: none;'
        )

    @pyqtSlot(bool)
    def _on_active_changed(self, active: bool) -> None:
        colour = _MODE_ACCENT.get(self._current_mode, ACCENT) if active else BORDER
        self._cam_frame.setStyleSheet(
            f'QFrame#cam_frame {{ background-color: #000000; border: 2px solid {colour}; border-radius: 16px; }}'
        )

    def _toggle_face_lock(self) -> None:
        enabled = not self._state.face_security_enabled
        self._state.set_face_security_enabled(enabled)

    def _toggle_gestures(self) -> None:
        enabled = not self._state.gesture_control_enabled
        self._state.set_gesture_control_enabled(enabled)

    def _reset_tracking_state(self) -> None:
        self._state.set_mode_stability(0.0)
        self._state.emit_log(time.strftime('%H:%M:%S'), 'SYSTEM', 'Tracking state reset from dashboard control')

    @pyqtSlot(bool)
    def _on_face_lock_state(self, enabled: bool) -> None:
        self._face_lock_btn.setText('Face Lock: ON' if enabled else 'Face Lock: OFF')
        if enabled:
            self._face_lock_btn.setStyleSheet(
                f'QPushButton {{ background: rgba(51,230,168,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE}; border-radius: 9px; padding: 6px 10px; font-size: 11px; font-weight: 700; }}'
                f'QPushButton:hover {{ background: rgba(51,230,168,0.24); }}'
            )
        else:
            self._face_lock_btn.setStyleSheet(
                f'QPushButton {{ background: rgba(255,107,135,0.12); color: {INACTIVE}; border: 1px solid {INACTIVE}; border-radius: 9px; padding: 6px 10px; font-size: 11px; font-weight: 700; }}'
                f'QPushButton:hover {{ background: rgba(255,107,135,0.24); }}'
            )

    @pyqtSlot(bool)
    def _on_gesture_control_state(self, enabled: bool) -> None:
        self._gesture_btn.setText('Gestures: ON' if enabled else 'Gestures: OFF')
        if enabled:
            self._gesture_btn.setStyleSheet(
                f'QPushButton {{ background: rgba(51,230,168,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE}; border-radius: 9px; padding: 6px 10px; font-size: 11px; font-weight: 700; }}'
                f'QPushButton:hover {{ background: rgba(51,230,168,0.24); }}'
            )
        else:
            self._gesture_btn.setStyleSheet(
                f'QPushButton {{ background: rgba(255,107,135,0.12); color: {INACTIVE}; border: 1px solid {INACTIVE}; border-radius: 9px; padding: 6px 10px; font-size: 11px; font-weight: 700; }}'
                f'QPushButton:hover {{ background: rgba(255,107,135,0.24); }}'
            )


# ===========================================================================
# SystemPanel cards  (was ui/system_panel.py)
# ===========================================================================

_MODE_COLOUR = {
    'App Mode':    MODE_APP,
    'Media Mode':  MODE_MEDIA,
    'System Mode': MODE_SYSTEM,
}

_GESTURE_INSTRUCTIONS: dict[str, list[tuple[str, str]]] = {
    'App Mode': [
        ('One Finger',  'Open Browser'),
        ('Two Fingers', 'Open Music'),
    ],
    'Media Mode': [
        ('One Finger',  'Volume Up'),
        ('Two Fingers', 'Volume Down'),
        ('4 Fingers',   'Play / Pause'),
        ('Thumbs Up',   'Mute / Unmute'),
    ],
    'System Mode': [],
}

_SWITCH_INSTRUCTIONS = [
    ('3 Fingers  → 1 s', 'Cycle Mode'),
]


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f'color: {BORDER}; background: {BORDER}; border: none; max-height: 1px;')
    return line


def _card(title: str) -> tuple[QFrame, QLabel, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName('card')
    frame.setStyleSheet(
        f'QFrame#card {{ background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(10)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        f'color: {ACCENT}; font-size: 10px; font-weight: 600; letter-spacing: 2px; background: transparent; border: none;'
    )
    lay.addWidget(title_lbl)
    return frame, title_lbl, lay


def _instr_row(left: str, right: str, left_colour: str, right_colour: str) -> QWidget:
    w = QWidget()
    w.setStyleSheet('background: transparent;')
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lbl_l = QLabel(left)
    lbl_l.setStyleSheet(f'color: {left_colour}; font-size: 12px; background: transparent; border: none;')
    lbl_r = QLabel(right)
    lbl_r.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lbl_r.setStyleSheet(f'color: {right_colour}; font-size: 12px; font-weight: 600; background: transparent; border: none;')
    lay.addWidget(lbl_l)
    lay.addStretch()
    lay.addWidget(lbl_r)
    return w


class SystemCard(QFrame):
    def __init__(self, state: SharedState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._build()
        state.system_active_changed.connect(self._on_active)
        state.face_auth_changed.connect(self._on_face_auth)

    def _build(self) -> None:
        self.setObjectName('card')
        self.setStyleSheet(
            f'QFrame#card {{ background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        title = QLabel('SYSTEM')
        title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 600; letter-spacing: 2px; background: transparent; border: none;'
        )
        lay.addWidget(title)
        lay.addWidget(_divider())

        badge_row = QHBoxLayout()
        self._dot = QLabel('●')
        self._dot.setStyleSheet(f'color: {INACTIVE}; font-size: 16px; background: transparent; border: none;')
        self._status_lbl = QLabel('INACTIVE')
        self._status_lbl.setStyleSheet(
            f'color: {INACTIVE}; font-size: 13px; font-weight: 600; background: transparent; border: none;'
        )
        badge_row.addWidget(self._dot)
        badge_row.addWidget(self._status_lbl)
        badge_row.addStretch()
        lay.addLayout(badge_row)

        self._toggle_btn = QPushButton('SYSTEM  OFF')
        self._toggle_btn.setObjectName('toggle_btn')
        self._toggle_btn.setFixedHeight(40)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setProperty('active', False)
        self._toggle_btn.setStyleSheet(self._btn_style(False))
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        lay.addWidget(self._toggle_btn)

        hint = QLabel('Show Open Palm 2 s to activate')
        hint.setWordWrap(True)
        hint.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px; background: transparent; border: none;')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)

        self._auth_lbl = QLabel('Face Auth: Idle (System Mode Only)')
        self._auth_lbl.setWordWrap(True)
        self._auth_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._auth_lbl.setStyleSheet(
            f'color: {TEXT_HINT}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
        )
        lay.addWidget(self._auth_lbl)

    @pyqtSlot(bool)
    def _on_active(self, active: bool) -> None:
        if active:
            self._dot.setStyleSheet(f'color: {ACTIVE}; font-size: 16px; background: transparent; border: none;')
            self._status_lbl.setText('ACTIVE')
            self._status_lbl.setStyleSheet(f'color: {ACTIVE}; font-size: 13px; font-weight: 600; background: transparent; border: none;')
            self._toggle_btn.setText('SYSTEM  ON')
            self._toggle_btn.setStyleSheet(self._btn_style(True))
        else:
            self._dot.setStyleSheet(f'color: {INACTIVE}; font-size: 16px; background: transparent; border: none;')
            self._status_lbl.setText('INACTIVE')
            self._status_lbl.setStyleSheet(f'color: {INACTIVE}; font-size: 13px; font-weight: 600; background: transparent; border: none;')
            self._toggle_btn.setText('SYSTEM  OFF')
            self._toggle_btn.setStyleSheet(self._btn_style(False))

    def _on_toggle_clicked(self) -> None:
        pass  # Visual feedback only

    @pyqtSlot(bool, str)
    def _on_face_auth(self, authorized: bool, status_text: str) -> None:
        text = status_text if status_text else 'Face Auth: Idle (System Mode Only)'
        neutral = 'system mode only' in text.lower()
        colour = TEXT_HINT if neutral else (ACTIVE if authorized else INACTIVE)
        self._auth_lbl.setText(text)
        self._auth_lbl.setStyleSheet(
            f'color: {colour}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
        )

    @staticmethod
    def _btn_style(active: bool) -> str:
        bg  = ACTIVE   if active else INACTIVE
        hov = '#33ffaa' if active else '#ff6680'
        return (
            f'QPushButton {{ background-color: {bg}; color: #0F0F14; border: none; border-radius: 20px; '
            f'padding: 8px 24px; font-size: 13px; font-weight: 700; letter-spacing: 1px; }}'
            f'QPushButton:hover {{ background-color: {hov}; }}'
        )


class ModeCard(QFrame):
    def __init__(self, state: SharedState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._build()
        state.mode_changed.connect(self._on_mode_changed)

    def _build(self) -> None:
        self.setObjectName('card')
        self.setStyleSheet(
            f'QFrame#card {{ background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(16, 14, 16, 16)
        self._lay.setSpacing(8)

        # Title row: 'MODE' label + current mode name
        title_row = QHBoxLayout()
        title_lbl = QLabel('MODE')
        title_lbl.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 600; letter-spacing: 2px; background: transparent; border: none;'
        )
        self._mode_name = QLabel('APP MODE')
        self._mode_name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._mode_name.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._mode_name.setStyleSheet(
            f'color: {MODE_APP}; font-size: 13px; font-weight: 700; background: transparent; border: none;'
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._mode_name)
        self._lay.addLayout(title_row)
        self._lay.addWidget(_divider())

        # Gesture–action instruction grid
        self._instr_container = QWidget()
        self._instr_container.setStyleSheet('background: transparent;')
        self._instr_lay = QGridLayout(self._instr_container)
        self._instr_lay.setContentsMargins(0, 2, 0, 2)
        self._instr_lay.setHorizontalSpacing(8)
        self._instr_lay.setVerticalSpacing(5)
        self._instr_lay.setColumnStretch(0, 3)
        self._instr_lay.setColumnStretch(1, 2)
        self._lay.addWidget(self._instr_container)

        self._lay.addWidget(_divider())

        switch_title = QLabel('SWITCH MODE')
        switch_title.setStyleSheet(
            f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;'
        )
        self._lay.addWidget(switch_title)
        for hold, target in _SWITCH_INSTRUCTIONS:
            row = _instr_row(hold, target, TEXT_HINT, TEXT_SEC)
            self._lay.addWidget(row)

        self._build_instructions('App Mode')

    def _build_instructions(self, mode: str) -> None:
        while self._instr_lay.count():
            item = self._instr_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Load dynamically from gesture_map.json
        data = _load_gesture_map()
        mode_gestures = data.get(mode, {})
        instructions = [
            (gesture, _ACTION_DISPLAY_LABELS.get(action, action))
            for gesture, action in mode_gestures.items()
        ]
        for r, (gesture, action_lbl) in enumerate(instructions):
            lbl_l = QLabel(gesture)
            lbl_l.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl_l.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
            lbl_l.setWordWrap(True)
            lbl_r = QLabel(action_lbl)
            lbl_r.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_r.setStyleSheet(f'color: {ACCENT}; font-size: 11px; font-weight: 600; background: transparent; border: none;')
            lbl_r.setWordWrap(True)
            self._instr_lay.addWidget(lbl_l, r, 0)
            self._instr_lay.addWidget(lbl_r, r, 1)
        if not instructions:
            ph = QLabel('No gestures configured')
            ph.setWordWrap(True)
            ph.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px; font-style: italic; background: transparent; border: none;')
            self._instr_lay.addWidget(ph, 0, 0, 1, 2)

    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str) -> None:
        colour = _MODE_COLOUR.get(mode, ACCENT)
        short  = mode.replace(' Mode', '').upper() + ' MODE'
        self._mode_name.setText(short)
        self._mode_name.setStyleSheet(
            f'color: {colour}; font-size: 13px; font-weight: 700; background: transparent; border: none;'
        )
        self._build_instructions(mode)

    def refresh_current_mode(self) -> None:
        """Refresh rows from gesture_map.json for whichever mode is currently active."""
        self._build_instructions(self._state.current_mode)


class PerformanceCard(QFrame):
    def __init__(self, state: SharedState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._build()
        state.fps_changed.connect(self._on_fps)
        state.latency_changed.connect(self._on_latency)
        state.volume_changed.connect(self._on_volume)
        state.confidence_changed.connect(self._on_confidence)
        state.cursor_sensitivity_changed.connect(self._on_cursor_sensitivity)
        state.metrics_changed.connect(self._on_metrics)

    def _build(self) -> None:
        self.setObjectName('card')
        self.setStyleSheet(
            f'QFrame#card {{ background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        title = QLabel('PERFORMANCE')
        title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 600; letter-spacing: 2px; background: transparent; border: none;'
        )
        lay.addWidget(title)

        metrics_w = QWidget()
        metrics_w.setStyleSheet('background: transparent;')
        metrics_grid = QGridLayout(metrics_w)
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setHorizontalSpacing(16)
        metrics_grid.setVerticalSpacing(2)

        fps_title = QLabel('FPS')
        fps_title.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;')
        self._fps_val = QLabel('—')
        self._fps_val.setStyleSheet(f'color: {TEXT_PRI}; font-size: 15px; font-weight: 700; background: transparent; border: none;')

        lat_title = QLabel('LATENCY')
        lat_title.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;')
        self._latency_val = QLabel('—')
        self._latency_val.setStyleSheet(f'color: {TEXT_PRI}; font-size: 15px; font-weight: 700; background: transparent; border: none;')

        metrics_grid.addWidget(fps_title,         0, 0)
        metrics_grid.addWidget(self._fps_val,     1, 0)
        metrics_grid.addWidget(lat_title,         0, 1)
        metrics_grid.addWidget(self._latency_val, 1, 1)
        metrics_grid.setColumnStretch(0, 1)
        metrics_grid.setColumnStretch(1, 1)
        lay.addWidget(metrics_w)

        lay.addWidget(_divider())

        vol_row = QHBoxLayout()
        vol_title = QLabel('VOLUME')
        vol_title.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;')
        self._vol_pct = QLabel('50 %')
        self._vol_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._vol_pct.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        vol_row.addWidget(vol_title)
        vol_row.addStretch()
        vol_row.addWidget(self._vol_pct)
        lay.addLayout(vol_row)

        self._vol_bar = QProgressBar()
        self._vol_bar.setRange(0, 100)
        self._vol_bar.setValue(50)
        self._vol_bar.setFixedHeight(6)
        self._vol_bar.setTextVisible(False)
        self._vol_bar.setStyleSheet(f"""
            QProgressBar {{ background: {BORDER}; border-radius: 3px; border: none; }}
            QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
        """)
        lay.addWidget(self._vol_bar)

        lay.addWidget(_divider())

        conf_row = QHBoxLayout()
        conf_title = QLabel('CONFIDENCE')
        conf_title.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;')
        self._conf_pct = QLabel('— %')
        self._conf_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._conf_pct.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        conf_row.addWidget(conf_title)
        conf_row.addStretch()
        conf_row.addWidget(self._conf_pct)
        lay.addLayout(conf_row)

        self._conf_bar = QProgressBar()
        self._conf_bar.setRange(0, 100)
        self._conf_bar.setValue(0)
        self._conf_bar.setFixedHeight(6)
        self._conf_bar.setTextVisible(False)
        self._conf_bar.setStyleSheet(f"""
            QProgressBar {{ background: {BORDER}; border-radius: 3px; border: none; }}
            QProgressBar::chunk {{ background: {ACTIVE}; border-radius: 3px; }}
        """)
        lay.addWidget(self._conf_bar)

        lay.addWidget(_divider())

        self._cursor_lbl = QLabel('Cursor Sensitivity: 1.00x')
        self._cursor_lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        lay.addWidget(self._cursor_lbl)

        self._metrics_lbl = QLabel('Acc: 0.0%   False Activations: 0.0%   Mode/min: 0')
        self._metrics_lbl.setWordWrap(True)
        self._metrics_lbl.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px; background: transparent; border: none;')
        lay.addWidget(self._metrics_lbl)

    @pyqtSlot(float)
    def _on_fps(self, fps: float) -> None:
        self._fps_val.setText(f'{fps:.0f}')

    @pyqtSlot(float)
    def _on_latency(self, ms: float) -> None:
        self._latency_val.setText(f'{ms:.0f} ms')

    @pyqtSlot(int)
    def _on_volume(self, pct: int) -> None:
        self._vol_pct.setText(f'{pct} %')
        self._vol_bar.setValue(pct)

    @pyqtSlot(float)
    def _on_confidence(self, conf: float) -> None:
        pct = int(conf * 100)
        self._conf_pct.setText(f'{pct} %')
        self._conf_bar.setValue(pct)

    @pyqtSlot(float)
    def _on_cursor_sensitivity(self, value: float) -> None:
        self._cursor_lbl.setText(f'Cursor Sensitivity: {value:.2f}x')

    @pyqtSlot(dict)
    def _on_metrics(self, payload: dict) -> None:
        acc = float(payload.get('gesture_accuracy_pct', 0.0))
        false_rate = float(payload.get('false_activation_rate_pct', 0.0))
        mode_rate = float(payload.get('mode_switches_per_min', 0.0))
        self._metrics_lbl.setText(
            f'Acc: {acc:.1f}%   False Activations: {false_rate:.1f}%   Mode/min: {mode_rate:.0f}'
        )


# ===========================================================================
# GestureGuideCard  — right-panel card showing all mappings dynamically
# ===========================================================================

class GestureGuideCard(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build()
        self._load_guide()

    def _build(self) -> None:
        self.setObjectName('card')
        self.setStyleSheet(
            f'QFrame#card {{ background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        title = QLabel('GESTURE GUIDE')
        title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 600; letter-spacing: 2px; background: transparent; border: none;'
        )
        lay.addWidget(title)
        lay.addWidget(_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')
        scroll.setMinimumHeight(80)

        self._inner = QWidget()
        self._inner.setStyleSheet('background: transparent;')
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(0, 0, 4, 0)
        self._inner_lay.setSpacing(4)

        scroll.setWidget(self._inner)
        lay.addWidget(scroll, stretch=1)

    def _load_guide(self) -> None:
        while self._inner_lay.count():
            item = self._inner_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = _load_gesture_map()
        modes_to_show = ['App Mode', 'Media Mode', 'System Mode']
        first = True
        for mode in modes_to_show:
            gestures = data.get(mode, {})
            if mode == 'System Mode' and not gestures:
                gestures = {'Voice Command': 'Voice Command'}
            if not gestures:
                continue
            colour = _MODE_COLOUR.get(mode, ACCENT)

            if not first:
                self._inner_lay.addWidget(_divider())
            first = False

            mode_lbl = QLabel(mode.upper())
            mode_lbl.setStyleSheet(
                f'color: {colour}; font-size: 9px; font-weight: 700; letter-spacing: 1px; '
                f'background: transparent; border: none; padding-top: 2px;'
            )
            self._inner_lay.addWidget(mode_lbl)

            # Two-column grid: Gesture | Action
            grid_w = QWidget()
            grid_w.setStyleSheet('background: transparent;')
            grid = QGridLayout(grid_w)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(4)
            grid.setColumnStretch(0, 3)
            grid.setColumnStretch(1, 2)

            for r, (gesture, action) in enumerate(gestures.items()):
                action_label = _ACTION_DISPLAY_LABELS.get(action, action)
                lbl_g = QLabel(gesture)
                lbl_g.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                lbl_g.setWordWrap(True)
                lbl_g.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
                lbl_a = QLabel(action_label)
                lbl_a.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                lbl_a.setWordWrap(True)
                lbl_a.setStyleSheet(f'color: {ACCENT}; font-size: 11px; font-weight: 600; background: transparent; border: none;')
                grid.addWidget(lbl_g, r, 0)
                grid.addWidget(lbl_a, r, 1)

            self._inner_lay.addWidget(grid_w)

        self._inner_lay.addStretch()

    def refresh(self) -> None:
        """Reload content from gesture_map.json."""
        self._load_guide()


# ===========================================================================
# GestureMapPanel — full Gestures tab for editing gesture→action mappings
# ===========================================================================

class GestureMapPanel(QWidget):
    mapping_changed = pyqtSignal()   # emitted after any mapping is saved
    _TRAIN_SECTION_LABEL = 'Adaptive Gesture Training'
    _SAVED_SECTION_LABEL = 'Saved Custom Gestures'

    def __init__(self, state: SharedState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        cfg = Config()
        store_path = str(cfg.get('adaptive_gesture.store_path') or 'config/custom_gestures.json')
        resolved_store_path = Path(store_path)
        if not resolved_store_path.is_absolute():
            resolved_store_path = Path(__file__).parent.parent / resolved_store_path

        self._custom_store = CustomGestureStore(resolved_store_path)
        self._recorder = GestureRecorder(target_frames=int(cfg.get('adaptive_gesture.training_frames') or 25))
        self._training_active = False
        self._training_name = ''
        self._training_action = ''

        self._build_ui()
        self._load_map()
        self._refresh_custom_gestures()
        self._state.landmarks_changed.connect(self._on_landmarks)

    def _build_ui(self) -> None:
        self.setStyleSheet(f'background-color: {BG_DEEP};')
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(8)

        # Header ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel('GESTURE MAPPING')
        title.setStyleSheet(
            f'color: {ACCENT}; font-size: 16px; font-weight: 700; letter-spacing: 2px;'
        )
        subtitle = QLabel('Gesture | Assigned Action | Edit. Click Edit to choose a new action and save.')
        subtitle.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px;')
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(subtitle)
        root.addLayout(hdr)

        # Adaptive training panel
        train_card = QFrame()
        train_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        train_card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}'
        )
        train_lay = QVBoxLayout(train_card)
        train_lay.setContentsMargins(10, 8, 10, 8)
        train_lay.setSpacing(6)

        self._train_toggle_btn = QPushButton()
        self._train_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._train_toggle_btn.setStyleSheet(
            f'QPushButton {{ '
            f'background: transparent; color: {ACTIVE}; border: none; '
            f'font-size: 12px; font-weight: 700; letter-spacing: 1px; text-align: left; padding: 4px 6px; }}'
            f'QPushButton:hover {{ color: {ACCENT}; }}'
        )
        self._train_toggle_btn.clicked.connect(
            lambda: self._toggle_section(self._train_content, self._train_toggle_btn, self._TRAIN_SECTION_LABEL)
        )
        train_lay.addWidget(self._train_toggle_btn)

        self._train_content = QWidget()
        train_content_lay = QVBoxLayout(self._train_content)
        train_content_lay.setContentsMargins(8, 2, 8, 6)
        train_content_lay.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._gesture_name_input = QLineEdit()
        self._gesture_name_input.setPlaceholderText('Gesture name')
        self._gesture_name_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_HOVER}; color: {TEXT_PRI}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 6px 10px; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)

        self._custom_action_combo = QComboBox()
        self._custom_action_combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG_HOVER}; color: {TEXT_PRI}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 6px 10px; font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; padding-right: 6px; }}
            QComboBox:hover {{ border-color: {ACCENT}; }}
            QComboBox QAbstractItemView {{
                background: {BG_CARD}; border: 1px solid {BORDER}; color: {TEXT_PRI};
                selection-background-color: rgba(0,229,255,0.2);
            }}
        """)
        for action_label in _CUSTOM_ACTION_DISPLAY_LABELS.values():
            self._custom_action_combo.addItem(action_label)

        self._train_btn = QPushButton('Train New Gesture')
        self._train_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._train_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,255,136,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE};
                border-radius: 6px; font-size: 12px; font-weight: 700; padding: 6px 10px;
            }}
            QPushButton:hover {{ background: rgba(0,255,136,0.24); }}
        """)
        self._train_btn.clicked.connect(self._on_train_clicked)

        row.addWidget(self._gesture_name_input, stretch=2)
        row.addWidget(self._custom_action_combo, stretch=2)
        row.addWidget(self._train_btn)
        train_content_lay.addLayout(row)

        self._train_progress = QProgressBar()
        self._train_progress.setRange(0, self._recorder.target_frames)
        self._train_progress.setValue(0)
        self._train_progress.setTextVisible(True)
        self._train_progress.setFormat('Frames: %v/%m')
        self._train_progress.setStyleSheet(f"""
            QProgressBar {{
                background: {BORDER}; color: {TEXT_PRI}; border-radius: 5px; border: none;
                height: 18px; text-align: center;
            }}
            QProgressBar::chunk {{ background: {ACTIVE}; border-radius: 5px; }}
        """)
        train_content_lay.addWidget(self._train_progress)

        self._train_status = QLabel('Enter name and action, then click Train New Gesture.')
        self._train_status.setFixedHeight(18)
        self._train_status.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px;')
        train_content_lay.addWidget(self._train_status)

        train_lay.addWidget(self._train_content)

        root.addWidget(train_card)

        # Custom gesture list
        list_card = QFrame()
        list_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        list_card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}'
        )
        list_lay = QVBoxLayout(list_card)
        list_lay.setContentsMargins(10, 8, 10, 8)
        list_lay.setSpacing(6)

        self._list_toggle_btn = QPushButton()
        self._list_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._list_toggle_btn.setStyleSheet(
            f'QPushButton {{ '
            f'background: transparent; color: {ACCENT}; border: none; '
            f'font-size: 12px; font-weight: 700; letter-spacing: 1px; text-align: left; padding: 4px 6px; }}'
            f'QPushButton:hover {{ color: {TEXT_PRI}; }}'
        )
        self._list_toggle_btn.clicked.connect(
            lambda: self._toggle_section(self._list_content, self._list_toggle_btn, self._SAVED_SECTION_LABEL)
        )
        list_lay.addWidget(self._list_toggle_btn)

        self._list_content = QWidget()
        list_content_lay = QVBoxLayout(self._list_content)
        list_content_lay.setContentsMargins(8, 2, 8, 6)
        list_content_lay.setSpacing(8)

        list_title_row = QHBoxLayout()
        self._delete_custom_btn = QPushButton('Delete Selected')
        self._delete_custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_custom_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,68,102,0.12); color: {INACTIVE}; border: 1px solid {INACTIVE};
                border-radius: 6px; font-size: 11px; font-weight: 700; padding: 5px 10px;
            }}
            QPushButton:hover {{ background: rgba(255,68,102,0.24); }}
        """)
        self._delete_custom_btn.clicked.connect(self._delete_selected_custom)
        list_title_row.addStretch()
        list_title_row.addWidget(self._delete_custom_btn)
        list_content_lay.addLayout(list_title_row)

        self._custom_list = QListWidget()
        self._custom_list.setMinimumHeight(88)
        self._custom_list.setMaximumHeight(126)
        self._custom_list.setStyleSheet(f"""
            QListWidget {{
                background: {BG_HOVER}; color: {TEXT_PRI}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 4px;
            }}
            QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
            QListWidget::item:selected {{ background: rgba(0,229,255,0.2); color: {ACCENT}; }}
        """)
        list_content_lay.addWidget(self._custom_list)

        list_lay.addWidget(self._list_content)

        root.addWidget(list_card)

        self._set_section_collapsed(self._train_content, self._train_toggle_btn, True, self._TRAIN_SECTION_LABEL)
        self._set_section_collapsed(self._list_content, self._list_toggle_btn, True, self._SAVED_SECTION_LABEL)

        # Column header row
        header_row = QFrame()
        header_row.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}'
        )
        header_lay = QHBoxLayout(header_row)
        header_lay.setContentsMargins(16, 8, 12, 8)
        header_lay.setSpacing(12)
        for text, width in [('Gesture', 180), ('Assigned Action', 220), ('Edit', 80)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(width)
            lbl.setStyleSheet(
                f'color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px; '
                f'background: transparent; border: none;'
            )
            header_lay.addWidget(lbl)
        header_lay.addStretch()
        root.addWidget(header_row)

        # Scrollable table area ─────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        self._container = QWidget()
        self._container.setStyleSheet('background: transparent;')
        self._rows_lay = QVBoxLayout(self._container)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(6)
        self._rows_lay.addStretch()

        scroll.setWidget(self._container)
        root.addWidget(scroll, stretch=1)

    def _load_map(self) -> None:
        """Rebuild the table rows from gesture_map.json."""
        # Clear all rows (leave the trailing stretch)
        while self._rows_lay.count() > 1:
            item = self._rows_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = _load_gesture_map()
        modes_to_show = ['App Mode', 'Media Mode', 'System Mode']

        for mode in modes_to_show:
            mode_gestures = dict(data.get(mode, {}))
            colour = _MODE_COLOUR.get(mode, ACCENT)

            # Mode section header
            mode_hdr = QLabel(mode.upper())
            mode_hdr.setStyleSheet(
                f'color: {colour}; font-size: 11px; font-weight: 700; letter-spacing: 2px; '
                f'background: transparent; padding: 10px 0 4px 0;'
            )
            self._rows_lay.insertWidget(self._rows_lay.count() - 1, mode_hdr)

            if not mode_gestures:
                empty = QLabel('No gestures configured for this mode.')
                empty.setStyleSheet(
                    f'color: {TEXT_HINT}; font-size: 11px; font-style: italic; background: transparent; padding: 2px 4px;'
                )
                self._rows_lay.insertWidget(self._rows_lay.count() - 1, empty)
            else:
                for gesture, action in mode_gestures.items():
                    row_widget = self._build_row(mode, gesture, action)
                    self._rows_lay.insertWidget(self._rows_lay.count() - 1, row_widget)

    def _build_row(self, mode: str, gesture: str, current_action: str) -> QWidget:
        row = QFrame()
        row.setMinimumHeight(50)
        row.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}'
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 8, 12, 8)
        lay.setSpacing(12)

        gesture_lbl = QLabel(gesture)
        gesture_lbl.setFixedWidth(180)
        gesture_lbl.setWordWrap(True)
        gesture_lbl.setStyleSheet(
            f'color: {TEXT_PRI}; font-size: 13px; background: transparent; border: none;'
        )

        action_lbl = QLabel(_ACTION_DISPLAY_LABELS.get(current_action, current_action))
        action_lbl.setFixedWidth(220)
        action_lbl.setWordWrap(True)
        action_lbl.setStyleSheet(
            f'color: {TEXT_SEC}; font-size: 12px; background: transparent; border: none;'
        )

        combo = QComboBox()
        combo.setFixedWidth(220)
        combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG_HOVER}; color: {TEXT_PRI}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 4px 10px; font-size: 12px; min-width: 180px;
            }}
            QComboBox::drop-down {{ border: none; padding-right: 6px; }}
            QComboBox:hover {{ border-color: {ACCENT}; }}
            QComboBox QAbstractItemView {{
                background: {BG_CARD}; border: 1px solid {BORDER}; color: {TEXT_PRI};
                selection-background-color: rgba(0,229,255,0.2);
            }}
        """)
        for display_name in _ACTION_DISPLAY_LABELS.values():
            combo.addItem(display_name)
        current_display = _ACTION_DISPLAY_LABELS.get(current_action, current_action)
        idx = combo.findText(current_display)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setVisible(False)

        saved_lbl = QLabel('✓ Saved')
        saved_lbl.setStyleSheet(
            f'color: {ACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
        )
        saved_lbl.setVisible(False)

        edit_btn = QPushButton('Edit')
        edit_btn.setFixedSize(64, 30)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,229,255,0.12); color: {ACCENT}; border: 1px solid {ACCENT};
                border-radius: 6px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(0,229,255,0.28); }}
        """)

        save_btn = QPushButton('Save')
        save_btn.setFixedSize(64, 30)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,255,136,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE};
                border-radius: 6px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(0,255,136,0.24); }}
        """)
        save_btn.setVisible(False)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.setFixedSize(68, 30)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC}; border: 1px solid {BORDER};
                border-radius: 6px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ border-color: {TEXT_PRI}; color: {TEXT_PRI}; }}
        """)
        cancel_btn.setVisible(False)

        def _start_edit():
            action_lbl.setVisible(False)
            combo.setVisible(True)
            edit_btn.setVisible(False)
            save_btn.setVisible(True)
            cancel_btn.setVisible(True)

        def _cancel_edit():
            idx_local = combo.findText(action_lbl.text())
            if idx_local >= 0:
                combo.setCurrentIndex(idx_local)
            combo.setVisible(False)
            action_lbl.setVisible(True)
            save_btn.setVisible(False)
            cancel_btn.setVisible(False)
            edit_btn.setVisible(True)

        def _on_save(_checked: bool = False, m: str = mode, g: str = gesture, c: QComboBox = combo, sl: QLabel = saved_lbl):
            selected_display = c.currentText()
            action_key = _ACTION_KEY_FROM_LABEL.get(selected_display, selected_display)
            self._save_mapping(m, g, action_key)
            action_lbl.setText(selected_display)
            sl.setVisible(True)
            QTimer.singleShot(1500, lambda: sl.setVisible(False))
            _cancel_edit()

        edit_btn.clicked.connect(_start_edit)
        save_btn.clicked.connect(_on_save)
        cancel_btn.clicked.connect(_cancel_edit)

        lay.addWidget(gesture_lbl)
        lay.addWidget(action_lbl)
        lay.addWidget(combo)
        lay.addWidget(edit_btn)
        lay.addWidget(save_btn)
        lay.addWidget(cancel_btn)
        lay.addStretch()
        lay.addWidget(saved_lbl)
        return row

    def _save_mapping(self, mode: str, gesture: str, action: str) -> None:
        try:
            valid_modes = {'App Mode', 'Media Mode', 'System Mode'}
            if mode not in valid_modes:
                raise ValueError(f'Invalid mode key: {mode!r}')

            data = _load_gesture_map()
            if mode not in data:
                data[mode] = {}
            data[mode][gesture] = action
            with open(_GESTURE_MAP_PATH, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=4)
            self.mapping_changed.emit()
        except Exception as exc:
            print(f'[GestureMapPanel] Failed to save: {exc}')

    def _set_training_inputs_enabled(self, enabled: bool) -> None:
        self._gesture_name_input.setEnabled(enabled)
        self._custom_action_combo.setEnabled(enabled)
        self._delete_custom_btn.setEnabled(enabled)

    def _set_section_collapsed(self, content: QWidget, button: QPushButton, collapsed: bool, label: str) -> None:
        content.setVisible(not collapsed)
        button.setProperty('collapsed', collapsed)
        marker = '►' if collapsed else '▼'
        button.setText(f'{marker} {label.upper()}')

    def _toggle_section(self, content: QWidget, button: QPushButton, label: str) -> None:
        currently_collapsed = bool(button.property('collapsed'))
        self._set_section_collapsed(content, button, not currently_collapsed, label)

    def _on_train_clicked(self) -> None:
        if self._training_active:
            self._training_active = False
            self._recorder.reset()
            self._train_progress.setValue(0)
            self._train_btn.setText('Train New Gesture')
            self._train_status.setText('Training cancelled.')
            self._train_status.setStyleSheet(f'color: {INACTIVE}; font-size: 11px;')
            self._set_training_inputs_enabled(True)
            return

        gesture_name = self._gesture_name_input.text().strip()
        if not gesture_name:
            self._train_status.setText('Gesture name is required.')
            self._train_status.setStyleSheet(f'color: {INACTIVE}; font-size: 11px;')
            return

        if gesture_name in self._custom_store.gestures:
            answer = QMessageBox.question(
                self,
                'Overwrite Gesture',
                f'A gesture named "{gesture_name}" already exists. Overwrite it?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        selected_label = self._custom_action_combo.currentText()
        action_key = _CUSTOM_ACTION_KEY_FROM_LABEL.get(selected_label, '').strip()
        if not action_key:
            self._train_status.setText('Please choose a valid action.')
            self._train_status.setStyleSheet(f'color: {INACTIVE}; font-size: 11px;')
            return

        self._recorder.reset()
        self._train_progress.setMaximum(self._recorder.target_frames)
        self._train_progress.setValue(0)
        self._training_name = gesture_name
        self._training_action = action_key
        self._training_active = True
        self._set_section_collapsed(self._train_content, self._train_toggle_btn, False, self._TRAIN_SECTION_LABEL)
        self._train_btn.setText('Cancel Training')
        self._set_training_inputs_enabled(False)
        self._train_status.setText('Training started. Hold your gesture steadily in view.')
        self._train_status.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px;')

    @pyqtSlot(object)
    def _on_landmarks(self, landmarks) -> None:
        if not self._training_active:
            return

        if landmarks is None:
            self._train_status.setText('No hand detected. Waiting for valid frames...')
            self._train_status.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px;')
            return

        added = self._recorder.add_frame(landmarks)
        if not added:
            self._train_status.setText('Invalid frame skipped. Keep your hand steady and fully visible.')
            self._train_status.setStyleSheet(f'color: {INACTIVE}; font-size: 11px;')
            return

        self._train_progress.setValue(self._recorder.frame_count)
        self._train_status.setText(
            f'Recording... {self._recorder.frame_count}/{self._recorder.target_frames} valid frames captured.'
        )
        self._train_status.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px;')

        if self._recorder.is_complete:
            self._finalize_training()

    def _finalize_training(self) -> None:
        try:
            pattern = self._recorder.average_pattern()
            self._custom_store.add_or_update(
                self._training_name,
                pattern,
                self._training_action,
            )
            self._train_status.setText(
                f'Saved custom gesture "{self._training_name}" mapped to '
                f'{_CUSTOM_ACTION_DISPLAY_LABELS.get(self._training_action, self._training_action)}.'
            )
            self._train_status.setStyleSheet(f'color: {ACTIVE}; font-size: 11px;')
            self._refresh_custom_gestures()
        except GestureDataError as exc:
            self._train_status.setText(f'Training failed: {exc}')
            self._train_status.setStyleSheet(f'color: {INACTIVE}; font-size: 11px;')
        except Exception as exc:
            self._train_status.setText(f'Training failed: {exc}')
            self._train_status.setStyleSheet(f'color: {INACTIVE}; font-size: 11px;')
        finally:
            self._training_active = False
            self._recorder.reset()
            self._train_progress.setValue(0)
            self._train_btn.setText('Train New Gesture')
            self._set_training_inputs_enabled(True)

    def _refresh_custom_gestures(self) -> None:
        self._custom_store.reload_if_changed()
        self._custom_list.clear()

        all_gestures = self._custom_store.list_gestures()
        if not all_gestures:
            item = QListWidgetItem('No custom gestures saved yet.')
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._custom_list.addItem(item)
            return

        for item_data in all_gestures:
            name = item_data['name']
            action_key = item_data['action']
            action_label = _CUSTOM_ACTION_DISPLAY_LABELS.get(action_key, action_key)
            item = QListWidgetItem(f'{name}  ->  {action_label}')
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._custom_list.addItem(item)

    def _delete_selected_custom(self) -> None:
        selected_item = self._custom_list.currentItem()
        if selected_item is None:
            self._train_status.setText('Select a saved custom gesture to delete.')
            self._train_status.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px;')
            return

        gesture_name = selected_item.data(Qt.ItemDataRole.UserRole)
        if not gesture_name:
            return

        answer = QMessageBox.question(
            self,
            'Delete Gesture',
            f'Delete custom gesture "{gesture_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        deleted = self._custom_store.delete(str(gesture_name))
        if deleted:
            self._train_status.setText(f'Deleted custom gesture "{gesture_name}".')
            self._train_status.setStyleSheet(f'color: {ACTIVE}; font-size: 11px;')
            self._refresh_custom_gestures()
        else:
            self._train_status.setText(f'Could not delete "{gesture_name}".')
            self._train_status.setStyleSheet(f'color: {INACTIVE}; font-size: 11px;')

    def reload(self) -> None:
        """Re-read gesture_map.json and refresh the displayed rows."""
        self._load_map()
        self._refresh_custom_gestures()


class HelpGuidePanel(QWidget):
    """Beginner-friendly in-app documentation with live gesture mappings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load_mapping_reference()

    def _build_ui(self) -> None:
        self.setStyleSheet(f'background-color: {BG_DEEP};')
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel('USER GUIDE')
        title.setStyleSheet(f'color: {ACCENT}; font-size: 16px; font-weight: 700; letter-spacing: 2px;')
        root.addWidget(title)

        subtitle = QLabel('Follow these steps to activate MMGI, use gestures, and switch modes confidently.')
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f'color: {TEXT_SEC}; font-size: 12px;')
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        content = QWidget()
        content.setStyleSheet('background: transparent;')
        self._content_lay = QVBoxLayout(content)
        self._content_lay.setContentsMargins(0, 0, 4, 0)
        self._content_lay.setSpacing(10)

        self._content_lay.addWidget(self._instruction_card(
            'How To Activate System',
            [
                '1. Face your hand toward the camera with Open Palm.',
                '2. Hold Open Palm steadily for 2 seconds.',
                '3. Wait for status to change to ACTIVE before giving commands.',
            ],
        ))
        self._content_lay.addWidget(self._instruction_card(
            'How To Use Gestures',
            [
                '1. Keep your hand centered and well-lit for accurate tracking.',
                '2. Show one clear gesture at a time.',
                '3. Hold the gesture briefly until action feedback appears.',
            ],
        ))
        self._content_lay.addWidget(self._instruction_card(
            'How To Switch Modes',
            [
                '1. Hold Three Fingers for about 1 second.',
                '2. Modes cycle in order: App -> Media -> System -> App.',
                '3. Wait for the mode label to update before your next command.',
            ],
        ))
        self._content_lay.addWidget(self._instruction_card(
            'New Features (Latest)',
            [
                '1. Login supports Face Recognition along with User-Password.',
                '2. In Settings -> Security, enable Face Security and capture your authorized face.',
                '3. In System Mode, use Voice Command for actions like Open Brave, Open YouTube, Close Window, Switch Tab, and Scroll Down.',
            ],
        ))

        self._mapping_title = QLabel('CURRENT GESTURE MAPPING')
        self._mapping_title.setStyleSheet(
            f'color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px; padding-top: 6px;'
        )
        self._content_lay.addWidget(self._mapping_title)

        self._mapping_container = QFrame()
        self._mapping_container.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        self._mapping_layout = QVBoxLayout(self._mapping_container)
        self._mapping_layout.setContentsMargins(14, 12, 14, 12)
        self._mapping_layout.setSpacing(6)
        self._content_lay.addWidget(self._mapping_container)
        self._content_lay.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    def _instruction_card(self, heading: str, lines: list[str]) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        head = QLabel(heading)
        head.setStyleSheet(f'color: {TEXT_PRI}; font-size: 13px; font-weight: 700;')
        lay.addWidget(head)

        for line in lines:
            lbl = QLabel(line)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 12px;')
            lay.addWidget(lbl)

        return card

    def _load_mapping_reference(self) -> None:
        while self._mapping_layout.count():
            item = self._mapping_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = _load_gesture_map()
        modes_to_show = ['App Mode', 'Media Mode', 'System Mode']

        found_any = False
        for mode in modes_to_show:
            gestures = data.get(mode, {})
            if mode == 'System Mode' and not gestures:
                gestures = {
                    'Voice Command': 'Open Brave / Open YouTube / Close Window / Switch Tab / Scroll Down'
                }
            if not gestures:
                continue
            found_any = True

            mode_label = QLabel(mode)
            mode_label.setStyleSheet(
                f'color: {_MODE_COLOUR.get(mode, ACCENT)}; font-size: 11px; font-weight: 700; letter-spacing: 1px;'
            )
            self._mapping_layout.addWidget(mode_label)

            for gesture, action in gestures.items():
                row = QLabel(f'{gesture} -> {_ACTION_DISPLAY_LABELS.get(action, action)}')
                row.setStyleSheet(f'color: {TEXT_SEC}; font-size: 12px; padding-left: 8px;')
                self._mapping_layout.addWidget(row)

            self._mapping_layout.addWidget(_divider())

        if not found_any:
            empty = QLabel('No gesture mappings found in config/gesture_map.json')
            empty.setStyleSheet(f'color: {TEXT_HINT}; font-size: 12px; font-style: italic;')
            self._mapping_layout.addWidget(empty)

    def refresh(self) -> None:
        self._load_mapping_reference()


class SettingsPanel(QWidget):
    """Settings tab with security controls for face-based authentication."""

    def __init__(self, state: SharedState, config_manager: ConfigManager | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._worker: WorkerThread | None = None
        self._cfg = _load_face_security_config()
        self._calibration = CalibrationManager()
        self._wizard_active = False
        self._latest_preview_image: QImage | None = None
        self._verification_samples = 0
        self._verification_hits = 0
        
        # Initialize ConfigManager (create if not provided)
        if config_manager is None:
            config_manager = ConfigManager()
        self._config_manager = config_manager
        
        self._build_ui()
        self._connect_state()
        self._sync_ui_from_config()
        self._subscribe_to_config_changes()

    def set_worker(self, worker: WorkerThread | None) -> None:
        self._worker = worker

    @pyqtSlot(QImage)
    def update_preview_frame(self, image: QImage) -> None:
        self._latest_preview_image = image
        if not hasattr(self, '_preview_label'):
            return
        viewport = self._preview_label.contentsRect()
        w = viewport.width()
        h = viewport.height()
        if w < 8 or h < 8:
            return
        pix = QPixmap.fromImage(image).scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(pix)

    def _connect_state(self) -> None:
        self._state.gesture_changed.connect(self._on_live_gesture)
        self._state.confidence_changed.connect(self._on_live_confidence)
        self._state.gesture_status_changed.connect(self._on_live_gesture_status)
        self._state.mode_changed.connect(self._on_mode_changed)

    def _build_ui(self) -> None:
        self.setStyleSheet(f'background-color: {BG_DEEP};')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        content = QWidget()
        content.setStyleSheet(f'background-color: {BG_DEEP};')

        root = QVBoxLayout(content)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(10)

        title = QLabel('SETTINGS')
        title.setStyleSheet(
            f'color: {ACCENT}; font-size: 16px; font-weight: 700; letter-spacing: 2px;'
        )
        root.addWidget(title)

        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        sec_title = QLabel('SECURITY')
        sec_title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 700; letter-spacing: 2px; background: transparent; border: none;'
        )
        lay.addWidget(sec_title)
        lay.addWidget(_divider())

        self._face_toggle = QCheckBox('Enable Face Security')
        self._face_toggle.setStyleSheet(f"""
            QCheckBox {{ color: {TEXT_PRI}; font-size: 13px; font-weight: 600; background: transparent; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QCheckBox::indicator:unchecked {{ border: 1px solid {BORDER}; background: {BG_HOVER}; border-radius: 3px; }}
            QCheckBox::indicator:checked {{ border: 1px solid {ACTIVE}; background: {ACTIVE}; border-radius: 3px; }}
        """)
        self._face_toggle.stateChanged.connect(self._on_toggle_face_security)
        lay.addWidget(self._face_toggle)

        self._capture_btn = QPushButton('Activate + Capture Authorized Face')
        self._capture_btn.setFixedHeight(36)
        self._capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._capture_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,229,255,0.12); color: {ACCENT}; border: 1px solid {ACCENT};
                border-radius: 8px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: rgba(0,229,255,0.24); }}
        """)
        self._capture_btn.clicked.connect(self._on_capture_face)
        lay.addWidget(self._capture_btn)

        hint = QLabel(
            'This captures your face from the live camera and enables face security.\n'
            'Restart MMGI after capture to apply the new authorized face encoding.'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px; background: transparent; border: none;')
        lay.addWidget(hint)

        self._status_lbl = QLabel('')
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; font-weight: 600; background: transparent; border: none;')
        lay.addWidget(self._status_lbl)

        root.addWidget(card)

        runtime_card = QFrame()
        runtime_card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        runtime_lay = QVBoxLayout(runtime_card)
        runtime_lay.setContentsMargins(16, 14, 16, 16)
        runtime_lay.setSpacing(8)

        runtime_title = QLabel('RUNTIME CONTROLS')
        runtime_title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 700; letter-spacing: 2px; background: transparent; border: none;'
        )
        runtime_lay.addWidget(runtime_title)
        runtime_lay.addWidget(_divider())

        self._voice_toggle = QCheckBox('Enable Voice Listener')
        self._voice_toggle.setStyleSheet(self._face_toggle.styleSheet())
        self._voice_toggle.stateChanged.connect(lambda _: self._state.set_voice_listener_enabled(self._voice_toggle.isChecked()))
        runtime_lay.addWidget(self._voice_toggle)

        self._gesture_toggle = QCheckBox('Enable Gesture Control')
        self._gesture_toggle.setStyleSheet(self._face_toggle.styleSheet())
        self._gesture_toggle.stateChanged.connect(lambda _: self._state.set_gesture_control_enabled(self._gesture_toggle.isChecked()))
        runtime_lay.addWidget(self._gesture_toggle)

        mode_row = QHBoxLayout()
        mode_lbl = QLabel('Manual Mode')
        mode_lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(['App Mode', 'Media Mode', 'System Mode'])
        self._mode_combo.setMinimumWidth(180)
        self._mode_combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG_HOVER}; color: {TEXT_PRI}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 5px 8px; font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox:hover {{ border-color: {ACCENT}; }}
        """)
        self._mode_combo.currentTextChanged.connect(self._state.request_mode)
        mode_row.addWidget(mode_lbl)
        mode_row.addStretch()
        mode_row.addWidget(self._mode_combo)
        runtime_lay.addLayout(mode_row)

        root.addWidget(runtime_card)

        # ── Detection & Response Controls ──────────────────────────────
        detection_card = QFrame()
        detection_card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        detection_lay = QVBoxLayout(detection_card)
        detection_lay.setContentsMargins(16, 14, 16, 16)
        detection_lay.setSpacing(10)

        detection_title = QLabel('DETECTION & RESPONSE')
        detection_title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 700; letter-spacing: 2px; background: transparent; border: none;'
        )
        detection_lay.addWidget(detection_title)
        detection_lay.addWidget(_divider())

        # Hand detection confidence slider
        conf_row = QHBoxLayout()
        conf_lbl = QLabel('Hand Detection Confidence')
        conf_lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        self._confidence_val = QLabel('0.70')
        self._confidence_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._confidence_val.setStyleSheet(f'color: {TEXT_PRI}; font-size: 11px; font-weight: 600; background: transparent; border: none;')
        conf_row.addWidget(conf_lbl)
        conf_row.addStretch()
        conf_row.addWidget(self._confidence_val)
        detection_lay.addLayout(conf_row)

        self._confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self._confidence_slider.setRange(50, 95)
        self._confidence_slider.setValue(70)
        self._confidence_slider.setSingleStep(1)
        self._confidence_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: {BORDER}; height: 5px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; margin: -5px 0; border-radius: 7px; }}
            QSlider::handle:horizontal:hover {{ background: #33ffff; }}
        """)
        self._confidence_slider.valueChanged.connect(self._on_confidence_changed)
        detection_lay.addWidget(self._confidence_slider)

        # Gesture confirmation frames slider
        frames_row = QHBoxLayout()
        frames_lbl = QLabel('Gesture Confirmation Frames')
        frames_lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        self._frames_val = QLabel('5')
        self._frames_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._frames_val.setStyleSheet(f'color: {TEXT_PRI}; font-size: 11px; font-weight: 600; background: transparent; border: none;')
        frames_row.addWidget(frames_lbl)
        frames_row.addStretch()
        frames_row.addWidget(self._frames_val)
        detection_lay.addLayout(frames_row)

        self._frames_slider = QSlider(Qt.Orientation.Horizontal)
        self._frames_slider.setRange(2, 20)
        self._frames_slider.setValue(5)
        self._frames_slider.setSingleStep(1)
        self._frames_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: {BORDER}; height: 5px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {ACTIVE}; width: 14px; margin: -5px 0; border-radius: 7px; }}
            QSlider::handle:horizontal:hover {{ background: #44ffaa; }}
        """)
        self._frames_slider.valueChanged.connect(self._on_frames_changed)
        detection_lay.addWidget(self._frames_slider)

        root.addWidget(detection_card)

        calib_card = QFrame()
        calib_card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        calib_lay = QVBoxLayout(calib_card)
        calib_lay.setContentsMargins(16, 14, 16, 16)
        calib_lay.setSpacing(10)

        calib_title = QLabel('CALIBRATION')
        calib_title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 700; letter-spacing: 2px; background: transparent; border: none;'
        )
        calib_lay.addWidget(calib_title)
        calib_lay.addWidget(_divider())

        self._hold_slider, self._hold_value = self._slider_row(
            'Gesture Hold Time',
            min_value=5,
            max_value=25,
            suffix='s',
            value_scale=10.0,
        )
        calib_lay.addLayout(self._hold_slider)

        self._stable_slider, self._stable_value = self._slider_row(
            'Stability Frames',
            min_value=2,
            max_value=20,
            suffix='f',
            value_scale=1.0,
        )
        calib_lay.addLayout(self._stable_slider)

        self._sensitivity_slider, self._sensitivity_value = self._slider_row(
            'Base Cursor Sensitivity',
            min_value=5,
            max_value=25,
            suffix='x',
            value_scale=10.0,
        )
        calib_lay.addLayout(self._sensitivity_slider)

        self._debug_overlay_toggle = QCheckBox('Enable debug overlay on camera feed')
        self._debug_overlay_toggle.setStyleSheet(f"""
            QCheckBox {{ color: {TEXT_PRI}; font-size: 12px; background: transparent; }}
            QCheckBox::indicator {{ width: 14px; height: 14px; }}
            QCheckBox::indicator:unchecked {{ border: 1px solid {BORDER}; background: {BG_HOVER}; border-radius: 3px; }}
            QCheckBox::indicator:checked {{ border: 1px solid {ACTIVE}; background: {ACTIVE}; border-radius: 3px; }}
        """)
        calib_lay.addWidget(self._debug_overlay_toggle)

        btn_row = QHBoxLayout()
        self._apply_calib_btn = QPushButton('Apply Calibration')
        self._apply_calib_btn.setFixedHeight(34)
        self._apply_calib_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_calib_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,255,136,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE};
                border-radius: 8px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: rgba(0,255,136,0.24); }}
        """)
        self._apply_calib_btn.clicked.connect(self._on_apply_calibration)

        self._wizard_btn = QPushButton('Start Calibration Wizard')
        self._wizard_btn.setFixedHeight(34)
        self._wizard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wizard_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,229,255,0.12); color: {ACCENT}; border: 1px solid {ACCENT};
                border-radius: 8px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: rgba(0,229,255,0.24); }}
        """)
        self._wizard_btn.clicked.connect(self._on_wizard_step)

        btn_row.addWidget(self._apply_calib_btn)
        btn_row.addWidget(self._wizard_btn)
        calib_lay.addLayout(btn_row)

        self._calib_status_lbl = QLabel('Adjust values and click Apply Calibration.')
        self._calib_status_lbl.setWordWrap(True)
        self._calib_status_lbl.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px; background: transparent; border: none;')
        calib_lay.addWidget(self._calib_status_lbl)

        root.addWidget(calib_card)

        verify_card = QFrame()
        verify_card.setStyleSheet(
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}'
        )
        verify_lay = QVBoxLayout(verify_card)
        verify_lay.setContentsMargins(16, 14, 16, 16)
        verify_lay.setSpacing(8)

        verify_title = QLabel('GESTURE VERIFICATION')
        verify_title.setStyleSheet(
            f'color: {ACCENT}; font-size: 10px; font-weight: 700; letter-spacing: 2px; background: transparent; border: none;'
        )
        verify_lay.addWidget(verify_title)
        verify_lay.addWidget(_divider())

        self._preview_label = QLabel('Live preview unavailable')
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setFixedHeight(220)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preview_label.setScaledContents(False)
        self._preview_label.setStyleSheet(
            f'background: #000; color: {TEXT_HINT}; border: 1px solid {BORDER}; border-radius: 8px;'
        )
        verify_lay.addWidget(self._preview_label)

        verify_row = QHBoxLayout()
        self._verify_gesture_combo = QComboBox()
        self._verify_gesture_combo.addItems(['Open Palm', 'Pinch', 'Three Fingers Hold'])
        self._verify_gesture_combo.setStyleSheet(self._mode_combo.styleSheet())
        self._test_gesture_btn = QPushButton('Test Gesture')
        self._test_gesture_btn.setFixedHeight(30)
        self._test_gesture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_gesture_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,229,255,0.12); color: {ACCENT}; border: 1px solid {ACCENT};
                border-radius: 8px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: rgba(0,229,255,0.24); }}
        """)
        self._test_gesture_btn.clicked.connect(self._on_test_gesture)
        verify_row.addWidget(self._verify_gesture_combo)
        verify_row.addWidget(self._test_gesture_btn)
        verify_lay.addLayout(verify_row)

        self._verify_feedback_lbl = QLabel('Select a target gesture and click Test Gesture.')
        self._verify_feedback_lbl.setWordWrap(True)
        self._verify_feedback_lbl.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px; background: transparent; border: none;')
        verify_lay.addWidget(self._verify_feedback_lbl)

        self._live_metrics_lbl = QLabel('Live: confidence=0.00, distance=n/a, status=Not Detected')
        self._live_metrics_lbl.setWordWrap(True)
        self._live_metrics_lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        verify_lay.addWidget(self._live_metrics_lbl)

        root.addWidget(verify_card)
        root.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _slider_row(
        self,
        title: str,
        min_value: int,
        max_value: int,
        suffix: str,
        value_scale: float,
    ) -> tuple[QVBoxLayout, QLabel]:
        block = QVBoxLayout()
        block.setSpacing(4)

        row = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; background: transparent; border: none;')
        val = QLabel('')
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val.setStyleSheet(f'color: {TEXT_PRI}; font-size: 11px; font-weight: 600; background: transparent; border: none;')
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        block.addLayout(row)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_value, max_value)
        slider.setSingleStep(1)
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: {BORDER}; height: 5px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; margin: -5px 0; border-radius: 7px; }}
        """)

        def _refresh_label(raw: int) -> None:
            value = raw / value_scale
            if value_scale == 1.0:
                val.setText(f'{int(value)} {suffix}')
            else:
                val.setText(f'{value:.1f} {suffix}')

        slider.valueChanged.connect(_refresh_label)
        block.addWidget(slider)

        if title.startswith('Gesture Hold'):
            self._hold_time_slider = slider
        elif title.startswith('Stability'):
            self._stability_frames_slider = slider
        else:
            self._base_sensitivity_slider = slider

        return block, val

    def _sync_ui_from_config(self) -> None:
        self._cfg = _load_face_security_config()
        self._calibration.load()
        self._face_toggle.blockSignals(True)
        self._face_toggle.setChecked(bool(self._cfg.get('enabled', True)))
        self._face_toggle.blockSignals(False)
        self._state.set_face_security_enabled(bool(self._cfg.get('enabled', True)))

        self._voice_toggle.blockSignals(True)
        self._voice_toggle.setChecked(bool(self._state.voice_listener_enabled))
        self._voice_toggle.blockSignals(False)

        self._gesture_toggle.blockSignals(True)
        self._gesture_toggle.setChecked(bool(self._state.gesture_control_enabled))
        self._gesture_toggle.blockSignals(False)

        self._mode_combo.blockSignals(True)
        idx = self._mode_combo.findText(self._state.current_mode)
        self._mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._mode_combo.blockSignals(False)

        profile = self._calibration.profile
        self._hold_time_slider.blockSignals(True)
        self._stability_frames_slider.blockSignals(True)
        self._base_sensitivity_slider.blockSignals(True)

        self._hold_time_slider.setValue(int(round(profile.gesture_hold_seconds * 10.0)))
        self._stability_frames_slider.setValue(int(profile.stability_frames))
        self._base_sensitivity_slider.setValue(int(round(profile.base_cursor_sensitivity * 10.0)))
        self._debug_overlay_toggle.setChecked(bool(profile.debug_overlay_enabled))

        self._hold_time_slider.blockSignals(False)
        self._stability_frames_slider.blockSignals(False)
        self._base_sensitivity_slider.blockSignals(False)

        self._hold_value.setText(f'{profile.gesture_hold_seconds:.1f} s')
        self._stable_value.setText(f'{int(profile.stability_frames)} f')
        self._sensitivity_value.setText(f'{profile.base_cursor_sensitivity:.1f} x')

        # Load ConfigManager settings
        self._confidence_slider.blockSignals(True)
        self._frames_slider.blockSignals(True)
        
        try:
            conf_value = self._config_manager.get('thresholds', 'hand_detection_confidence', default=0.70)
            if conf_value is not None:
                conf_slider_val = int(conf_value * 100)
                self._confidence_slider.setValue(conf_slider_val)
                self._confidence_val.setText(f'{conf_value:.2f}')
        except Exception:
            pass
        
        try:
            frames_value = self._config_manager.get('smoothing', 'gesture_confirmation_frames', default=4)
            if frames_value is not None:
                frames_slider_val = int(frames_value)
                self._frames_slider.setValue(frames_slider_val)
                self._frames_val.setText(str(frames_slider_val))
        except Exception:
            pass
        
        self._confidence_slider.blockSignals(False)
        self._frames_slider.blockSignals(False)

    def _subscribe_to_config_changes(self) -> None:
        """Subscribe to ConfigManager changes to update UI when config changes externally."""
        try:
            self._config_manager.subscribe(self._on_config_changed)
        except Exception:
            pass

    @pyqtSlot()
    def _on_config_changed(self, change=None) -> None:
        """Handle ConfigManager config file changes by reloading from config."""
        # Reload sliders from config file
        self._confidence_slider.blockSignals(True)
        self._frames_slider.blockSignals(True)
        
        try:
            conf_value = self._config_manager.get('thresholds', 'hand_detection_confidence', default=0.70)
            if conf_value is not None:
                conf_slider_val = int(conf_value * 100)
                self._confidence_slider.setValue(conf_slider_val)
                self._confidence_val.setText(f'{conf_value:.2f}')
        except Exception:
            pass
        
        try:
            frames_value = self._config_manager.get('smoothing', 'gesture_confirmation_frames', default=4)
            if frames_value is not None:
                frames_slider_val = int(frames_value)
                self._frames_slider.setValue(frames_slider_val)
                self._frames_val.setText(str(frames_slider_val))
        except Exception:
            pass
        
        self._confidence_slider.blockSignals(False)
        self._frames_slider.blockSignals(False)

    @pyqtSlot(int)
    def _on_confidence_changed(self, slider_value: int) -> None:
        """Update hand detection confidence threshold in ConfigManager."""
        conf_float = slider_value / 100.0
        self._confidence_val.setText(f'{conf_float:.2f}')
        try:
            self._config_manager.set('thresholds', 'hand_detection_confidence', conf_float)
        except Exception as e:
            print(f'[SettingsPanel] Failed to save confidence threshold: {e}')

    @pyqtSlot(int)
    def _on_frames_changed(self, slider_value: int) -> None:
        """Update gesture confirmation frames in ConfigManager."""
        self._frames_val.setText(str(slider_value))
        try:
            self._config_manager.set('smoothing', 'gesture_confirmation_frames', slider_value)
        except Exception as e:
            print(f'[SettingsPanel] Failed to save frames threshold: {e}')

    def _on_toggle_face_security(self, _state: int) -> None:
        self._cfg['enabled'] = self._face_toggle.isChecked()
        self._state.set_face_security_enabled(self._cfg['enabled'])
        try:
            _save_face_security_config(self._cfg)
            if self._cfg['enabled']:
                self._status_lbl.setText('Face security enabled. It will remain active until you disable it.')
                self._status_lbl.setStyleSheet(
                    f'color: {ACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
                )
            else:
                self._status_lbl.setText('Face security disabled.')
                self._status_lbl.setStyleSheet(
                    f'color: {INACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
                )
        except Exception as exc:
            self._status_lbl.setText(f'Failed to save setting: {exc}')
            self._status_lbl.setStyleSheet(
                f'color: {INACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )

    def _on_capture_face(self) -> None:
        self._cfg['enabled'] = True
        self._face_toggle.blockSignals(True)
        self._face_toggle.setChecked(True)
        self._face_toggle.blockSignals(False)
        try:
            _save_face_security_config(self._cfg)
        except Exception as exc:
            self._status_lbl.setText(f'Failed to enable face security: {exc}')
            self._status_lbl.setStyleSheet(
                f'color: {INACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )
            return

        if self._worker is None or not self._worker.isRunning():
            self._status_lbl.setText('Worker not running yet. Start camera stream and try again.')
            self._status_lbl.setStyleSheet(
                f'color: {INACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )
            return

        ok, message = self._worker.capture_authorized_face()
        if ok:
            self._status_lbl.setText(message)
            self._status_lbl.setStyleSheet(
                f'color: {ACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )
            QMessageBox.information(self, 'Face Captured', message)
        else:
            self._status_lbl.setText(message)
            self._status_lbl.setStyleSheet(
                f'color: {INACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )

    def _on_apply_calibration(self) -> None:
        hold_seconds = self._hold_time_slider.value() / 10.0
        stability_frames = int(self._stability_frames_slider.value())
        base_sensitivity = self._base_sensitivity_slider.value() / 10.0
        debug_enabled = self._debug_overlay_toggle.isChecked()

        self._calibration.update(
            gesture_hold_seconds=hold_seconds,
            mode_switch_hold_seconds=hold_seconds,
            stability_frames=stability_frames,
            base_cursor_sensitivity=base_sensitivity,
            debug_overlay_enabled=debug_enabled,
        )
        self._calibration.save()

        if self._worker is not None:
            self._worker.reload_calibration()

        self._calib_status_lbl.setText(
            f'Calibration applied: hold={hold_seconds:.1f}s, stability={stability_frames}, sensitivity={base_sensitivity:.1f}x'
        )
        self._calib_status_lbl.setStyleSheet(
            f'color: {ACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
        )

    def _on_wizard_step(self) -> None:
        landmarks = getattr(self._state, '_latest_landmarks', None)
        sample = CalibrationManager.estimate_hand_distance(landmarks)

        if not self._wizard_active:
            message = self._calibration.start_wizard()
            self._wizard_active = True
            self._wizard_btn.setText('Wizard: Next Step')
        else:
            message = self._calibration.wizard_record_sample(sample)
            if 'complete' in message.lower():
                self._wizard_active = False
                self._wizard_btn.setText('Start Calibration Wizard')
                self._sync_ui_from_config()
                if self._worker is not None:
                    self._worker.reload_calibration()

        self._calib_status_lbl.setText(message)
        self._calib_status_lbl.setStyleSheet(
            f'color: {ACCENT}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
        )

    @pyqtSlot(str)
    def _on_live_gesture(self, gesture: str) -> None:
        confidence = self._state.confidence
        hand_distance = CalibrationManager.estimate_hand_distance(getattr(self._state, '_latest_landmarks', None))
        distance_text = f'{hand_distance:.3f}' if hand_distance is not None else 'n/a'
        self._live_metrics_lbl.setText(
            f'Live: confidence={confidence:.2f}, distance={distance_text}, status={self._state.gesture_status}'
        )

    @pyqtSlot(float)
    def _on_live_confidence(self, _confidence: float) -> None:
        self._on_live_gesture(self._state.current_gesture)

    @pyqtSlot(str)
    def _on_live_gesture_status(self, _status: str) -> None:
        self._on_live_gesture(self._state.current_gesture)

    @pyqtSlot(str)
    def _on_mode_changed(self, mode: str) -> None:
        self._mode_combo.blockSignals(True)
        idx = self._mode_combo.findText(mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._mode_combo.blockSignals(False)

    def _on_test_gesture(self) -> None:
        target = self._verify_gesture_combo.currentText()
        gesture = self._state.current_gesture
        confidence = float(self._state.confidence)
        landmarks = getattr(self._state, '_latest_landmarks', None)

        detected = False
        if target == 'Open Palm':
            detected = gesture.strip().lower() == 'open palm'
        elif target == 'Pinch':
            detected = CalibrationManager.is_pinch_detected(landmarks)
        elif target == 'Three Fingers Hold':
            detected = gesture.strip().lower() in {'three fingers', 'three fingers hold'}

        threshold = self._calibration.profile.gesture_thresholds.get(target)
        min_conf = threshold.min_confidence if threshold is not None else 0.5
        stable_ok = self._state.gesture_status.lower() == 'stable'
        pass_now = detected and confidence >= min_conf and stable_ok

        self._verification_samples += 1
        if pass_now:
            self._verification_hits += 1

        pass_rate = (self._verification_hits / self._verification_samples) * 100.0
        if pass_now:
            self._verify_feedback_lbl.setText(
                f'Detected: {target} (confidence={confidence:.2f} >= {min_conf:.2f}, stable={stable_ok}). Pass rate {pass_rate:.0f}%.'
            )
            self._verify_feedback_lbl.setStyleSheet(
                f'color: {ACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )
        else:
            self._verify_feedback_lbl.setText(
                f'Not detected: {target}. Need confidence >= {min_conf:.2f} and stable gesture. Pass rate {pass_rate:.0f}%.'
            )
            self._verify_feedback_lbl.setStyleSheet(
                f'color: {INACTIVE}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )

    def refresh(self) -> None:
        self._sync_ui_from_config()


class SystemPanel(QWidget):
    def __init__(self, state: SharedState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build(state)

    def _build(self, state: SharedState) -> None:
        self.setMinimumWidth(280)
        self.setMaximumWidth(380)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f'background-color: {BG_DEEP};')

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Wrap all cards in a scroll area so nothing is clipped
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        container = QWidget()
        container.setStyleSheet(f'background: {BG_DEEP};')
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(SystemCard(state))
        self._mode_card = ModeCard(state)
        root.addWidget(self._mode_card)
        self._guide_card = GestureGuideCard()
        root.addWidget(self._guide_card)
        root.addWidget(PerformanceCard(state))
        root.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def refresh_guide(self) -> None:
        self._guide_card.refresh()

    def refresh_mappings(self) -> None:
        """Refresh mapping-dependent cards after gesture remapping."""
        self._mode_card.refresh_current_mode()
        self._guide_card.refresh()


# ===========================================================================
# MainWindow  (was ui/main_window.py)
# ===========================================================================

class MainWindow(QMainWindow):
    WINDOW_TITLE   = 'MMGI  —  Smart Mode AI Gesture Controller'
    MIN_W, MIN_H   = 1100, 650

    def __init__(self) -> None:
        super().__init__()
        self._state  = SharedState(self)
        self._worker: WorkerThread | None = None
        self._lifecycle = PipelineLifecycleManager(self)
        self._config_manager = ConfigManager()
        self._setup_window()
        self._build_ui()
        self._start_worker()

    def _setup_window(self) -> None:
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.resize(1280, 720)
        self.setStyleSheet(GLOBAL_QSS)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)

        self._sidebar = Sidebar()
        self._sidebar.tab_selected.connect(self._on_tab_selected)

        # Main view: camera + system panel
        main_view = QWidget()
        main_view.setStyleSheet(f'background: {BG_DEEP};')
        main_lay = QHBoxLayout(main_view)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        self._vision    = VisionPanel(self._state)
        self._sys_panel = SystemPanel(self._state)
        main_lay.addWidget(self._vision, stretch=1)
        main_lay.addWidget(self._sys_panel)

        # Gestures tab view
        self._gesture_map_panel = GestureMapPanel(self._state)
        self._gesture_map_panel.mapping_changed.connect(self._on_mapping_changed)

        # Help / Guide tab view
        self._help_panel = HelpGuidePanel()

        # Settings tab view
        self._settings_panel = SettingsPanel(self._state, self._config_manager)

        # Logs tab view
        self._logs_panel = QWidget()
        logs_lay = QVBoxLayout(self._logs_panel)
        logs_lay.setContentsMargins(20, 16, 20, 16)
        logs_lay.setSpacing(8)
        logs_title = QLabel('LIVE LOG STREAM')
        logs_title.setStyleSheet(
            f'color: {ACCENT}; font-size: 14px; font-weight: 700; letter-spacing: 2px; background: transparent; border: none;'
        )
        logs_lay.addWidget(logs_title)
        self._activity = ActivityLog(self._state, compact=False)
        logs_lay.addWidget(self._activity, stretch=1)

        # Stack: index 0 = main view, index 1 = gesture mapping, index 2 = help, index 3 = settings, index 4 = logs
        self._body_stack = QStackedWidget()
        self._body_stack.addWidget(main_view)
        self._body_stack.addWidget(self._gesture_map_panel)
        self._body_stack.addWidget(self._help_panel)
        self._body_stack.addWidget(self._settings_panel)
        self._body_stack.addWidget(self._logs_panel)

        body.addWidget(self._sidebar)
        body.addWidget(self._body_stack, stretch=1)
        root.addLayout(body, stretch=1)

    @pyqtSlot(str)
    def _on_tab_selected(self, tab_id: str) -> None:
        if tab_id == 'gestures':
            self._gesture_map_panel.reload()
            self._body_stack.setCurrentIndex(1)
        elif tab_id == 'mode':
            self._body_stack.setCurrentIndex(0)
        elif tab_id == 'logs':
            self._body_stack.setCurrentIndex(4)
        elif tab_id == 'help':
            self._help_panel.refresh()
            self._body_stack.setCurrentIndex(2)
        elif tab_id == 'settings':
            self._settings_panel.refresh()
            self._body_stack.setCurrentIndex(3)
        else:
            self._body_stack.setCurrentIndex(0)

    @pyqtSlot()
    def _on_mapping_changed(self) -> None:
        """Refresh the gesture guide card after a mapping is saved."""
        self._sys_panel.refresh_mappings()
        self._help_panel.refresh()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f'background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, '
            f'stop:0 #0F1A2E, stop:1 #111F36); border-bottom: 1px solid rgba(123,233,255,0.16);'
        )
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(10)

        dot = QLabel('◉')
        dot.setStyleSheet(f'color: {ACCENT}; font-size: 14px;')
        self._header_dot = dot

        title = QLabel('MMGI')
        title.setStyleSheet(f'color: {ACCENT_SOFT}; font-size: 16px; font-weight: 800; letter-spacing: 4px;')

        subtitle = QLabel('Smart Mode AI Gesture Controller')
        subtitle.setStyleSheet(f'color: {TEXT_HINT}; font-size: 12px;')

        self._header_status = QLabel('INACTIVE')
        self._header_status.setStyleSheet(f'color: {INACTIVE}; font-size: 12px; font-weight: 700;')

        self._status_dot = QLabel('●')
        self._status_dot.setStyleSheet(f'color: {INACTIVE}; font-size: 12px;')

        self._header_mode = QLabel('APP MODE')
        self._header_mode.setStyleSheet(
            f'color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px; '
            f'background: rgba(56,221,248,0.12); border: 1px solid rgba(123,233,255,0.45); border-radius: 12px; padding: 3px 12px;'
        )

        self._fps_stat = QLabel('FPS: --')
        self._fps_stat.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; font-weight: 600;')
        self._lat_stat = QLabel('Latency: -- ms')
        self._lat_stat.setStyleSheet(f'color: {TEXT_SEC}; font-size: 11px; font-weight: 600;')

        lay.addWidget(dot)
        lay.addWidget(title)
        lay.addWidget(subtitle)
        lay.addStretch()
        lay.addWidget(self._header_mode)
        lay.addStretch()

        self._start_btn = QPushButton('Start')
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setFixedHeight(26)
        self._start_btn.setStyleSheet(
            f'QPushButton {{ background: rgba(0,255,136,0.12); color: {ACTIVE}; border: 1px solid {ACTIVE}; '
            f'border-radius: 8px; padding: 2px 10px; font-size: 11px; font-weight: 700; }}'
            f'QPushButton:hover {{ background: rgba(0,255,136,0.24); }}'
        )
        self._start_btn.clicked.connect(self._start_worker)

        self._stop_btn = QPushButton('Stop')
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setFixedHeight(26)
        self._stop_btn.setStyleSheet(
            f'QPushButton {{ background: rgba(255,68,102,0.12); color: {INACTIVE}; border: 1px solid {INACTIVE}; '
            f'border-radius: 8px; padding: 2px 10px; font-size: 11px; font-weight: 700; }}'
            f'QPushButton:hover {{ background: rgba(255,68,102,0.24); }}'
        )
        self._stop_btn.clicked.connect(self._stop_worker)

        self._restart_btn = QPushButton('Restart')
        self._restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restart_btn.setFixedHeight(26)
        self._restart_btn.setStyleSheet(
            f'QPushButton {{ background: rgba(34,211,238,0.12); color: {ACCENT}; border: 1px solid {ACCENT}; '
            f'border-radius: 8px; padding: 2px 10px; font-size: 11px; font-weight: 700; }}'
            f'QPushButton:hover {{ background: rgba(34,211,238,0.24); }}'
        )
        self._restart_btn.clicked.connect(self._restart_worker)

        lay.addWidget(self._start_btn)
        lay.addWidget(self._stop_btn)
        lay.addWidget(self._restart_btn)
        lay.addWidget(self._fps_stat)
        lay.addWidget(self._lat_stat)
        lay.addWidget(self._status_dot)
        lay.addWidget(self._header_status)

        self._state.system_active_changed.connect(self._on_active_header)
        self._state.mode_changed.connect(self._on_mode_header)
        self._state.fps_changed.connect(self._on_fps_header)
        self._state.latency_changed.connect(self._on_latency_header)
        self._lifecycle.state_changed.connect(self._on_lifecycle_state_changed)
        return header

    def _start_worker(self) -> None:
        def _factory() -> WorkerThread:
            worker = WorkerThread(self._state, parent=self)
            worker.frame_ready.connect(self._vision.update_frame)
            worker.frame_ready.connect(self._settings_panel.update_preview_frame)
            worker.error.connect(self._on_worker_error)
            return worker

        if self._lifecycle.start(_factory):
            self._worker = self._lifecycle.worker
            self._settings_panel.set_worker(self._worker)

    def _stop_worker(self) -> None:
        stopped = self._lifecycle.stop(timeout_ms=3500)
        if not stopped:
            self._state.emit_log('--:--:--', 'ERROR', 'Pipeline stop timed out')
        self._worker = self._lifecycle.worker
        self._settings_panel.set_worker(self._worker)  # type: ignore[arg-type]

    def _restart_worker(self) -> None:
        def _factory() -> WorkerThread:
            worker = WorkerThread(self._state, parent=self)
            worker.frame_ready.connect(self._vision.update_frame)
            worker.frame_ready.connect(self._settings_panel.update_preview_frame)
            worker.error.connect(self._on_worker_error)
            return worker

        ok = self._lifecycle.restart(_factory, timeout_ms=3500)
        if not ok:
            self._state.emit_log('--:--:--', 'ERROR', 'Pipeline restart failed')
        self._worker = self._lifecycle.worker
        self._settings_panel.set_worker(self._worker)

    @pyqtSlot(bool)
    def _on_active_header(self, active: bool) -> None:
        if active:
            self._header_status.setText('ACTIVE')
            self._header_status.setStyleSheet(f'color: {ACTIVE}; font-size: 12px; font-weight: 600;')
            self._status_dot.setStyleSheet(f'color: {ACTIVE}; font-size: 12px;')
        else:
            self._header_status.setText('INACTIVE')
            self._header_status.setStyleSheet(f'color: {INACTIVE}; font-size: 12px; font-weight: 600;')
            self._status_dot.setStyleSheet(f'color: {INACTIVE}; font-size: 12px;')

    @pyqtSlot(str)
    def _on_mode_header(self, mode: str) -> None:
        colour_map = {'App Mode': MODE_APP, 'Media Mode': MODE_MEDIA, 'System Mode': MODE_SYSTEM}
        colour = colour_map.get(mode, ACCENT)
        short  = mode.replace(' Mode', '').upper() + ' MODE'
        self._header_mode.setText(short)
        self._header_mode.setStyleSheet(
            f'color: {colour}; font-size: 11px; font-weight: 700; letter-spacing: 1px; '
            f'background: rgba(56,221,248,0.12); border: 1px solid {colour}; border-radius: 12px; padding: 3px 12px;'
        )

    @pyqtSlot(float)
    def _on_fps_header(self, fps: float) -> None:
        self._fps_stat.setText(f'FPS: {fps:.0f}')

    @pyqtSlot(float)
    def _on_latency_header(self, ms: float) -> None:
        self._lat_stat.setText(f'Latency: {ms:.0f} ms')

    @pyqtSlot(str)
    def _on_worker_error(self, msg: str) -> None:
        self._state.emit_log('--:--:--', 'ERROR', msg.split('\n')[0])
        QMessageBox.critical(self, 'Pipeline Error',
                             f'The gesture pipeline encountered an error:\n\n{msg[:400]}')

    @pyqtSlot(str)
    def _on_lifecycle_state_changed(self, state: str) -> None:
        self._state.emit_log('--:--:--', 'SYSTEM', f'Lifecycle state: {state}')
        self._start_btn.setEnabled(state in {'STOPPED', 'ERROR'})
        self._stop_btn.setEnabled(state in {'RUNNING', 'STARTING'})
        self._restart_btn.setEnabled(state in {'RUNNING', 'ERROR', 'STOPPED'})

    def closeEvent(self, event: QCloseEvent) -> None:
        self._lifecycle.stop(timeout_ms=3500)
        event.accept()
