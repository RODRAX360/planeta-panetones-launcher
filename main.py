#!/usr/bin/env python3
"""Launcher independiente de Planeta Panetones."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRect, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QSplashScreen

import standalone
from discord_presence import DiscordPresence

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
                profile = standalone.selected_profile()
                account = profile if profile["type"] == "local" else standalone.refreshed_account(status)
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
            try:
                self._emit("state", state=standalone.game_state())
            except Exception as exc:
                self._emit("error", text=str(exc))

    @Slot(result=str)
    def login(self) -> str:
        return self._start("login")

    @Slot(result=str)
    def update(self) -> str:
        return self._start("update")

    @Slot(result=str)
    def play(self) -> str:
        return self._start("play")

    @Slot(str, result=str)
    def createLocalProfile(self, name: str) -> str:
        try:
            standalone.create_local_profile(name)
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @Slot(str, result=str)
    def selectProfile(self, identifier: str) -> str:
        try:
            standalone.select_profile(identifier)
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @Slot(result=str)
    def chooseLocalSkin(self) -> str:
        try:
            source, _ = QFileDialog.getOpenFileName(self.parent(), "Elegir skin de Minecraft", str(Path.home()), "Imagen PNG (*.png)")
            if source:
                standalone.set_local_skin(Path(source))
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

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
    presence = DiscordPresence(standalone.read_config().get("discord_application_id", ""))
    presence.start()
    app.aboutToQuit.connect(presence.stop)
    icon = QPixmap(str(APP_DIR / "assets/icono.png"))

    def splash_frame(percent: int) -> QPixmap:
        pixmap = QPixmap(420, 205)
        pixmap.fill(QColor("#0b1524"))
        painter = QPainter(pixmap)
        if not icon.isNull():
            painter.drawPixmap(QRect(26, 40, 76, 76), icon)
        painter.setPen(QColor("#e8a637"))
        painter.setFont(QFont("Poppins", 16, QFont.Weight.Bold))
        painter.drawText(QRect(113, 42, 290, 40), Qt.AlignmentFlag.AlignVCenter, "PLANETA PANETONES")
        painter.setPen(QColor("#c2d1df"))
        painter.setFont(QFont("Poppins", 10))
        painter.drawText(QRect(113, 82, 285, 35), Qt.AlignmentFlag.AlignVCenter, "Preparando el launcher…")
        painter.fillRect(30, 156, 360, 6, QColor("#38485a"))
        painter.fillRect(30, 156, int(360 * percent / 100), 6, QColor("#e8a637"))
        painter.end()
        return pixmap

    splash = QSplashScreen(splash_frame(5))
    splash.show()
    loading = {"percent": 5}
    splash_timer = QTimer()

    def animate_splash():
        loading["percent"] = min(loading["percent"] + 3, 92)
        splash.setPixmap(splash_frame(loading["percent"]))

    splash_timer.timeout.connect(animate_splash)
    splash_timer.start(45)
    app.processEvents()
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
    ready = {"loaded": False, "delay": False, "shown": False}

    def reveal(*_args):
        if ready["shown"] or not ready["loaded"] or not ready["delay"]:
            return
        ready["shown"] = True
        splash_timer.stop()
        splash.setPixmap(splash_frame(100))
        window.show()
        splash.finish(window)

    view.loadFinished.connect(lambda _ok: (ready.__setitem__("loaded", True), reveal()))
    QTimer.singleShot(1050, lambda: (ready.__setitem__("delay", True), reveal()))
    QTimer.singleShot(8000, lambda: (ready.__setitem__("loaded", True), ready.__setitem__("delay", True), reveal()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
