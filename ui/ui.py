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

# ===========================================================================
# Colour tokens & global QSS  (was ui/styles.py)
# ===========================================================================

BG_DEEP   = '#0F0F14'
BG_CARD   = '#1A1A22'
BG_HOVER  = '#22222E'
BORDER    = '#2A2A3A'
ACCENT    = '#00E5FF'
ACTIVE    = '#00FF88'
INACTIVE  = '#FF4466'
TEXT_PRI  = '#E8E8F0'
TEXT_SEC  = '#8A8AA0'
TEXT_HINT = '#505068'

MODE_APP    = '#00E5FF'
MODE_MEDIA  = '#00BFFF'
MODE_SYSTEM = '#8A7CFF'

GLOBAL_QSS = f"""
QMainWindow, QWidget {{
    background-color: {BG_DEEP};
    color: {TEXT_PRI};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}
QScrollBar:vertical {{
    background: {BG_CARD}; width: 6px; margin: 0; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG_CARD}; height: 6px; border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 3px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QFrame#card {{
    background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 15px;
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
QPushButton#nav_btn[selected="true"] {{ background-color: rgba(0,229,255,0.12); color: {ACCENT}; font-weight: 600; }}
QProgressBar {{
    background-color: {BORDER}; border-radius: 4px; border: none; height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 4px; }}
QProgressBar#stability_bar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACTIVE}, stop:1 {ACCENT});
}}
QToolTip {{
    background-color: {BG_CARD}; color: {TEXT_PRI}; border: 1px solid {BORDER};
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
)

from ui.shared_state  import SharedState
from ui.worker_thread import WorkerThread
from utils.config     import Config
from core.adaptive_gesture_learning import (
    CustomGestureStore,
    GestureRecorder,
    GestureDataError,
)

# ---------------------------------------------------------------------------
# Gesture-map config helpers (shared across panels)
# ---------------------------------------------------------------------------

_GESTURE_MAP_PATH = Path(__file__).parent.parent / 'config' / 'gesture_map.json'

# Human-readable labels for action keys (mirrors ActionExecutor._LABELS)
_ACTION_DISPLAY_LABELS: dict[str, str] = {
    'open_brave':        'Open Browser',
    'open_apple_music':  'Open Music',
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


# ===========================================================================
# ActivityLog  (was ui/activity_log.py)
# ===========================================================================

MAX_EVENTS = 200

_CATEGORY_STYLE = {
    'ACTION': (ACCENT,    'rgba(0,229,255,0.12)'),
    'MODE':   (ACTIVE,    'rgba(0,255,136,0.12)'),
    'SYSTEM': (TEXT_SEC,  'rgba(138,138,160,0.12)'),
    'ERROR':  (INACTIVE,  'rgba(255,68,102,0.12)'),
}
_DEFAULT_STYLE = (TEXT_SEC, 'rgba(138,138,160,0.12)')


def _pill_colour(category: str) -> tuple[str, str]:
    return _CATEGORY_STYLE.get(category.upper(), _DEFAULT_STYLE)


class EventPill(QFrame):
    def __init__(self, timestamp: str, category: str, description: str) -> None:
        super().__init__()
        colour, bg = _pill_colour(category)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f'QFrame {{ background-color: {bg}; border: 1px solid {colour}33; border-radius: 21px; }}'
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(8)

        dot = QLabel('●')
        dot.setStyleSheet(f'color: {colour}; font-size: 10px; background: transparent; border: none;')
        ts_lbl = QLabel(timestamp)
        ts_lbl.setStyleSheet(f'color: {TEXT_HINT}; font-size: 11px; background: transparent; border: none;')
        cat_lbl = QLabel(category.upper())
        cat_lbl.setStyleSheet(
            f'color: {colour}; font-size: 10px; font-weight: 700; letter-spacing: 1px; background: transparent; border: none;'
        )
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(f'color: {TEXT_PRI}; font-size: 12px; background: transparent; border: none;')

        lay.addWidget(dot)
        lay.addWidget(ts_lbl)
        lay.addWidget(cat_lbl)
        lay.addWidget(desc_lbl)
        self.adjustSize()


class ActivityLog(QWidget):
    def __init__(self, state: SharedState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state  = state
        self._count  = 0
        self._pills: list[EventPill] = []
        self._build()
        state.log_event.connect(self._on_log_event)

    def _build(self) -> None:
        self.setFixedHeight(76)
        self.setStyleSheet(f'background-color: {BG_CARD}; border-top: 1px solid {BORDER};')

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
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        self._inner = QWidget()
        self._inner.setStyleSheet('background: transparent;')
        self._pills_lay = QHBoxLayout(self._inner)
        self._pills_lay.setContentsMargins(0, 0, 0, 0)
        self._pills_lay.setSpacing(8)
        self._pills_lay.addStretch()

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

    @pyqtSlot(str, str, str)
    def _on_log_event(self, timestamp: str, category: str, description: str) -> None:
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
        QTimer.singleShot(30, self._scroll_right)

    def _scroll_right(self) -> None:
        sb = self._scroll.horizontalScrollBar()
        sb.setValue(sb.maximum())


# ===========================================================================
# Sidebar  (was ui/sidebar.py)
# ===========================================================================

EXPANDED_W  = 220
COLLAPSED_W = 56
ANIM_MS     = 200

_TABS = [
    ('vision',   '◉', 'Vision'),
    ('mode',     '⊞', 'Mode'),
    ('gestures', '✋', 'Gestures'),
    ('help',     '?', 'Guide'),
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

    @staticmethod
    def _nav_btn_style(selected: bool = False) -> str:
        if selected:
            return (
                f'QPushButton {{ background-color: rgba(0,229,255,0.12); color: {ACCENT}; font-weight: 600; '
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
        self._cam_frame.setStyleSheet(
            f'QFrame#cam_frame {{ background-color: #000000; border: 2px solid {BORDER}; border-radius: 16px; }}'
        )
        cam_lay = QVBoxLayout(self._cam_frame)
        cam_lay.setContentsMargins(0, 0, 0, 0)

        self._video_label = QLabel()
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_label.setMinimumSize(480, 270)
        self._video_label.setText('⬤  Waiting for camera…')
        self._video_label.setStyleSheet(f'color: {TEXT_HINT}; font-size: 16px; background: transparent; border: none;')
        cam_lay.addWidget(self._video_label)
        root.addWidget(self._cam_frame, stretch=1)

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
            f'QFrame {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}'
        )
        fb_lay = QHBoxLayout(feedback_frame)
        fb_lay.setContentsMargins(14, 8, 14, 8)
        fb_lay.setSpacing(6)

        gest_title = QLabel('DETECTED GESTURE')
        gest_title.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;')
        self._gesture_detected_val = QLabel('—')
        self._gesture_detected_val.setStyleSheet(
            f'color: {TEXT_PRI}; font-size: 13px; font-weight: 600; background: transparent; border: none;'
        )

        sep = QLabel('|')
        sep.setStyleSheet(f'color: {BORDER}; background: transparent; border: none; margin: 0 6px;')

        action_title = QLabel('LAST ACTION')
        action_title.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;')
        self._action_executed_val = QLabel('—')
        self._action_executed_val.setStyleSheet(
            f'color: {ACTIVE}; font-size: 13px; font-weight: 600; background: transparent; border: none;'
        )

        sep2 = QLabel('|')
        sep2.setStyleSheet(f'color: {BORDER}; background: transparent; border: none; margin: 0 6px;')

        auth_title = QLabel('FACE AUTH')
        auth_title.setStyleSheet(f'color: {TEXT_HINT}; font-size: 10px; letter-spacing: 1px; background: transparent; border: none;')
        self._face_auth_val = QLabel('Face Auth: Idle')
        self._face_auth_val.setStyleSheet(
            f'color: {TEXT_SEC}; font-size: 13px; font-weight: 600; background: transparent; border: none;'
        )

        fb_lay.addWidget(gest_title)
        fb_lay.addWidget(self._gesture_detected_val)
        fb_lay.addWidget(sep)
        fb_lay.addWidget(action_title)
        fb_lay.addWidget(self._action_executed_val)
        fb_lay.addWidget(sep2)
        fb_lay.addWidget(auth_title)
        fb_lay.addWidget(self._face_auth_val)
        fb_lay.addStretch()
        root.addWidget(feedback_frame)

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

    def _connect_state(self) -> None:
        s = self._state
        s.mode_changed.connect(self._on_mode_changed)
        s.gesture_changed.connect(self._on_gesture_changed)
        s.mode_stability_changed.connect(self._on_stability_changed)
        s.system_active_changed.connect(self._on_active_changed)
        s.action_executed.connect(self._on_action_executed)
        s.face_auth_changed.connect(self._on_face_auth_changed)

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
        self._gesture_detected_val.setText(gesture if gesture else '—')

    @pyqtSlot(str)
    def _on_action_executed(self, action: str) -> None:
        label = _ACTION_DISPLAY_LABELS.get(action, action)
        self._action_executed_val.setText(label if label else '—')

    @pyqtSlot(bool, str)
    def _on_face_auth_changed(self, authorized: bool, status_text: str) -> None:
        self._face_auth_val.setText(status_text if status_text else 'Face Auth: Idle')
        colour = ACTIVE if authorized else INACTIVE
        self._face_auth_val.setStyleSheet(
            f'color: {colour}; font-size: 13px; font-weight: 600; background: transparent; border: none;'
        )

    @pyqtSlot(float)
    def _on_stability_changed(self, progress: float) -> None:
        self._stability_bar.setValue(int(progress * 100))

    @pyqtSlot(bool)
    def _on_active_changed(self, active: bool) -> None:
        colour = _MODE_ACCENT.get(self._current_mode, ACCENT) if active else BORDER
        self._cam_frame.setStyleSheet(
            f'QFrame#cam_frame {{ background-color: #000000; border: 2px solid {colour}; border-radius: 16px; }}'
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
        colour = ACTIVE if authorized else INACTIVE
        self._auth_lbl.setText(status_text if status_text else 'Face Auth: Idle (System Mode Only)')
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

        # Stack: index 0 = main view, index 1 = gesture mapping, index 2 = help
        self._body_stack = QStackedWidget()
        self._body_stack.addWidget(main_view)
        self._body_stack.addWidget(self._gesture_map_panel)
        self._body_stack.addWidget(self._help_panel)

        body.addWidget(self._sidebar)
        body.addWidget(self._body_stack, stretch=1)
        root.addLayout(body, stretch=1)

        self._activity = ActivityLog(self._state)
        root.addWidget(self._activity)

    @pyqtSlot(str)
    def _on_tab_selected(self, tab_id: str) -> None:
        if tab_id == 'gestures':
            self._gesture_map_panel.reload()
            self._body_stack.setCurrentIndex(1)
            self._activity.setVisible(False)
        elif tab_id == 'help':
            self._help_panel.refresh()
            self._body_stack.setCurrentIndex(2)
            self._activity.setVisible(False)
        else:
            self._body_stack.setCurrentIndex(0)
            self._activity.setVisible(True)

    @pyqtSlot()
    def _on_mapping_changed(self) -> None:
        """Refresh the gesture guide card after a mapping is saved."""
        self._sys_panel.refresh_mappings()
        self._help_panel.refresh()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f'background-color: {BG_CARD}; border-bottom: 1px solid {BORDER};')
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        dot = QLabel('◉')
        dot.setStyleSheet(f'color: {ACCENT}; font-size: 14px;')
        self._header_dot = dot

        title = QLabel('MMGI')
        title.setStyleSheet(f'color: {ACCENT}; font-size: 15px; font-weight: 700; letter-spacing: 3px;')

        subtitle = QLabel('Smart Mode AI Controller')
        subtitle.setStyleSheet(f'color: {TEXT_HINT}; font-size: 12px;')

        self._header_status = QLabel('⬤  INACTIVE')
        self._header_status.setStyleSheet(f'color: {INACTIVE}; font-size: 12px; font-weight: 600;')

        self._header_mode = QLabel('APP MODE')
        self._header_mode.setStyleSheet(
            f'color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 1px; '
            f'background: rgba(0,229,255,0.10); border: 1px solid {ACCENT}; border-radius: 10px; padding: 2px 10px;'
        )

        lay.addWidget(dot)
        lay.addWidget(title)
        lay.addWidget(subtitle)
        lay.addStretch()
        lay.addWidget(self._header_mode)
        lay.addWidget(self._header_status)

        self._state.system_active_changed.connect(self._on_active_header)
        self._state.mode_changed.connect(self._on_mode_header)
        return header

    def _start_worker(self) -> None:
        self._worker = WorkerThread(self._state, parent=self)
        self._worker.frame_ready.connect(self._vision.update_frame)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    @pyqtSlot(bool)
    def _on_active_header(self, active: bool) -> None:
        if active:
            self._header_status.setText('⬤  ACTIVE')
            self._header_status.setStyleSheet(f'color: {ACTIVE}; font-size: 12px; font-weight: 600;')
        else:
            self._header_status.setText('⬤  INACTIVE')
            self._header_status.setStyleSheet(f'color: {INACTIVE}; font-size: 12px; font-weight: 600;')

    @pyqtSlot(str)
    def _on_mode_header(self, mode: str) -> None:
        colour_map = {'App Mode': MODE_APP, 'Media Mode': MODE_MEDIA, 'System Mode': MODE_SYSTEM}
        colour = colour_map.get(mode, ACCENT)
        short  = mode.replace(' Mode', '').upper() + ' MODE'
        self._header_mode.setText(short)
        self._header_mode.setStyleSheet(
            f'color: {colour}; font-size: 11px; font-weight: 700; letter-spacing: 1px; '
            f'background: rgba(0,229,255,0.10); border: 1px solid {colour}; border-radius: 10px; padding: 2px 10px;'
        )

    @pyqtSlot(str)
    def _on_worker_error(self, msg: str) -> None:
        self._state.emit_log('--:--:--', 'ERROR', msg.split('\n')[0])
        QMessageBox.critical(self, 'Pipeline Error',
                             f'The gesture pipeline encountered an error:\n\n{msg[:400]}')

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        event.accept()
