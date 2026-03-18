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

from PyQt6.QtCore    import Qt, QEvent, QTimer
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout,
)

from ui.auth_state import auth_state

_USERS_PATH   = Path(__file__).parent.parent / 'config' / 'users.json'
_MAX_ATTEMPTS = 3       # failed attempts before temporary lockout
_LOCKOUT_SECS = 10      # lockout duration in seconds
_VERSION      = 'MMGI v0.3'

# Inline stylesheets applied to _pw_container on focus events.
# Both strings must be self-contained so child widgets remain styled while
# the parent QDialog stylesheet is shadowed on the container widget.
_PW_FOCUSED = (
    'QFrame#pw_container { background:#131840; border:2px solid #00e5ff;'
    '  border-radius:9px; }'
    'QLineEdit#pw_edit { background:transparent; border:none; color:#dde8ff;'
    '  font-size:13px; padding:9px 4px 9px 12px; }'
    'QPushButton#eye_btn { background:transparent; border:none; color:#445577;'
    '  font-size:14px; padding:0 8px; min-width:34px; max-width:34px; }'
    'QPushButton#eye_btn:hover { color:#00e5ff; }'
)
_PW_NORMAL = (
    'QFrame#pw_container { background:#111630; border:1px solid #1e2a45;'
    '  border-radius:9px; }'
    'QLineEdit#pw_edit { background:transparent; border:none; color:#dde8ff;'
    '  font-size:13px; padding:9px 4px 9px 12px; }'
    'QPushButton#eye_btn { background:transparent; border:none; color:#445577;'
    '  font-size:14px; padding:0 8px; min-width:34px; max-width:34px; }'
    'QPushButton#eye_btn:hover { color:#00e5ff; }'
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


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

_QSS = """
/* Dialog: dark blue-to-deep-purple gradient background */
QDialog {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0  #07091c,
        stop:0.5 #0b0d22,
        stop:1  #130828
    );
}

/* Glass-style login card */
QFrame#card {
    background: #0e1230;
    border: 1px solid rgba(0, 229, 255, 55);
    border-radius: 16px;
}

/* Gesture logo */
QLabel#logo {
    color: #00e5ff;
    font-size: 36px;
}

/* Title */
QLabel#title {
    color: #00e5ff;
    font-size: 24px;
    font-weight: bold;
    letter-spacing: 3px;
}

/* Subtitle lines */
QLabel#sub1 {
    color: #6677aa;
    font-size: 9px;
    letter-spacing: 2px;
}
QLabel#sub2 {
    color: #4d5c88;
    font-size: 9px;
    letter-spacing: 1px;
}

/* Divider */
QFrame#divider {
    background: rgba(0, 229, 255, 30);
    max-height: 1px;
    border: none;
}

/* Field labels */
QLabel#field_lbl {
    color: #99aacc;
    font-size: 11px;
}

/* Input fields: rounded corners (9px), dark background, cyan glow on focus */
QLineEdit {
    background: #111630;
    border: 1px solid #1e2a45;
    border-radius: 9px;
    color: #dde8ff;
    font-size: 13px;
    padding: 9px 12px;
    selection-background-color: #00e5ff;
    selection-color: #07091c;
}
QLineEdit:hover:!focus {
    border: 1px solid #2c3f64;
}
QLineEdit:focus {
    border: 2px solid #00e5ff;
    background: #131840;
}

/* Password container (normal state; focus handled via _PW_FOCUSED/_PW_NORMAL) */
QFrame#pw_container {
    background: #111630;
    border: 1px solid #1e2a45;
    border-radius: 9px;
}

/* Inner QLineEdit inside pw_container -- no border, transparent background */
QLineEdit#pw_edit {
    background: transparent;
    border: none;
    border-radius: 0;
    color: #dde8ff;
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
    color: #445577;
    font-size: 14px;
    padding: 0 8px;
    min-width: 34px;
    max-width: 34px;
}
QPushButton#eye_btn:hover {
    color: #00e5ff;
}

/* Error / success message */
QLabel#msg_label {
    font-size: 11px;
}

/* Login button: cyan gradient with hover / pressed / disabled states */
QPushButton#login_btn {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #00bfd4, stop:1 #00e5ff
    );
    color: #07091c;
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
        stop:0 #33d0e8, stop:1 #55edff
    );
}
QPushButton#login_btn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #009bb5, stop:1 #00bed4
    );
}
QPushButton#login_btn:disabled {
    background: #1a2440;
    color: #3a4a68;
    letter-spacing: 0;
}

/* Version watermark */
QLabel#version_lbl {
    color: #283a5a;
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
        return login_is_enabled()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('MMGI — Login')
        self.setFixedSize(420, 520)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )

        self._users           = _load_users()
        self._attempts        = 0
        self._locked          = False
        self._pw_visible      = False
        self._countdown_val   = 0
        self._countdown_timer: QTimer | None = None
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

        lay.addSpacing(24)      # title section -> inputs: 24 px

        # -- Username ----------------------------------------------------
        u_lbl = QLabel('Username')
        u_lbl.setObjectName('field_lbl')
        lay.addWidget(u_lbl)
        lay.addSpacing(5)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText('Enter username')
        self._username_edit.returnPressed.connect(self._on_login)
        lay.addWidget(self._username_edit)

        lay.addSpacing(16)      # between fields: 16 px

        # -- Password ----------------------------------------------------
        p_lbl = QLabel('Password')
        p_lbl.setObjectName('field_lbl')
        lay.addWidget(p_lbl)
        lay.addSpacing(5)

        lay.addWidget(self._build_pw_container())

        lay.addSpacing(10)

        # -- Message (error / success / lockout) -------------------------
        self._msg_label = QLabel('')
        self._msg_label.setObjectName('msg_label')
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        self._msg_label.setFixedHeight(20)
        lay.addWidget(self._msg_label)

        lay.addSpacing(20)      # fields -> button: 20 px

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
        QTimer.singleShot(0, self._username_edit.setFocus)

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

    # ------------------------------------------------------------------
    # Login flow
    # ------------------------------------------------------------------

    def _on_login(self) -> None:
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
