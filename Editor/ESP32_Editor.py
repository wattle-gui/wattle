#!/usr/bin/env python3
"""Wattle Editor: the screen designer for Wattle."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if sys.platform.startswith("linux"):               # Linux only: Windows has its own window system
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    os.environ.setdefault("GTK_MODULES", "")
    os.environ.setdefault("GTK_PATH", "")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ESD_INSTANCE_KEY = "esd-single-instance"


def _esd_lock_path() -> str:
    from PyQt6.QtCore import QStandardPaths

    root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.RuntimeLocation
    )
    if not root:
        root = tempfile.gettempdir()
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "esd-single-instance.lock")


def _ask_running_esd_to_raise() -> bool:
    from PyQt6.QtNetwork import QLocalSocket

    sock = QLocalSocket()
    sock.connectToServer(ESD_INSTANCE_KEY)
    if not sock.waitForConnected(400):
        return False
    sock.write(b"raise\n")
    sock.waitForBytesWritten(400)
    sock.disconnectFromServer()
    return True


def _start_esd_instance_server(window):
    from PyQt6.QtNetwork import QLocalServer

    QLocalServer.removeServer(ESD_INSTANCE_KEY)
    server = QLocalServer(window)
    if not server.listen(ESD_INSTANCE_KEY):
        QLocalServer.removeServer(ESD_INSTANCE_KEY)
        server.listen(ESD_INSTANCE_KEY)

    def _on_second_launch():
        client = server.nextPendingConnection()
        if client is not None:
            client.close()
        window.raise_existing_window()

    server.newConnection.connect(_on_second_launch)
    return server


def main() -> int:
    from PyQt6.QtCore import QLockFile, Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication, QMessageBox

    if os.environ.get("WATTLE_REPLAY") and os.environ.pop("WATTLE_RECORD", None):
        # Recording starts by emptying its file -- if WATTLE_RECORD is left set from an
        # earlier session (exported variables outlive the command that needed them), a replay
        # launch would otherwise wipe out the very recording it's about to read, before it
        # even gets a chance to read it. Replaying always wins over an accidentally-still-set
        # recording variable.
        print("WATTLE_REPLAY is set -- ignoring WATTLE_RECORD for this launch (it was still "
              "set from an earlier session and would have erased the recording being replayed).")

    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Wattle")
    app.setApplicationDisplayName("Wattle Editor")
    QGuiApplication.setDesktopFileName("esp32-editor")
    try:
        from wattle_theme import apply_theme
        from wattle_tools import install_soft_quit_signals

        apply_theme(app)
        install_soft_quit_signals()
    except Exception:
        pass

    if _ask_running_esd_to_raise():
        if os.environ.get("WATTLE_RECORD") or os.environ.get("WATTLE_REPLAY"):
            # The Editor that is already open was NOT started for recording or replaying, so this launch
            # cannot do its job. Say so (it used to hand over silently, and the recording was never made).
            QMessageBox.information(
                None, "Wattle Editor",
                "The Wattle Editor is already open, so Understudy cannot start.\n\n"
                "Close the Editor first, then double-click the Understudy icon again.")
        return 0
    instance_lock = QLockFile(_esd_lock_path())
    instance_lock.setStaleLockTime(10000)
    if not instance_lock.tryLock(200):
        if _ask_running_esd_to_raise():
            return 0
        QMessageBox.information(None, "Wattle Editor", "Wattle Editor is already running.")
        return 0

    from esd.window import MainWindow

    win = MainWindow()
    win._instance_lock = instance_lock
    win._instance_server = _start_esd_instance_server(win)
    if len(sys.argv) > 1:
        from esd.json_io import load_design
        from esd.model import Design

        path = Path(sys.argv[1])
        win.design = Design(load_design(path))
        win.design.path = str(path)
        sc = win.design.first_screen()
        token = f"screen:{sc.get('id')}" if sc else "design"
        win._reload_view(token)
        win._mark_clean()
        win._set_status(win._opened_status(str(path)))
    win.show()

    replay_path = os.environ.get("WATTLE_REPLAY")
    if replay_path:
        from PyQt6.QtCore import QTimer

        from esd.replay import Replayer

        QTimer.singleShot(1200, lambda: Replayer(win).run(replay_path))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
