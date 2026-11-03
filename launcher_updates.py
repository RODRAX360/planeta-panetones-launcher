"""Checks and installs a published launcher update for Windows or Linux."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from standalone import data_dir
from version import VERSION

MAX_INSTALLER_BYTES = 500 * 1024 * 1024


def failed_update_marker(version: str) -> Path:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Versión de actualización inválida.")
    return data_dir() / "updates" / f"failed-{version}.txt"


def windows_handoff_script() -> str:
    """Keep a failed installation from leaving the user without a launcher."""
    return "\r\n".join((
        "@echo off",
        "setlocal DisableDelayedExpansion",
        '>>"%PP_UPDATE_LOG%" echo Inicio de actualizacion',
        '>"%PP_UPDATE_READY%" echo ready',
        "if errorlevel 1 exit /b 1",
        ":wait_parent",
        'tasklist /FI "PID eq %PP_UPDATE_PARENT_PID%" /NH 2>nul | findstr /R /C:"[ ]%PP_UPDATE_PARENT_PID%[ ]" >nul',
        "if not errorlevel 1 (",
        "  ping -n 2 127.0.0.1 >nul",
        "  goto wait_parent",
        ")",
        "ping -n 2 127.0.0.1 >nul",
        'start "" /WAIT "%PP_UPDATE_INSTALLER%" /S',
        'set "InstallResult=%errorlevel%"',
        'if "%InstallResult%"=="0" (',
        '  if exist "%PP_UPDATE_FAILED%" del /F /Q "%PP_UPDATE_FAILED%" >nul 2>nul',
        '  >>"%PP_UPDATE_LOG%" echo Instalacion completada',
        ") else (",
        '  >"%PP_UPDATE_FAILED%" echo Instalador termino con codigo %InstallResult%',
        '  >>"%PP_UPDATE_LOG%" echo Instalacion fallida: %InstallResult%',
        ")",
        'start "" "%PP_UPDATE_LAUNCHER%" --skip-auto-update',
        'if errorlevel 1 >>"%PP_UPDATE_LOG%" echo No se pudo reabrir el launcher',
    )) + "\r\n"


def can_self_update() -> bool:
    if not getattr(sys, "frozen", False):
        return False
    if sys.platform == "win32":
        return True
    if sys.platform.startswith("linux"):
        appimage = os.environ.get("APPIMAGE", "")
        return bool(appimage and Path(appimage).is_file() and os.access(Path(appimage).parent, os.W_OK))
    return False


def _https_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("La actualización del launcher debe usar HTTPS.")
    return value


def _version_parts(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("Versión inválida en la actualización del launcher.")
    return tuple(map(int, value.split(".")))


def check_update(manifest_url: str) -> dict | None:
    if not manifest_url:
        return None
    url = _https_url(manifest_url)
    with urllib.request.urlopen(url, timeout=12) as response:
        if urllib.parse.urlparse(response.geturl()).scheme != "https":
            raise ValueError("La actualización redirigió fuera de HTTPS.")
        content = response.read(65537)
    if len(content) > 65536:
        raise ValueError("El manifiesto del launcher es demasiado grande.")
    data = json.loads(content)
    version = data.get("version")
    if _version_parts(version) <= _version_parts(VERSION):
        return None
    installer = data.get("installer", {})
    installer_url = _https_url(str(installer.get("url", "")))
    digest = installer.get("sha256")
    size = installer.get("size")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("SHA-256 inválido para el instalador.")
    if type(size) is not int or not 0 < size <= MAX_INSTALLER_BYTES:
        raise ValueError("Tamaño inválido para el instalador.")
    return {"version": version, "url": installer_url, "sha256": digest, "size": size}


def inspect_update(manifest_url: str, *, install_supported: bool) -> dict:
    """Return a terminal preflight state without treating missing hosting as an update.

    Call this from a worker thread: a configured manifest requires network access.
    ``update`` is included only when an installer was validated and can be run here.
    """
    url = str(manifest_url or "").strip()
    if not url:
        return {
            "status": "unconfigured",
            "message": "Las actualizaciones del launcher aún no están configuradas.",
            "version": VERSION,
        }
    try:
        update = check_update(url)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"No se pudo comprobar el launcher: {exc}",
            "version": VERSION,
        }
    if update is None:
        return {
            "status": "current",
            "message": "Tienes la versión más reciente del launcher.",
            "version": VERSION,
        }
    if not install_supported:
        return {
            "status": "unsupported",
            "message": "Hay una versión nueva; descarga el instalador para actualizar este launcher.",
            "version": VERSION,
            "availableVersion": update["version"],
        }
    return {
        "status": "available",
        "message": "Hay una actualización del launcher disponible.",
        "version": VERSION,
        "availableVersion": update["version"],
        "update": update,
    }


def download_installer(update: dict, progress: Callable[[int, int], None]) -> Path:
    """Download to a temporary file and publish it only after SHA-256 verification."""
    directory = data_dir() / "updates"
    directory.mkdir(parents=True, exist_ok=True)
    filename = (f"PlanetaPanetones-{update['version']}-x86_64.AppImage"
                if sys.platform.startswith("linux") else f"PlanetaPanetones-Setup-{update['version']}.exe")
    destination = directory / filename
    if destination.is_file() and destination.stat().st_size == update["size"]:
        if _hash_file(destination) == update["sha256"]:
            progress(update["size"], update["size"])
            return destination
    temporary = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    transferred = 0
    try:
        progress(0, update["size"])
        with urllib.request.urlopen(update["url"], timeout=30) as response, temporary.open("wb") as output:
            if urllib.parse.urlparse(response.geturl()).scheme != "https":
                raise ValueError("El instalador redirigió fuera de HTTPS.")
            while chunk := response.read(1024 * 1024):
                transferred += len(chunk)
                if transferred > update["size"]:
                    raise ValueError("El instalador supera el tamaño publicado.")
                digest.update(chunk)
                output.write(chunk)
                progress(transferred, update["size"])
        if transferred != update["size"] or digest.hexdigest() != update["sha256"]:
            raise ValueError("El instalador descargado no coincide con su SHA-256.")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def start_installer_after_exit(installer: Path) -> None:
    if sys.platform.startswith("linux") and can_self_update():
        target = Path(os.environ["APPIMAGE"]).resolve()
        script = data_dir() / "updates" / "install-after-exit.sh"
        script.write_text(
            '#!/bin/sh\n'
            'parent="$1"\n'
            'download="$2"\n'
            'target="$3"\n'
            'while kill -0 "$parent" 2>/dev/null; do sleep 1; done\n'
            'pending="${target}.update.$$"\n'
            'if cp -- "$download" "$pending" && chmod 755 "$pending" && mv -f -- "$pending" "$target"; then\n'
            '  nohup "$target" >/dev/null 2>&1 &\n'
            'else\n'
            '  rm -f -- "$pending"\n'
            '  nohup "$target" >/dev/null 2>&1 &\n'
            'fi\n',
            encoding="utf-8",
        )
        subprocess.Popen(["/bin/sh", str(script), str(os.getpid()), str(installer), str(target)],
                         start_new_session=True, close_fds=True)
        return
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise RuntimeError("La actualización automática requiere un instalador de Windows o AppImage modificable.")
    directory = data_dir() / "updates"
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "install-after-exit.cmd"
    ready = directory / "install-ready.txt"
    version = installer.name.removeprefix("PlanetaPanetones-Setup-").removesuffix(".exe")
    failed = failed_update_marker(version)
    log = directory / "update.log"
    ready.unlink(missing_ok=True)
    script.write_bytes(windows_handoff_script().encode("ascii"))
    handoff_env = os.environ.copy()
    handoff_env.update({
        "PP_UPDATE_PARENT_PID": str(os.getpid()),
        "PP_UPDATE_INSTALLER": str(installer),
        "PP_UPDATE_LAUNCHER": str(Path(sys.executable).resolve()),
        "PP_UPDATE_READY": str(ready),
        "PP_UPDATE_FAILED": str(failed),
        "PP_UPDATE_LOG": str(log),
    })
    process = subprocess.Popen(
        ["cmd.exe", "/D", "/V:OFF", "/C", "call", str(script)],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
        close_fds=True, env=handoff_env,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if ready.is_file():
            return
        if process.poll() is not None:
            break
        time.sleep(0.05)
    if process.poll() is None:
        process.terminate()
    raise RuntimeError(f"No se pudo iniciar el instalador. Revisa {log}. El launcher permanecerá abierto.")
