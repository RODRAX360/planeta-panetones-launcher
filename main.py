#!/usr/bin/env python3
"""Launcher independiente de Planeta Panetones."""

import json
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRect, QRectF, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QCursor, QFont, QPainterPath, QPen
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QSplashScreen

import standalone
from discord_presence import DiscordPresence
from server_status import query_server

APP_DIR = Path(__file__).resolve().parent


class Bridge(QObject):
    event = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._server_address = str(standalone.read_config().get("server_address", "")).strip()
        self._server_status = query_server("")
        self._server_status["configured"] = bool(self._server_address)
        self._server_polling = False

    def _emit(self, kind: str, **fields):
        self.event.emit(json.dumps({"type": kind, **fields}, ensure_ascii=False))

    @Slot(result=str)
    def getState(self) -> str:
        try:
            state = standalone.game_state()
            state["serverStatus"] = self._server_status
            return json.dumps({"ok": True, "state": state})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    def refresh_server_status(self) -> None:
        if not self._server_address or self._server_polling:
            return
        self._server_polling = True

        def check() -> None:
            try:
                self._server_status = query_server(self._server_address)
                self._emit("server", status=self._server_status)
            finally:
                self._server_polling = False

        threading.Thread(target=check, daemon=True).start()

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
                state = standalone.game_state()
                state["serverStatus"] = self._server_status
                self._emit("state", state=state)
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

    @Slot(str, result=str)
    def removeLocalProfile(self, name: str) -> str:
        try:
            standalone.remove_local_profile(name)
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @Slot(str, result=str)
    def removeMicrosoftAccount(self, identifier: str) -> str:
        try:
            standalone.remove_microsoft_account(identifier)
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @Slot(int, result=str)
    def saveMemory(self, value: int) -> str:
        try:
            standalone.set_memory_mb(value)
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @Slot(int, int, result=str)
    def saveResolution(self, width: int, height: int) -> str:
        try:
            standalone.set_resolution(width, height)
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    @Slot(result=str)
    def resetResolution(self) -> str:
        try:
            standalone.reset_resolution()
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

    @Slot(result=str)
    def openModsFolder(self) -> str:
        try:
            folder = standalone.data_dir() / "minecraft/mods"
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
    if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland" \
            and os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    app.setApplicationName("Planeta Panetones")

    def center_window(widget) -> None:
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            widget.move(area.x() + (area.width() - widget.width()) // 2,
                        area.y() + (area.height() - widget.height()) // 2)

    presence = DiscordPresence(standalone.read_config().get("discord_application_id", ""))
    presence.start()
    app.aboutToQuit.connect(presence.stop)
    icon = QPixmap(str(APP_DIR / "assets/icono.png"))
    poster = QPixmap(str(APP_DIR / "assets/portada.jpg"))
    splash_state = {"message": "Preparando archivos…", "error": False}
    animation_started = time.monotonic()

    def splash_frame(percent: int) -> QPixmap:
        width, height = 400, 480
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(0, 0, width, height), 18, 18)
        painter.setClipPath(outline)
        painter.fillRect(QRect(0, 0, width, height), QColor("#0b1524"))
        if not poster.isNull():
            cover = poster.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(0, 0, cover.copy((cover.width() - width) // 2,
                                                (cover.height() - height) // 2, width, height))
        painter.fillRect(QRect(0, 0, width, height), QColor(4, 10, 20, 145))
        elapsed = time.monotonic() - animation_started
        painter.setOpacity(min(1.0, max(0.0, elapsed / 0.45)))
        if not icon.isNull():
            bob = round(6 * math.sin(elapsed * math.tau / 2.4))
            painter.drawPixmap(QRect(118, 102 + bob, 164, 164), icon)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Poppins", 19, QFont.Weight.Bold))
        painter.drawText(QRect(16, 296, 368, 45), Qt.AlignmentFlag.AlignCenter, "Planeta Panetones")
        painter.setOpacity(1.0)
        painter.setPen(QColor("#f2f3f3"))
        painter.setFont(QFont("Poppins", 11, QFont.Weight.Bold))
        painter.drawText(QRect(20, 360, 360, 36), Qt.AlignmentFlag.AlignCenter, splash_state["message"])
        painter.fillRect(40, 412, 320, 13, QColor("#030303"))
        painter.fillRect(43, 415, 314, 7, QColor("#171717"))
        painter.fillRect(43, 415, int(314 * percent / 100), 7,
                         QColor("#d8dcdf") if not splash_state["error"] else QColor("#e55c5c"))
        painter.setPen(QColor("#c7d0de"))
        painter.setFont(QFont("Poppins", 8))
        painter.drawText(QRect(18, 431, 364, 18), Qt.AlignmentFlag.AlignCenter,
                         "Launcher independiente · Forge 1.20.1")
        painter.setPen(QColor("#f2f3f3"))
        painter.setFont(QFont("Poppins", 9, QFont.Weight.Bold))
        painter.drawText(QRect(18, 453, 364, 18), Qt.AlignmentFlag.AlignCenter, "@rodrax360")
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 36), 1))
        painter.drawRoundedRect(QRectF(0.5, 0.5, width - 1, height - 1), 18, 18)
        painter.end()
        return pixmap

    splash = QSplashScreen(splash_frame(5), Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
    splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    splash.setMask(splash.pixmap().mask())
    splash.show()
    center_window(splash)
    loading = {"percent": 5}
    splash_timer = QTimer()

    def animate_splash():
        loading["percent"] = min(loading["percent"] + 3, 92)
        frame = splash_frame(loading["percent"])
        splash.setPixmap(frame)
        splash.setMask(frame.mask())

    splash_timer.timeout.connect(animate_splash)
    splash_timer.start(45)
    app.processEvents()
    window = QMainWindow()
    window.setWindowTitle("Planeta Panetones")
    window.resize(1280, 720)
    window.setMinimumSize(960, 600)
    center_window(window)
    view = QWebEngineView(window)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    channel = QWebChannel(view.page())
    bridge = Bridge(window)
    channel.registerObject("launcher", bridge)
    view.page().setWebChannel(channel)
    view.load(QUrl.fromLocalFile(str(APP_DIR / "index.html")))
    window.setCentralWidget(view)
    server_timer = QTimer(window)
    server_timer.timeout.connect(bridge.refresh_server_status)
    server_timer.start(30000)
    QTimer.singleShot(500, bridge.refresh_server_status)
    ready = {"loaded": False, "delay": False, "shown": False}

    def reveal(*_args):
        if ready["shown"] or not ready["loaded"] or not ready["delay"]:
            return
        ready["shown"] = True
        splash_timer.stop()
        window.show()
        splash.close()

    def on_load_finished(ok: bool) -> None:
        if ok:
            ready["loaded"] = True
            reveal()
        else:
            splash_state.update(message="No se pudo abrir la interfaz.", error=True)
            splash_timer.stop()
            splash.setPixmap(splash_frame(100))
            QTimer.singleShot(5000, app.quit)

    view.loadFinished.connect(on_load_finished)
    QTimer.singleShot(1050, lambda: (ready.__setitem__("delay", True), reveal()))
    def on_loading_timeout() -> None:
        if not ready["shown"] and not splash_state["error"]:
            splash_state.update(message="La carga está tardando más de lo esperado…")
            splash.setPixmap(splash_frame(92))

    QTimer.singleShot(8000, on_loading_timeout)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
