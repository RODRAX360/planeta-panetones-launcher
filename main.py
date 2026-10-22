#!/usr/bin/env python3
"""Launcher independiente de Planeta Panetones."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

import standalone

APP_DIR = Path(__file__).resolve().parent


class Bridge(QObject):
    event = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()

    def _emit(self, kind: str, **fields):
        self.event.emit(json.dumps({"type": kind, **fields}, ensure_ascii=False))

    @Slot(result=str)
    def getState(self) -> str:
        try:
            return json.dumps({"ok": True, "state": standalone.game_state()})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    def _start(self, action: str) -> str:
        if not self._lock.acquire(blocking=False):
            return json.dumps({"ok": False, "error": "Hay una operación en curso."})
        threading.Thread(target=self._run, args=(action,), daemon=True).start()
        return json.dumps({"ok": True})

    def _run(self, action: str) -> None:
        status = lambda message: self._emit("status", text=message)
        progress = lambda value, maximum: self._emit("progress", value=value, max=maximum)
        try:
            if action == "login":
                account = standalone.microsoft_login(status)
                status(f"Sesión iniciada como {account['name']}.")
            elif action == "update":
                manifest = standalone.update_pack(status, progress)
                standalone.install_game(status, progress)
                status(f"Pack {manifest['version']} listo para jugar.")
            elif action == "play":
                account = standalone.refreshed_account(status)
                standalone.update_pack(status, progress)
                game, java = standalone.install_game(status, progress)
                status("Iniciando Minecraft…")
                standalone.launch_game(account, game, java)
                status("Minecraft está iniciando.")
            else:
                raise ValueError("Operación desconocida.")
            self._emit("done", action=action)
        except Exception as exc:
            self._emit("error", text=str(exc))
        finally:
            self._lock.release()
            self._emit("state", state=standalone.game_state())

    @Slot(result=str)
    def login(self) -> str:
        return self._start("login")

    @Slot(result=str)
    def update(self) -> str:
        return self._start("update")

    @Slot(result=str)
    def play(self) -> str:
        return self._start("play")

    @Slot(result=str)
    def openFolder(self) -> str:
        try:
            folder = standalone.data_dir() / "minecraft"
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", str(folder)], start_new_session=True)
            return json.dumps({"ok": True})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})


def main() -> int:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--autoplay-policy=no-user-gesture-required")
    app = QApplication(sys.argv)
    app.setApplicationName("Planeta Panetones")
    window = QMainWindow()
    window.setWindowTitle("Planeta Panetones")
    window.resize(1280, 720)
    window.setMinimumSize(960, 600)
    view = QWebEngineView(window)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    channel = QWebChannel(view.page())
    bridge = Bridge(window)
    channel.registerObject("launcher", bridge)
    view.page().setWebChannel(channel)
    view.load(QUrl.fromLocalFile(str(APP_DIR / "index.html")))
    window.setCentralWidget(view)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
