"""
Module: login_window.py
Description: Optional login dialog shown before the main MMGI dashboard.
             Credentials are loaded from config/users.json; passwords are
             stored as bcrypt hashes (legacy SHA-256 hashes are auto-migrated).
Author: Pratham Chaturvedi

Behaviour
---------
* If config/users.json is missing or ``"enabled": false``, login is skipped
  and this module returns Accepted immediately.
* Password visibility can be toggled with the eye button inside the field.
* On incorrect credentials a red error message is shown below the password
  field; the dialog stays open so the user can retry.
* After 3 consecutive failures the Login button is disabled for 10 seconds
  (live countdown displayed -- brute-force throttle).
* Username field is auto-focused when the window opens.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bcrypt
import cv2
import numpy as np

from PyQt6.QtCore    import Qt, QEvent, QTimer
from PyQt6.QtGui     import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QStackedWidget, QWidget,
)

from ui.auth_state import auth_state
from core.face_security import FaceSecurityManager

_USERS_PATH   = Path(__file__).parent.parent / 'config' / 'users.json'
_FACE_SECURITY_PATH = Path(__file__).parent.parent / 'config' / 'face_security.json'
_MAX_ATTEMPTS = 3       # failed attempts before temporary lockout
_LOCKOUT_SECS = 10      # lockout duration in seconds
_VERSION      = 'MMGI v0.3'

# Inline stylesheets applied to _pw_container on focus events.
# Both strings must be self-contained so child widgets remain styled while
# the parent QDialog stylesheet is shadowed on the container widget.
_PW_FOCUSED = (
    'QFrame#pw_container { background:#172743; border:2px solid #22d3ee;'
    '  border-radius:9px; }'
    'QLineEdit#pw_edit { background:transparent; border:none; color:#e6eef9;'
    '  font-size:13px; padding:9px 4px 9px 12px; }'
    'QPushButton#eye_btn { background:transparent; border:none; color:#6b7b96;'
    '  font-size:14px; padding:0 8px; min-width:34px; max-width:34px; }'
    'QPushButton#eye_btn:hover { color:#22d3ee; }'
)
_PW_NORMAL = (
    'QFrame#pw_container { background:#111d33; border:1px solid #243350;'
    '  border-radius:9px; }'
    'QLineEdit#pw_edit { background:transparent; border:none; color:#e6eef9;'
    '  font-size:13px; padding:9px 4px 9px 12px; }'
    'QPushButton#eye_btn { background:transparent; border:none; color:#6b7b96;'
    '  font-size:14px; padding:0 8px; min-width:34px; max-width:34px; }'
    'QPushButton#eye_btn:hover { color:#22d3ee; }'
)


def _hash_pw_legacy(password: str) -> str:
    """Return the legacy SHA-256 hex digest used in older user files."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _is_bcrypt_hash(value: str) -> bool:
    return value.startswith(('$2a$', '$2b$', '$2y$'))


def _hash_pw_bcrypt(password: str) -> str:
    """Return bcrypt hash for password."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(password: str, stored_hash: str) -> tuple[bool, bool]:
    """
    Verify a password against stored hash.

    Returns:
        (is_valid, needs_upgrade)
        needs_upgrade=True means legacy SHA-256 matched and should be migrated.
    """
    if not stored_hash:
        return False, False

    if _is_bcrypt_hash(stored_hash):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')), False
        except ValueError:
            return False, False

    return _hash_pw_legacy(password) == stored_hash, True


def _load_users() -> dict:
    """Load users.json. Returns an empty dict on any error."""
    try:
        with open(_USERS_PATH, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def login_is_enabled() -> bool:
    """Return True when the login screen should be shown."""
    return bool(_load_users().get('enabled', False))


def _load_face_security_cfg() -> dict:
    cfg = {
        'enabled': True,
        'authorized_image_path': 'config/authorized_face.jpg',
        'authorized_encoding_path': 'config/authorized_face_encoding.json',
        'similarity_threshold': 0.84,
        'min_detection_confidence': 0.6,
        'eval_interval_s': 0.08,
    }
    try:
        with open(_FACE_SECURITY_PATH, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            cfg.update(raw)
    except Exception:
        pass
    return cfg


def face_login_is_enabled() -> bool:
    return bool(_load_face_security_cfg().get('enabled', True))


def _is_strong_face_match(
    similarity: float | None,
    minimum_similarity: float,
) -> bool:
    """Return True only for a high-confidence similarity match."""
    if similarity is None:
        return False
    return float(similarity) >= float(minimum_similarity)


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

_QSS = """
/* Dialog: refined deep-navy gradient */
QDialog {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0  #070f1f,
        stop:0.55 #0b1426,
        stop:1  #111a2f
    );
}

/* Glass-style login card */
QFrame#card {
    background: #101c31;
    border: 1px solid rgba(34, 211, 238, 75);
    border-radius: 18px;
}

/* Gesture logo */
QLabel#logo {
    color: #22d3ee;
    font-size: 36px;
}

/* Title */
QLabel#title {
    color: #22d3ee;
    font-size: 25px;
    font-weight: 800;
    letter-spacing: 5px;
}

/* Subtitle lines */
QLabel#sub1 {
    color: #a5b4cc;
    font-size: 10px;
    letter-spacing: 2px;
}
QLabel#sub2 {
    color: #6b7b96;
    font-size: 10px;
    letter-spacing: 1px;
}

/* Divider */
QFrame#divider {
    background: rgba(34, 211, 238, 40);
    max-height: 1px;
    border: none;
}

/* Field labels */
QLabel#field_lbl {
    color: #b7c5d9;
    font-size: 11px;
}

/* Input fields: rounded corners (9px), dark background, cyan glow on focus */
QLineEdit {
    background: #111d33;
    border: 1px solid #243350;
    border-radius: 9px;
    color: #e6eef9;
    font-size: 13px;
    padding: 9px 12px;
    selection-background-color: #22d3ee;
    selection-color: #090e1a;
}
QLineEdit:hover:!focus {
    border: 1px solid #35527d;
}
QLineEdit:focus {
    border: 2px solid #22d3ee;
    background: #172743;
}

/* Password container (normal state; focus handled via _PW_FOCUSED/_PW_NORMAL) */
QFrame#pw_container {
    background: #111d33;
    border: 1px solid #243350;
    border-radius: 9px;
}

/* Inner QLineEdit inside pw_container -- no border, transparent background */
QLineEdit#pw_edit {
    background: transparent;
    border: none;
    border-radius: 0;
    color: #e6eef9;
    font-size: 13px;
    padding: 9px 4px 9px 12px;
}
QLineEdit#pw_edit:focus {
    border: none;
    background: transparent;
}

/* Password visibility toggle button */
QPushButton#eye_btn {
    background: transparent;
    border: none;
    color: #6b7b96;
    font-size: 14px;
    padding: 0 8px;
    min-width: 34px;
    max-width: 34px;
}
QPushButton#eye_btn:hover {
    color: #22d3ee;
}

/* Error / success message */
QLabel#msg_label {
    font-size: 11px;
}

/* Login button: cyan gradient with hover / pressed / disabled states */
QPushButton#login_btn {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #22d3ee, stop:1 #60a5fa
    );
    color: #061224;
    border: none;
    border-radius: 9px;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 11px 0;
}
QPushButton#login_btn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #3fddf6, stop:1 #7db8ff
    );
}
QPushButton#login_btn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #1ea7bd, stop:1 #4d83cd
    );
}
QPushButton#login_btn:disabled {
    background: #1b2941;
    color: #5f7392;
    letter-spacing: 0;
}

/* Version watermark */
QLabel#version_lbl {
    color: #4a6082;
    font-size: 10px;
    letter-spacing: 1px;
}
"""


class LoginWindow(QDialog):
    """
    Styled login dialog gating access to the MMGI dashboard.

    Credentials are loaded from config/users.json; passwords are stored as
    bcrypt hashes (never in plain-text). Closing or cancelling the dialog
    returns ``QDialog.DialogCode.Rejected``.

    Improvements over the original
    --------------------------------
    - Dark gradient background + glass-style card (glassmorphism aesthetic)
    - Gesture/AI logo above the title (hand emoji)
    - Three-line header: MMGI / MULTI-MODAL... / Touch-Free Desktop Control...
    - Password show/hide eye toggle (circle symbol changes state)
    - "Logging in..." loading state while authenticating
    - Detailed error messages with remaining attempt counter (prefix)
    - 10-second live-countdown lockout after 3 failed attempts
    - Auto-focus on username field when dialog opens
    - Full keyboard navigation: Tab between fields, Enter triggers login
    - Cyan glow border on pw_container when pw_edit is focused (eventFilter)
    - Consistent 24 / 16 / 20 px spacing across sections
    - Version watermark at card bottom
    """

    @staticmethod
    def should_show() -> bool:
        """Return True when the login screen is enabled in users.json."""
        return login_is_enabled() or face_login_is_enabled()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('MMGI — Login')
        self.setFixedSize(460, 640)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )

        self._users           = _load_users()
        self._face_cfg        = _load_face_security_cfg()
        self._attempts        = 0
        self._locked          = False
        self._pw_visible      = False
        self._countdown_val   = 0
        self._countdown_timer: QTimer | None = None
        self._auth_mode       = 'password'
        self._face_timer: QTimer | None = None
        self._face_cap = None
        self._face_security: FaceSecurityManager | None = None
        self._face_armed = False
        self._face_match_streak = 0
        base_threshold = float(self._face_cfg.get('similarity_threshold', 0.84))
        self._face_login_similarity_threshold = float(
            self._face_cfg.get('login_similarity_threshold', max(0.93, base_threshold))
        )
        self._face_required_match_streak = max(
            1,
            int(self._face_cfg.get('login_required_match_streak', 3)),
        )
        self._face_guard_threshold = float(
            self._face_cfg.get('login_lbph_confidence_threshold', 68.0)
        )
        self._face_similarity_override_threshold = float(
            self._face_cfg.get('login_similarity_override_threshold', 0.975)
        )
        self._face_override_required_match_streak = max(
            self._face_required_match_streak,
            int(self._face_cfg.get('login_override_required_match_streak', 5)),
        )
        self._face_guard_model = None
        self._face_guard_ready = False
        cascade_path = Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'
        self._face_guard_cascade = cv2.CascadeClassifier(str(cascade_path))
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)

        # -- Glass card --------------------------------------------------
        card = QFrame()
        card.setObjectName('card')
        outer.addWidget(card, 1)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(36, 28, 36, 22)
        lay.setSpacing(0)

        # -- Logo (gesture icon) -----------------------------------------
        logo = QLabel('✋')
        logo.setObjectName('logo')
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo)

        lay.addSpacing(6)

        # -- Title -------------------------------------------------------
        title = QLabel('MMGI')
        title.setObjectName('title')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        lay.addSpacing(6)   # title -> sub1: 6-8 px

        sub1 = QLabel('MULTI-MODAL GESTURE INTELLIGENCE')
        sub1.setObjectName('sub1')
        sub1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub1)

        lay.addSpacing(4)

        sub2 = QLabel('Touch-Free Desktop Control System')
        sub2.setObjectName('sub2')
        sub2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(sub2)

        lay.addSpacing(18)

        div = QFrame()
        div.setObjectName('divider')
        lay.addWidget(div)

        lay.addSpacing(16)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._pw_mode_btn = QPushButton('User-Password')
        self._face_mode_btn = QPushButton('Face Recognition')
        for btn in (self._pw_mode_btn, self._face_mode_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setStyleSheet(self._auth_mode_btn_style(active=False))
        self._pw_mode_btn.clicked.connect(lambda: self._select_auth_mode('password'))
        self._face_mode_btn.clicked.connect(lambda: self._select_auth_mode('face'))
        mode_row.addWidget(self._pw_mode_btn)
        mode_row.addWidget(self._face_mode_btn)
        lay.addLayout(mode_row)

        lay.addSpacing(14)

        self._auth_stack = QStackedWidget()

        # -- Password panel ---------------------------------------------
        pw_panel = QWidget()
        pw_lay = QVBoxLayout(pw_panel)
        pw_lay.setContentsMargins(0, 0, 0, 0)
        pw_lay.setSpacing(0)

        u_lbl = QLabel('Username')
        u_lbl.setObjectName('field_lbl')
        pw_lay.addWidget(u_lbl)
        pw_lay.addSpacing(5)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText('Enter username')
        self._username_edit.returnPressed.connect(self._on_login)
        pw_lay.addWidget(self._username_edit)

        pw_lay.addSpacing(16)

        p_lbl = QLabel('Password')
        p_lbl.setObjectName('field_lbl')
        pw_lay.addWidget(p_lbl)
        pw_lay.addSpacing(5)
        pw_lay.addWidget(self._build_pw_container())

        # -- Face panel --------------------------------------------------
        face_panel = QWidget()
        face_lay = QVBoxLayout(face_panel)
        face_lay.setContentsMargins(0, 0, 0, 0)
        face_lay.setSpacing(8)

        self._face_preview = QLabel('Camera preview not started')
        self._face_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._face_preview.setFixedHeight(220)
        self._face_preview.setStyleSheet('background:#0d162b; border:1px solid #243350; border-radius:10px; color:#6b7b96;')
        face_lay.addWidget(self._face_preview)

        self._face_status_lbl = QLabel('Press "Login with Face" and look at camera.')
        self._face_status_lbl.setWordWrap(True)
        self._face_status_lbl.setStyleSheet('color:#a5b4cc; font-size:11px;')
        face_lay.addWidget(self._face_status_lbl)

        self._face_login_btn = QPushButton('Login with Face')
        self._face_login_btn.setObjectName('login_btn')
        self._face_login_btn.clicked.connect(self._on_face_login)
        face_lay.addWidget(self._face_login_btn)

        self._auth_stack.addWidget(pw_panel)
        self._auth_stack.addWidget(face_panel)
        lay.addWidget(self._auth_stack)

        lay.addSpacing(10)

        # -- Message (error / success / lockout) -------------------------
        self._msg_label = QLabel('')
        self._msg_label.setObjectName('msg_label')
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        self._msg_label.setFixedHeight(20)
        lay.addWidget(self._msg_label)

        lay.addSpacing(8)

        # -- Login button ------------------------------------------------
        self._login_btn = QPushButton('Login')
        self._login_btn.setObjectName('login_btn')
        self._login_btn.clicked.connect(self._on_login)
        lay.addWidget(self._login_btn)

        lay.addSpacing(14)

        # -- Version watermark -------------------------------------------
        ver = QLabel(_VERSION)
        ver.setObjectName('version_lbl')
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ver)

        # -- Tab order ---------------------------------------------------
        self.setTabOrder(self._username_edit, self._pw_edit)
        self.setTabOrder(self._pw_edit, self._eye_btn)
        self.setTabOrder(self._eye_btn, self._login_btn)
        self._select_auth_mode('password')

    def _build_pw_container(self) -> QFrame:
        """Return a styled frame containing the password field + eye toggle."""
        self._pw_container = QFrame()
        self._pw_container.setObjectName('pw_container')
        self._pw_container.setStyleSheet(_PW_NORMAL)

        row = QHBoxLayout(self._pw_container)
        row.setContentsMargins(0, 0, 4, 0)
        row.setSpacing(0)

        self._pw_edit = QLineEdit()
        self._pw_edit.setObjectName('pw_edit')
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_edit.setPlaceholderText('Enter password')
        self._pw_edit.returnPressed.connect(self._on_login)
        self._pw_edit.installEventFilter(self)  # drives container focus glow
        row.addWidget(self._pw_edit)

        self._eye_btn = QPushButton('◉')   # filled circle = password hidden
        self._eye_btn.setObjectName('eye_btn')
        self._eye_btn.setFixedSize(34, 34)
        self._eye_btn.setToolTip('Show / hide password')
        self._eye_btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._eye_btn.clicked.connect(self._toggle_pw_visibility)
        row.addWidget(self._eye_btn)

        return self._pw_container

    # ------------------------------------------------------------------
    # Event filter: cyan border on pw_container while pw_edit has focus
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self._pw_edit:
            if event.type() == QEvent.Type.FocusIn:
                self._pw_container.setStyleSheet(_PW_FOCUSED)
            elif event.type() == QEvent.Type.FocusOut:
                self._pw_container.setStyleSheet(_PW_NORMAL)
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Auto-focus username field when dialog is shown
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._auth_mode == 'password':
            QTimer.singleShot(0, self._username_edit.setFocus)
        else:
            self._start_face_stream()

    # ------------------------------------------------------------------
    # Password visibility toggle
    # ------------------------------------------------------------------

    def _toggle_pw_visibility(self) -> None:
        self._pw_visible = not self._pw_visible
        if self._pw_visible:
            self._pw_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._eye_btn.setText('◎')   # open bull's-eye = visible
        else:
            self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._eye_btn.setText('◉')   # filled circle  = hidden

    @staticmethod
    def _auth_mode_btn_style(active: bool) -> str:
        if active:
            return (
                'QPushButton { background:#22d3ee; color:#061224; border:1px solid #22d3ee; '
                'border-radius:8px; font-size:12px; font-weight:700; }'
            )
        return (
            'QPushButton { background:#111d33; color:#a5b4cc; border:1px solid #243350; '
            'border-radius:8px; font-size:12px; font-weight:600; }'
            'QPushButton:hover { border:1px solid #22d3ee; color:#22d3ee; }'
        )

    def _select_auth_mode(self, mode: str) -> None:
        self._auth_mode = mode
        is_pw = mode == 'password'
        self._auth_stack.setCurrentIndex(0 if is_pw else 1)
        self._login_btn.setVisible(is_pw)

        if is_pw:
            self._pw_mode_btn.setStyleSheet(self._auth_mode_btn_style(active=True))
            self._face_mode_btn.setStyleSheet(self._auth_mode_btn_style(active=False))
            self._stop_face_stream()
            self._face_armed = False
            self._msg_label.setText('')
            self._username_edit.setFocus()
            return

        self._face_mode_btn.setStyleSheet(self._auth_mode_btn_style(active=True))
        self._pw_mode_btn.setStyleSheet(self._auth_mode_btn_style(active=False))
        self._start_face_stream()

    def _start_face_stream(self) -> None:
        if not bool(self._face_cfg.get('enabled', True)):
            self._face_login_btn.setEnabled(False)
            self._face_status_lbl.setText('Face login is disabled in settings.')
            return

        if self._face_cap is None:
            self._face_cap = cv2.VideoCapture(0)
        if self._face_timer is None:
            self._face_timer = QTimer(self)
            self._face_timer.setInterval(120)
            self._face_timer.timeout.connect(self._on_face_tick)

        if self._face_security is None:
            self._face_security = FaceSecurityManager(
                enabled=True,
                authorized_image_path=str(self._face_cfg.get('authorized_image_path', 'config/authorized_face.jpg')),
                authorized_encoding_path=str(self._face_cfg.get('authorized_encoding_path', 'config/authorized_face_encoding.json')),
                similarity_threshold=float(self._face_cfg.get('similarity_threshold', 0.84)),
                min_detection_confidence=float(self._face_cfg.get('min_detection_confidence', 0.6)),
                eval_interval_s=float(self._face_cfg.get('eval_interval_s', 0.08)),
            )
        self._prepare_face_guard_model()

        self._face_login_btn.setEnabled(True)
        if self._face_timer is not None and not self._face_timer.isActive():
            self._face_timer.start()

    def _prepare_face_guard_model(self) -> None:
        self._face_guard_ready = False
        self._face_guard_model = None

        if not hasattr(cv2, 'face') or not hasattr(cv2.face, 'LBPHFaceRecognizer_create'):
            return
        if self._face_guard_cascade.empty():
            return

        root = Path(__file__).parent.parent
        authorized_path = Path(str(self._face_cfg.get('authorized_image_path', 'config/authorized_face.jpg')))
        if not authorized_path.is_absolute():
            authorized_path = root / authorized_path
        if not authorized_path.exists():
            return

        ref_img = cv2.imread(str(authorized_path))
        if ref_img is None:
            return

        ref_face = self._extract_face_for_guard(ref_img)
        if ref_face is None:
            return

        model = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        aug_1 = cv2.convertScaleAbs(ref_face, alpha=1.0, beta=8)
        aug_2 = cv2.convertScaleAbs(ref_face, alpha=0.92, beta=-4)
        images = [ref_face, aug_1, aug_2]
        labels = np.array([1, 1, 1], dtype=np.int32)
        model.train(images, labels)

        self._face_guard_model = model
        self._face_guard_ready = True

    def _extract_face_for_guard(self, frame_bgr):
        if frame_bgr is None or self._face_guard_cascade.empty():
            return None

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._face_guard_cascade.detectMultiScale(
            gray,
            scaleFactor=1.12,
            minNeighbors=5,
            minSize=(44, 44),
        )
        if len(faces) == 0:
            return None

        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(gray.shape[1], int(x + w))
        y2 = min(gray.shape[0], int(y + h))
        roi = gray[y1:y2, x1:x2]
        if roi is None or roi.size == 0:
            return None

        roi = cv2.resize(roi, (128, 128), interpolation=cv2.INTER_AREA)
        roi = cv2.equalizeHist(roi)
        return roi

    def _stop_face_stream(self) -> None:
        if self._face_timer is not None and self._face_timer.isActive():
            self._face_timer.stop()
        if self._face_cap is not None:
            self._face_cap.release()
            self._face_cap = None
        if self._face_security is not None:
            self._face_security.close()
            self._face_security = None

    def _on_face_login(self) -> None:
        if not bool(self._face_cfg.get('enabled', True)):
            self._face_status_lbl.setText('Face login is disabled. Enable it from Settings.')
            return
        if not self._face_guard_ready or self._face_guard_model is None:
            self._face_status_lbl.setText('Face guard not ready. Re-capture authorized face from Settings.')
            return
        if self._face_security is None or not self._face_security.has_reference:
            self._face_status_lbl.setText('No authorized face enrolled yet. Use Settings -> Security to capture face.')
            return
        self._face_armed = True
        self._face_match_streak = 0
        self._face_status_lbl.setText('Scanning... keep your face centered and well lit.')

    def _on_face_tick(self) -> None:
        if self._face_cap is None or self._face_security is None:
            return

        ok, frame = self._face_cap.read()
        if not ok or frame is None:
            self._face_status_lbl.setText('Camera unavailable. Please check webcam access.')
            return

        frame = cv2.flip(frame, 1)
        result = self._face_security.evaluate(frame)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self._face_preview.width(),
            self._face_preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._face_preview.setPixmap(pix)

        if 'No Authorized Face Registered' in result.status_text:
            self._face_status_lbl.setText('No authorized face enrolled yet. Use Settings -> Security to capture face.')
            self._face_armed = False
            self._face_match_streak = 0
            return

        strong_match = result.is_authorized and _is_strong_face_match(
            result.similarity,
            self._face_login_similarity_threshold,
        )

        if not self._face_armed:
            if strong_match:
                self._face_status_lbl.setText('Authorized face detected. Press "Login with Face" to continue.')
            else:
                self._face_status_lbl.setText(result.status_text)
            self._face_match_streak = 0
            return

        if strong_match:
            if self._face_guard_model is None:
                self._face_match_streak = 0
                self._face_status_lbl.setText('Face guard unavailable. Try restarting after re-enrolling face.')
                return

            guard_face = self._extract_face_for_guard(frame)
            if guard_face is None:
                self._face_match_streak = 0
                self._face_status_lbl.setText('Face not clear for verification. Keep face centered.')
                return

            predicted_label, confidence = self._face_guard_model.predict(guard_face)
            lbph_ok = predicted_label == 1 and float(confidence) <= self._face_guard_threshold
            similarity_override_ok = (
                result.similarity is not None
                and float(result.similarity) >= self._face_similarity_override_threshold
            )
            if not lbph_ok and not similarity_override_ok:
                self._face_match_streak = 0
                self._face_status_lbl.setText('Face not authorized. Access denied.')
                return

            self._face_match_streak += 1
            required = self._face_required_match_streak if lbph_ok else self._face_override_required_match_streak
            if self._face_match_streak < required:
                if lbph_ok:
                    self._face_status_lbl.setText(
                        f'Verifying identity... {self._face_match_streak}/{required}'
                    )
                else:
                    self._face_status_lbl.setText(
                        f'High similarity detected. Extra verification... {self._face_match_streak}/{required}'
                    )
                return

            auth_state.set_authenticated('face-user')
            self._face_status_lbl.setText('Access granted by face recognition.')
            self._face_armed = False
            self._face_match_streak = 0
            QTimer.singleShot(250, self.accept)
            return

        self._face_match_streak = 0
        if result.face_detected:
            self._face_status_lbl.setText('Face not authorized. Access denied.')
        else:
            self._face_status_lbl.setText(result.status_text)

    # ------------------------------------------------------------------
    # Login flow
    # ------------------------------------------------------------------

    def _on_login(self) -> None:
        if self._auth_mode != 'password':
            return
        if self._locked:
            return

        username = self._username_edit.text().strip()
        password = self._pw_edit.text()

        if not username or not password:
            self._show_error('❌  Please enter both username and password.')
            return

        self._set_loading(True)
        self._msg_label.setText('')
        self._authenticate(username, password)

    def _authenticate(self, username: str, password: str) -> None:
        """Validate credentials and establish authenticated runtime session."""
        stored_user = self._users.get('username', '')
        stored_hash = self._users.get('password', '')

        valid_password, needs_upgrade = _verify_password(password, stored_hash)

        if username == stored_user and valid_password:
            if needs_upgrade:
                self._users['password'] = _hash_pw_bcrypt(password)
                self._save_users()

            auth_state.set_authenticated(username)
            self._show_success('✓  Access granted.')
            QTimer.singleShot(400, self.accept)
        else:
            auth_state.reset()
            self._set_loading(False)
            self._attempts += 1
            remaining = _MAX_ATTEMPTS - self._attempts
            if remaining > 0:
                self._show_error(
                    f'❌  Invalid username or password. '
                    f'{remaining} attempt(s) remaining.'
                )
            else:
                self._lock_temporarily()

    def _save_users(self) -> None:
        """Persist user file updates (used for hash migration)."""
        try:
            with open(_USERS_PATH, 'w', encoding='utf-8') as fh:
                json.dump(self._users, fh, indent=4)
        except Exception:
            pass

    def _set_loading(self, loading: bool) -> None:
        self._login_btn.setEnabled(not loading)
        self._login_btn.setText('Logging in...' if loading else 'Login')

    def _show_error(self, message: str) -> None:
        self._msg_label.setStyleSheet('color: #ff4466; font-size: 11px;')
        self._msg_label.setText(message)

    def _show_success(self, message: str) -> None:
        self._msg_label.setStyleSheet('color: #00ff88; font-size: 11px;')
        self._msg_label.setText(message)

    # ------------------------------------------------------------------
    # Brute-force throttle with live countdown
    # ------------------------------------------------------------------

    def _lock_temporarily(self) -> None:
        """Disable login for _LOCKOUT_SECS seconds, showing a live countdown."""
        self._locked = True
        self._login_btn.setEnabled(False)
        self._countdown_val = _LOCKOUT_SECS
        self._update_lockout_msg()

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._countdown_timer.start()

    def _tick_countdown(self) -> None:
        self._countdown_val -= 1
        if self._countdown_val <= 0:
            if self._countdown_timer:
                self._countdown_timer.stop()
            self._unlock()
        else:
            self._update_lockout_msg()

    def _update_lockout_msg(self) -> None:
        self._show_error(
            f'Too many attempts. Try again in {self._countdown_val}s.'
        )

    def _unlock(self) -> None:
        self._locked    = False
        self._attempts  = 0
        self._login_btn.setEnabled(True)
        self._login_btn.setText('Login')
        self._msg_label.setText('')
        self._pw_edit.clear()
        self._pw_edit.setFocus()

    def done(self, result: int) -> None:
        self._stop_face_stream()
        super().done(result)
