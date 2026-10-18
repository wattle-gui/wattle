"""Closing the Editor from outside (Ctrl+C or a stop signal) asks to save first, instead of just killing it."""

from __future__ import annotations

import os


def install_soft_quit_signals() -> None:
    """SIGTERM/SIGINT close windows (save prompts) instead of killing the process."""
    import signal

    from PyQt6.QtCore import QSocketNotifier, QTimer
    from PyQt6.QtWidgets import QApplication

    # Pipe + notifier: Python signal writes a byte; Qt wakes and runs close().
    try:
        r_fd, w_fd = os.pipe()
        os.set_blocking(r_fd, False)
        os.set_blocking(w_fd, False)
        signal.set_wakeup_fd(w_fd)
        install_soft_quit_signals._pipe = (r_fd, w_fd)  # noqa: SLF001
    except Exception:
        r_fd = None

    def _close_all() -> None:
        app = QApplication.instance()
        if app is None:
            return
        for widget in list(app.topLevelWidgets()):
            try:
                if widget.isWindow() and widget.isVisible():
                    widget.close()
            except Exception:
                pass

    def _soft_quit(*_args) -> None:
        QTimer.singleShot(0, _close_all)

    if r_fd is not None:
        try:
            notifier = QSocketNotifier(r_fd, QSocketNotifier.Type.Read)
            def _drained() -> None:
                try:
                    while True:
                        chunk = os.read(r_fd, 256)
                        if not chunk:
                            break
                except BlockingIOError:
                    pass
                except OSError:
                    pass
                _close_all()
            notifier.activated.connect(lambda *_: _drained())
            install_soft_quit_signals._notifier = notifier  # noqa: SLF001
        except Exception:
            pass

    try:
        signal.signal(signal.SIGTERM, _soft_quit)
        signal.signal(signal.SIGINT, _soft_quit)
    except Exception:
        pass
