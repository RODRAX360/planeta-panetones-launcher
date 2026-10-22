"""Instalación, actualización, autenticación y arranque sin Modrinth."""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import minecraft_launcher_lib as mll

from updater import sync_pack


APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "launcher-config.json"
MINECRAFT_VERSION = "1.20.1"
FORGE_VERSION = "47.4.20"
FORGE_ID = f"{MINECRAFT_VERSION}-forge-{FORGE_VERSION}"


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    return base / "PlanetaPanetones"


def read_config() -> dict:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if not config.get("manifest_url") and (APP_DIR / "publicar/manifest.json").is_file():
        config["manifest_url"] = (APP_DIR / "publicar/manifest.json").as_uri()
    return config


def _account_path() -> Path:
    return data_dir() / "account.json"


def account_name() -> str | None:
    path = _account_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("name")
    except (ValueError, OSError):
        return None


def save_account(account: dict) -> None:
    target = _account_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.part")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as output:
        json.dump(account, output)
    temporary.replace(target)


def microsoft_login(status) -> dict:
    config = read_config()
    client_id = config.get("microsoft_client_id", "").strip()
    if not client_id:
        raise RuntimeError("Falta el Client ID de Microsoft en launcher-config.json.")
    redirect_uri = config.get("redirect_uri", "http://localhost:8765/callback")
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.port:
        raise ValueError("El redirect_uri debe ser una dirección HTTP local con puerto.")

    login_url, state, verifier = mll.microsoft_account.get_secure_login_data(client_id, redirect_uri)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urllib.parse.urlparse(self.path).path != parsed.path:
                self.send_error(404)
                return
            self.server.callback_url = redirect_uri.split("?", 1)[0] + "?" + urllib.parse.urlparse(self.path).query
            body = "<html><meta charset='utf-8'><body><h2>Planeta Panetones</h2><p>Inicio de sesión recibido. Ya puedes cerrar esta pestaña.</p></body></html>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = HTTPServer(("127.0.0.1", parsed.port), Handler)
    server.timeout = 1
    server.callback_url = None
    try:
        status("Abriendo Microsoft para iniciar sesión…")
        if not webbrowser.open(login_url):
            raise RuntimeError("No se pudo abrir el navegador para iniciar sesión.")
        deadline = time.monotonic() + 180
        while not server.callback_url and time.monotonic() < deadline:
            server.handle_request()
        if not server.callback_url:
            raise TimeoutError("Se agotó el tiempo de inicio de sesión.")
        auth_code = mll.microsoft_account.parse_auth_code_url(server.callback_url, state)
    finally:
        server.server_close()
    status("Verificando la cuenta de Minecraft…")
    try:
        account = mll.microsoft_account.complete_login(client_id, None, redirect_uri, auth_code, verifier)
    except mll.exceptions.AzureAppNotPermitted as exc:
        raise RuntimeError(
            "Minecraft aún no autoriza esta aplicación. El Client ID de Planeta Panetones necesita permiso para la API de Minecraft."
        ) from exc
    save_account(account)
    return account


def refreshed_account(status) -> dict:
    config = read_config()
    client_id = config.get("microsoft_client_id", "").strip()
    path = _account_path()
    if not client_id:
        raise RuntimeError("Falta el Client ID de Microsoft en launcher-config.json.")
    if not path.is_file():
        return microsoft_login(status)
    old = json.loads(path.read_text(encoding="utf-8"))
    status("Actualizando la sesión de Minecraft…")
    try:
        account = mll.microsoft_account.complete_refresh(
            client_id,
            None,
            config.get("redirect_uri", "http://localhost:8765/callback"),
            old["refresh_token"],
        )
    except Exception as exc:
        raise RuntimeError("La sesión caducó. Vuelve a iniciar sesión en Cuentas.") from exc
    save_account(account)
    return account


def install_game(status, progress) -> tuple[Path, str]:
    game = data_dir() / "minecraft"
    game.mkdir(parents=True, exist_ok=True)
    max_value = 0

    def set_max(value):
        nonlocal max_value
        max_value = max(value, 1)

    callbacks = {
        "setStatus": lambda value: status(value),
        "setProgress": lambda value: progress(value, max_value),
        "setMax": set_max,
    }
    if not (game / "versions" / MINECRAFT_VERSION / f"{MINECRAFT_VERSION}.json").is_file():
        status("Instalando Minecraft 1.20.1…")
        mll.install.install_minecraft_version(MINECRAFT_VERSION, game, callback=callbacks)
    runtime = mll.runtime.get_version_runtime_information(MINECRAFT_VERSION, game)
    if runtime is None:
        raise RuntimeError("No se pudo identificar la versión de Java necesaria.")
    java_name = runtime["name"]
    java = mll.runtime.get_executable_path(java_name, game)
    if not java or not Path(java).is_file():
        status(f"Instalando Java {runtime['javaMajorVersion']}…")
        mll.runtime.install_jvm_runtime(java_name, game, callback=callbacks)
        java = mll.runtime.get_executable_path(java_name, game)
    if not java:
        raise RuntimeError("No se pudo instalar Java.")
    if not mll.mod_loader.is_version_valid(FORGE_ID, game):
        status("Instalando Forge 47.4.20…")
        mll.mod_loader.get_mod_loader("forge").install(
            MINECRAFT_VERSION,
            game,
            loader_version=FORGE_VERSION,
            callback=callbacks,
            java=java,
        )
    return game, java


def update_pack(status, progress) -> dict:
    manifest_url = read_config().get("manifest_url", "").strip()
    if not manifest_url:
        raise RuntimeError("Falta la URL HTTPS del pack en launcher-config.json.")
    status("Buscando actualizaciones de Planeta Panetones…")
    return sync_pack(
        manifest_url,
        data_dir() / "minecraft",
        lambda name, index, total: (status(name), progress(index, total)),
    )


def launch_game(account: dict, game: Path, java: str) -> None:
    config = read_config()
    memory_mb = int(config.get("memory_mb", 8192))
    if not 2048 <= memory_mb <= 32768:
        raise ValueError("La memoria debe estar entre 2048 y 32768 MB.")
    options = {
        "username": account["name"],
        "uuid": account["id"],
        "token": account["access_token"],
        "executablePath": java,
        "gameDirectory": str(game),
        "jvmArguments": [f"-Xmx{memory_mb}m"],
        "launcherName": "PlanetaPanetones",
        "launcherVersion": "1.0.0",
    }
    command = mll.command.get_minecraft_command(FORGE_ID, game, options)
    subprocess.Popen(command, cwd=game, start_new_session=True)


def game_state() -> dict:
    config = read_config()
    local = (data_dir() / "minecraft/.planeta-panetones-manifest.json").is_file()
    return {
        "account": account_name(),
        "packConfigured": bool(config.get("manifest_url")),
        "localManifest": config.get("manifest_url", "").startswith("file:"),
        "clientConfigured": bool(config.get("microsoft_client_id")),
        "installed": local,
        "gameDirectory": str(data_dir() / "minecraft"),
        "memoryMb": int(config.get("memory_mb", 8192)),
    }
