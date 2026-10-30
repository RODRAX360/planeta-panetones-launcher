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

from PySide6.QtCore import QObject, QPointF, QRect, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QCursor, QFont, QIcon
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QWidget

import standalone
import launcher_updates
from discord_presence import DiscordPresence
from server_status import query_server

APP_DIR = standalone.APP_DIR


class Bridge(QObject):
    event = Signal(str)
    requestClose = Signal()
    preflightFinished = Signal(str)
    requestMinimize = Signal()

    def __init__(self, parent=None, *, skip_auto_update=False):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._server_address = str(standalone.read_config().get("server_address", "")).strip()
        self._server_status = query_server("")
        self._server_status["configured"] = bool(self._server_address)
        self._server_polling = False
        self._launcher_update = None
        self._update_checking = False
        self._preflight_state = {"status": "checking", "message": "Comprobando el launcher…",
                                 "version": launcher_updates.VERSION}
        self._login_cancel_event = None
        self._skip_auto_update = skip_auto_update

    def _emit(self, kind: str, **fields):
        self.event.emit(json.dumps({"type": kind, **fields}, ensure_ascii=False))

    @Slot(result=str)
    def getState(self) -> str:
        try:
            state = standalone.game_state()
            state["serverStatus"] = self._server_status
            state["launcherVersion"] = launcher_updates.VERSION
            state["launcherUpdateConfigured"] = bool(standalone.read_config().get("launcher_update_url"))
            state["launcherUpdateStatus"] = self._preflight_state
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

    def check_launcher_update(self) -> None:
        if self._update_checking:
            return
        url = str(standalone.read_config().get("launcher_update_url", "")).strip()
        self._update_checking = True

        def check() -> None:
            try:
                result = launcher_updates.inspect_update(
                    url, install_supported=launcher_updates.can_self_update())
                public = {key: value for key, value in result.items() if key != "update"}
                self._preflight_state = public
                self._emit("launcher_update_status", **public)
                if result["status"] == "available":
                    self._launcher_update = result["update"]
                    failed_before = launcher_updates.failed_update_marker(result["availableVersion"]).is_file()
                    if self._skip_auto_update or failed_before:
                        if failed_before:
                            public["message"] = "La instalación automática falló. Reintenta desde el launcher o descarga el instalador."
                        public["retryAvailable"] = True
                        self._preflight_state = public
                        self._emit("launcher_update_status", **public)
                        self.preflightFinished.emit("available")
                        return
                    if self._install_launcher_update():
                        return
                    public = {"status": "available", "message": "No se pudo instalar la actualización. Puedes reintentar desde el selector.",
                              "version": launcher_updates.VERSION,
                              "availableVersion": result["availableVersion"], "retryAvailable": True}
                    self._preflight_state = public
                    self._emit("launcher_update_status", **public)
                    self.preflightFinished.emit("available")
                else:
                    self.preflightFinished.emit(public["status"])
            except Exception as exc:
                public = {"status": "error", "message": f"No se pudo comprobar el launcher: {exc}",
                          "version": launcher_updates.VERSION}
                self._preflight_state = public
                self._emit("launcher_update_status", **public)
                self.preflightFinished.emit("error")
            finally:
                self._update_checking = False

        threading.Thread(target=check, daemon=True).start()

    def _install_launcher_update(self) -> bool:
        if not self._launcher_update or not self._lock.acquire(blocking=False):
            return False
        try:
            self._emit("busy", busy=True)
            self._emit("status", text=f"Actualizando launcher a {self._launcher_update['version']}…")
            installer = launcher_updates.download_installer(
                self._launcher_update,
                lambda value, maximum: self._emit("progress", value=value, max=maximum),
            )
            self._emit("status", text="Instalando la nueva versión…")
            launcher_updates.start_installer_after_exit(installer)
            self.requestClose.emit()
            return True
        except Exception as exc:
            self._emit("error", text=f"No se pudo actualizar el launcher: {exc}")
            self._emit("busy", busy=False)
            return False
        finally:
            self._lock.release()

    @Slot(result=str)
    def installLauncherUpdate(self) -> str:
        if not self._launcher_update:
            return json.dumps({"ok": False, "error": "No hay una actualización del launcher disponible."})
        threading.Thread(target=self._install_launcher_update, daemon=True).start()
        return json.dumps({"ok": True})

    def _start(self, action: str) -> str:
        if not self._lock.acquire(blocking=False):
            return json.dumps({"ok": False, "error": "Hay una operación en curso."})
        if action == "login":
            self._login_cancel_event = threading.Event()
        threading.Thread(target=self._run, args=(action,), daemon=True).start()
        return json.dumps({"ok": True})

    @Slot(result=str)
    def cancelLogin(self) -> str:
        if self._login_cancel_event is None:
            return json.dumps({"ok": False, "error": "No hay un inicio de sesión pendiente."})
        self._login_cancel_event.set()
        return json.dumps({"ok": True})

    def _run(self, action: str) -> None:
        status = lambda message: self._emit("status", text=message)
        progress = lambda value, maximum: self._emit("progress", value=value, max=maximum)
        try:
            instance_id = standalone.selected_instance_id()
            if action == "login":
                account = standalone.microsoft_login(status, self._login_cancel_event)
                status(f"Sesión iniciada como {account['name']}.")
            elif action == "update":
                manifest = standalone.update_pack(status, progress, verify_all=True, instance_id=instance_id)
                standalone.install_game(status, progress)
                status(f"Pack {manifest['version']} listo para jugar.")
            elif action == "play":
                profile = standalone.selected_profile()
                account = profile if profile["type"] == "local" else standalone.refreshed_account(status)
                standalone.update_pack(status, progress, instance_id=instance_id)
                game, java = standalone.install_game(status, progress)
                status("Iniciando Minecraft…")
                standalone.launch_game(account, game, java, instance_id=instance_id)
                status("Minecraft está iniciando.")
                self.requestMinimize.emit()
            else:
                raise ValueError("Operación desconocida.")
            self._emit("done", action=action)
        except standalone.LoginCancelled:
            self._emit("cancelled", action=action)
        except Exception as exc:
            self._emit("error", text=str(exc))
        finally:
            if action == "login":
                self._login_cancel_event = None
            self._lock.release()
            try:
                state = standalone.game_state()
                state["serverStatus"] = self._server_status
                state["launcherVersion"] = launcher_updates.VERSION
                state["launcherUpdateConfigured"] = bool(standalone.read_config().get("launcher_update_url"))
                state["launcherUpdateStatus"] = self._preflight_state
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
    def selectInstance(self, instance_id: str) -> str:
        if self._lock.locked():
            return json.dumps({"ok": False, "error": "Espera a que termine la operación actual."})
        try:
            standalone.set_instance(instance_id)
            return self.getState()
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

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

    @Slot(int, int, int, bool, result=str)
    def saveSettings(self, memory_mb: int, width: int, height: int, custom_resolution: bool) -> str:
        try:
            standalone.save_global_settings(memory_mb, width, height, custom_resolution)
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
            folder = standalone.instance_game_dir()
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
            folder = standalone.instance_game_dir() / "mods"
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", str(folder)], start_new_session=True)
            return json.dumps({"ok": True})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})


class StartupSplash(QWidget):
    """Draw the small splash in the center of a transparent Wayland surface."""

    def __init__(self, frame: QPixmap, fullscreen: bool):
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self._frame = frame
        self._fullscreen = fullscreen
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        if not fullscreen:
            self.resize(frame.size())
            self.setMask(frame.mask())

    def setPixmap(self, frame: QPixmap) -> None:
        previous = self._frame_rect()
        self._frame = frame
        if not self._fullscreen:
            self.resize(frame.size())
            self.setMask(frame.mask())
        self.update(previous.united(self._frame_rect()))

    def _frame_rect(self) -> QRect:
        return QRect((self.width() - self._frame.width()) // 2,
                     (self.height() - self._frame.height()) // 2,
                     self._frame.width(), self._frame.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawPixmap(self._frame_rect().topLeft(), self._frame)
        painter.end()


def main(*, skip_auto_update=False) -> int:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--autoplay-policy=no-user-gesture-required")
    app = QApplication(sys.argv)
    app.setApplicationName("Planeta Panetones")
    brand_icon = QIcon(str(APP_DIR / "assets/icono.png"))
    app.setWindowIcon(brand_icon)

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
    if not icon.isNull():
        small = icon.scaled(258, 258, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        left, top = small.width(), small.height()
        right, bottom = -1, -1
        for y in range(small.height()):
            for x in range(small.width()):
                color = small.pixelColor(x, y)
                if color.alpha():
                    left, top = min(left, x), min(top, y)
                    right, bottom = max(right, x), max(bottom, y)
        icon = QPixmap.fromImage(small.copy(left, top, right - left + 1, bottom - top + 1)) \
            if right >= left else QPixmap()
    splash_width, splash_height = 420, 300
    splash_state = {"message": "Buscando actualizaciones…", "mode": "checking", "error": False,
                    "text_started": time.monotonic()}
    animation_started = time.monotonic()

    def splash_frame(percent: int = 0) -> QPixmap:
        pixmap = QPixmap(splash_width, splash_height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        elapsed = time.monotonic() - animation_started
        bob = round(3 * math.sin(elapsed * math.tau / 2.2))
        if not icon.isNull():
            logo_width = 320
            logo_height = round(logo_width * icon.height() / icon.width())
            painter.drawPixmap((splash_width - logo_width) // 2, 35 + bob,
                               logo_width, logo_height, icon)
        painter.setFont(QFont("Poppins", 12, QFont.Weight.Bold))
        metrics = painter.fontMetrics()
        message = splash_state["message"]
        if splash_state["mode"] == "downloading" and percent:
            message = f"{message} {percent} %"
        lines = []
        for word in message.split():
            candidate = (lines[-1] + " " + word) if lines else word
            if lines and metrics.horizontalAdvance(candidate) <= 400:
                lines[-1] = candidate
            else:
                lines.append(word)
        remaining = min(len(message),
                        max(0, int((time.monotonic() - splash_state["text_started"]) * 58)))
        baseline = 242 - (len(lines) - 1) * 11
        for index, line in enumerate(lines):
            visible = line[:remaining]
            remaining = max(0, remaining - len(line) - 1)
            x = (splash_width - metrics.horizontalAdvance(line)) / 2
            y = baseline + index * 22
            painter.setPen(QColor(0, 0, 0, 210))
            painter.drawText(QPointF(x, y + 2), visible)
            painter.setPen(QColor("#ffffff") if not splash_state["error"] else QColor("#ffd0d0"))
            painter.drawText(QPointF(x, y), visible)
        painter.end()
        return pixmap

    fullscreen_splash = app.platformName().startswith("wayland")
    splash = StartupSplash(splash_frame(), fullscreen_splash)
    splash.setWindowIcon(brand_icon)
    if fullscreen_splash:
        screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
        if screen:
            splash.setScreen(screen)
        splash.showFullScreen()
    else:
        splash.show()
        center_window(splash)
    loading = {"percent": 0.0, "target": 0.0}
    splash_timer = QTimer()

    def render_splash() -> None:
        frame = splash_frame(round(loading["percent"]))
        splash.setPixmap(frame)

    def animate_splash():
        loading["percent"] += max(0.0, (loading["target"] - loading["percent"]) * 0.24)
        loading["percent"] = min(loading["percent"], loading["target"])
        render_splash()

    splash_timer.timeout.connect(animate_splash)
    splash_timer.start(33)
    app.processEvents()
    window = QMainWindow()
    window.setWindowTitle("Planeta Panetones")
    window.setWindowIcon(brand_icon)
    window.resize(1280, 720)
    window.setMinimumSize(780, 560)
    center_window(window)
    view = QWebEngineView(window)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    channel = QWebChannel(view.page())
    bridge = Bridge(window, skip_auto_update=skip_auto_update)
    bridge.requestClose.connect(app.quit)
    bridge.requestMinimize.connect(window.showMinimized)
    channel.registerObject("launcher", bridge)
    view.page().setWebChannel(channel)
    window.setCentralWidget(view)
    server_timer = QTimer(window)
    server_timer.timeout.connect(bridge.refresh_server_status)
    server_timer.start(30000)
    QTimer.singleShot(500, bridge.refresh_server_status)
    ready = {"loaded": False, "delay": False, "preflight": False, "shown": False}

    def reveal(*_args):
        if ready["shown"] or not ready["loaded"] or not ready["delay"] or not ready["preflight"]:
            return
        ready["shown"] = True
        splash_timer.stop()
        render_splash()
        QTimer.singleShot(110, lambda: (window.show(), splash.close()))

    def on_preflight_finished(status: str) -> None:
        ready["preflight"] = True
        messages = {
            "current": "Tienes la versión más reciente.",
            "unconfigured": "Actualizaciones sin configurar.",
            "unsupported": "Hay una versión nueva disponible.",
            "error": "No se pudo comprobar la actualización.",
            "available": "Actualización disponible en el launcher.",
        }
        if status == "error" and bridge._preflight_state.get("retryAvailable"):
            splash_state["message"] = "No se pudo instalar. Podrás reintentar dentro del launcher."
        else:
            splash_state["message"] = messages.get(status, "Preparando launcher…")
        splash_state["mode"] = status
        splash_state["error"] = status == "error"
        splash_state["text_started"] = time.monotonic()
        render_splash()
        def after_result() -> None:
            ready["delay"] = True
            reveal()
        QTimer.singleShot(1600, after_result)

    def on_launcher_event(raw: str) -> None:
        if ready["shown"]:
            return
        try:
            event = json.loads(raw)
        except ValueError:
            return
        if event.get("type") == "status" and not ready["preflight"]:
            installing = "Instalando" in str(event.get("text", ""))
            splash_state.update(message="Instalando actualización…" if installing
                                else "Descargando actualización…",
                                mode="installing" if installing else "downloading",
                                text_started=time.monotonic())
        elif event.get("type") == "progress" and not ready["preflight"]:
            maximum = max(int(event.get("max") or 1), 1)
            fraction = min(max(int(event.get("value") or 0) / maximum, 0.0), 1.0)
            loading["target"] = max(loading["target"], 100.0 * fraction)
        elif event.get("type") == "error" and not ready["preflight"]:
            splash_state.update(message="No se pudo actualizar el launcher.", mode="error", error=True,
                                text_started=time.monotonic())

    bridge.preflightFinished.connect(on_preflight_finished)
    bridge.event.connect(on_launcher_event)
    QTimer.singleShot(0, bridge.check_launcher_update)

    def on_load_finished(ok: bool) -> None:
        if ok:
            ready["loaded"] = True
            reveal()
        else:
            splash_state.update(message="No se pudo abrir la interfaz.", mode="error", error=True,
                                text_started=time.monotonic())
            splash_timer.stop()
            render_splash()
            QTimer.singleShot(5000, app.quit)

    view.loadFinished.connect(on_load_finished)
    view.load(QUrl.fromLocalFile(str(APP_DIR / "index.html")))
    def on_loading_timeout() -> None:
        if not ready["shown"] and not splash_state["error"] and splash_state["mode"] == "checking":
            splash_state["message"] = "La comprobación está tardando…"
            splash_state["text_started"] = time.monotonic()
            render_splash()

    QTimer.singleShot(8000, on_loading_timeout)
    return app.exec()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        for resource in ("index.html", "app.js", "style.css", "assets/icono.png"):
            if not (APP_DIR / resource).is_file():
                raise SystemExit(f"Falta el recurso {resource}")
        standalone.read_config()
        print("Launcher y recursos listos.")
        raise SystemExit(0)
    skip_auto_update = "--skip-auto-update" in sys.argv
    if skip_auto_update:
        sys.argv.remove("--skip-auto-update")
    raise SystemExit(main(skip_auto_update=skip_auto_update))
