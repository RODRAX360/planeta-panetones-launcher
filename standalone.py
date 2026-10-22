"""Instalación, actualización, autenticación y arranque sin Modrinth."""

import json
import hashlib
import os
import ctypes
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import minecraft_launcher_lib as mll
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from updater import sync_pack


APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "launcher-config.json"
MINECRAFT_VERSION = "1.20.1"
FORGE_VERSION = "47.4.20"
FORGE_ID = f"{MINECRAFT_VERSION}-forge-{FORGE_VERSION}"
NAME_PATTERN = re.compile(r"[A-Za-z0-9_]{3,16}\Z")


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
    try:
        preferences = json.loads((data_dir() / "preferences.json").read_text(encoding="utf-8"))
        if isinstance(preferences, dict):
            for key in ("memory_mb", "resolution_width", "resolution_height", "custom_resolution"):
                if key in preferences:
                    config[key] = preferences[key]
    except (OSError, ValueError, TypeError):
        pass
    try:
        requested_memory = int(config.get("memory_mb", 8192))
    except (TypeError, ValueError):
        requested_memory = 8192
    config["memory_mb"] = max(2048, min(requested_memory, memory_limit_mb()))
    if not config.get("manifest_url") and (APP_DIR / "publicar/manifest.json").is_file():
        config["manifest_url"] = (APP_DIR / "publicar/manifest.json").as_uri()
    return config


def system_memory_mb() -> int:
    """Return physical RAM in MiB, or zero if the OS does not report it."""
    try:
        if sys.platform == "win32":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            ("total_phys", ctypes.c_ulonglong), ("available_phys", ctypes.c_ulonglong),
                            ("total_page", ctypes.c_ulonglong), ("available_page", ctypes.c_ulonglong),
                            ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                            ("available_extended", ctypes.c_ulonglong)]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.total_phys // 1048576
        elif sys.platform == "darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=2)) // 1048576
        else:
            return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // 1048576
    except (AttributeError, OSError, ValueError, subprocess.SubprocessError):
        pass
    return 0


def memory_limit_mb() -> int:
    total = system_memory_mb()
    return max(2048, min(32768, (total * 3 // 4 // 64) * 64)) if total else 32768


def _save_preferences(**changes) -> None:
    path = data_dir() / "preferences.json"
    try:
        preferences = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(preferences, dict):
            preferences = {}
    except (OSError, ValueError, TypeError):
        preferences = {}
    preferences.update(changes)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(preferences, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def set_memory_mb(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 2048 <= value <= memory_limit_mb():
        raise ValueError(f"Elige entre 2048 y {memory_limit_mb()} MiB de RAM.")
    _save_preferences(memory_mb=value)


def set_resolution(width: int, height: int) -> None:
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (width, height)) \
            or not 640 <= width <= 7680 or not 360 <= height <= 4320:
        raise ValueError("La resolución debe estar entre 640×360 y 7680×4320.")
    _save_preferences(resolution_width=width, resolution_height=height, custom_resolution=True)


def reset_resolution() -> None:
    _save_preferences(resolution_width=854, resolution_height=480, custom_resolution=False)


def _account_path() -> Path:
    return data_dir() / "account.json"


def _accounts_path() -> Path:
    return data_dir() / "accounts.json"


def _read_accounts() -> list[dict]:
    path = _accounts_path()
    if path.is_file():
        try:
            accounts = json.loads(path.read_text(encoding="utf-8")).get("accounts", [])
            return [item for item in accounts if isinstance(item, dict) and item.get("id") and item.get("name")]
        except (OSError, ValueError, TypeError, AttributeError):
            return []
    try:
        legacy = json.loads(_account_path().read_text(encoding="utf-8"))
        return [legacy] if isinstance(legacy, dict) and legacy.get("id") and legacy.get("name") else []
    except (OSError, ValueError, TypeError):
        return []


def _save_accounts(accounts: list[dict]) -> None:
    path = _accounts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as output:
        json.dump({"accounts": accounts}, output, ensure_ascii=False)
    temporary.replace(path)
    _account_path().unlink(missing_ok=True)


def _microsoft_avatar_path(identifier: str) -> Path:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:20]
    return data_dir() / "avatars" / f"microsoft-{digest}.png"


def selected_microsoft_account() -> dict | None:
    accounts = _read_accounts()
    selection = _read_profiles().get("selected", "microsoft")
    if selection.startswith("microsoft:"):
        return next((account for account in accounts if "microsoft:" + account["id"] == selection), None)
    return accounts[0] if accounts else None


def _profiles_path() -> Path:
    return data_dir() / "profiles.json"


def _read_profiles() -> dict:
    try:
        data = json.loads(_profiles_path().read_text(encoding="utf-8"))
        if isinstance(data.get("local", []), list):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {"selected": "microsoft", "local": []}


def _save_profiles(data: dict) -> None:
    path = _profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def create_local_profile(name: str) -> None:
    name = name.strip()
    if not NAME_PATTERN.fullmatch(name):
        raise ValueError("El nombre debe tener entre 3 y 16 caracteres: letras, números o guion bajo.")
    data = _read_profiles()
    existing = next((item["name"] for item in data["local"] if item["name"].lower() == name.lower()), None)
    if existing:
        name = existing
    else:
        data["local"].append({"name": name})
    data["selected"] = "local:" + name
    _save_profiles(data)


def select_profile(identifier: str) -> None:
    data = _read_profiles()
    valid_local = any("local:" + item["name"] == identifier for item in data["local"])
    valid_microsoft = identifier == "microsoft" or any("microsoft:" + item["id"] == identifier for item in _read_accounts())
    if not valid_local and not valid_microsoft:
        raise ValueError("No se encontró esa cuenta.")
    data["selected"] = identifier
    _save_profiles(data)


def remove_local_profile(name: str) -> None:
    data = _read_profiles()
    remaining = [item for item in data["local"] if item["name"] != name]
    if len(remaining) == len(data["local"]):
        raise ValueError("No se encontró ese perfil local.")
    data["local"] = remaining
    if data.get("selected") == "local:" + name:
        data["selected"] = "microsoft" if account_name() else ("local:" + remaining[0]["name"] if remaining else "microsoft")
    _save_profiles(data)


def selected_profile() -> dict:
    data = _read_profiles()
    selection = data.get("selected", "microsoft")
    if selection.startswith("local:"):
        name = selection[6:]
        if any(item["name"] == name for item in data["local"]):
            raw = hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest()
            value = bytearray(raw)
            value[6] = value[6] & 0x0f | 0x30
            value[8] = value[8] & 0x3f | 0x80
            return {"type": "local", "name": name, "id": str(uuid.UUID(bytes=bytes(value))), "access_token": "0"}
    account = selected_microsoft_account()
    return {"type": "microsoft", "name": account["name"] if account else None,
            "id": account["id"] if account else None}


def _avatar_for(image: QImage, destination: Path) -> None:
    canvas = QImage(64, 64, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    painter.drawImage(canvas.rect(), image.copy(8, 8, 8, 8))
    overlay = image.copy(40, 8, 8, 8)
    painter.drawImage(canvas.rect(), overlay)
    painter.end()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(destination), "PNG"):
        raise RuntimeError("No se pudo guardar el avatar.")


def set_local_skin(source: Path) -> None:
    profile = selected_profile()
    if profile["type"] != "local":
        raise ValueError("Selecciona un perfil local antes de elegir una skin.")
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("La PNG de la skin no puede superar 2 MiB.")
    with source.open("rb") as stream:
        signature = stream.read(8)
    if source.suffix.lower() != ".png" or signature != b"\x89PNG\r\n\x1a\n":
        raise ValueError("El archivo debe ser una imagen PNG.")
    image = QImage(str(source))
    if image.isNull() or (image.width(), image.height()) not in {(64, 64), (64, 32)}:
        raise ValueError("La skin debe ser una PNG de Minecraft de 64×64 o 64×32 píxeles.")
    name = profile["name"]
    destination = data_dir() / "minecraft/CustomSkinLoader/LocalSkin/skins" / f"{name}.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(destination), "PNG"):
        raise RuntimeError("No se pudo guardar la skin.")
    _avatar_for(image, data_dir() / "avatars" / f"local-{name}.png")


def save_microsoft_avatar(account: dict) -> None:
    skins = account.get("skins") or []
    if not skins:
        return
    url = skins[0].get("url", "")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "textures.minecraft.net":
        return
    try:
        with urllib.request.urlopen(url, timeout=12) as response:
            content = response.read(1024 * 1024 + 1)
        if len(content) > 1024 * 1024:
            return
        image = QImage.fromData(content, "PNG")
        if not image.isNull() and image.width() >= 48 and image.height() >= 16:
            _avatar_for(image, _microsoft_avatar_path(account["id"]))
    except (OSError, ValueError):
        pass


def account_name() -> str | None:
    account = selected_microsoft_account()
    return account["name"] if account else None


def account_id() -> str | None:
    account = selected_microsoft_account()
    return account["id"] if account else None


def remove_microsoft_account(identifier: str) -> None:
    accounts = _read_accounts()
    remaining = [account for account in accounts if "microsoft:" + account["id"] != identifier]
    if len(remaining) == len(accounts):
        raise ValueError("No se encontró esa cuenta Microsoft.")
    removed = next(account for account in accounts if "microsoft:" + account["id"] == identifier)
    _microsoft_avatar_path(removed["id"]).unlink(missing_ok=True)
    if _account_path().is_file():
        (data_dir() / "avatars/microsoft.png").unlink(missing_ok=True)
    _save_accounts(remaining)
    profiles = _read_profiles()
    if profiles.get("selected") == identifier or (profiles.get("selected") == "microsoft" and not remaining):
        profiles["selected"] = ("microsoft:" + remaining[0]["id"] if remaining else
                                "local:" + profiles["local"][0]["name"] if profiles["local"] else "microsoft")
        _save_profiles(profiles)


def save_account(account: dict) -> None:
    if not account.get("id") or not account.get("name"):
        raise ValueError("La cuenta Microsoft no tiene un perfil de Minecraft válido.")
    accounts = _read_accounts()
    if _account_path().is_file() and accounts:
        legacy_avatar = data_dir() / "avatars/microsoft.png"
        migrated_avatar = _microsoft_avatar_path(accounts[0]["id"])
        if legacy_avatar.is_file() and not migrated_avatar.is_file():
            migrated_avatar.parent.mkdir(parents=True, exist_ok=True)
            legacy_avatar.replace(migrated_avatar)
    accounts = [item for item in accounts if item["id"] != account["id"]]
    accounts.append(account)
    _save_accounts(accounts)


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
    save_microsoft_avatar(account)
    select_profile("microsoft:" + account["id"])
    return account


def refreshed_account(status) -> dict:
    config = read_config()
    client_id = config.get("microsoft_client_id", "").strip()
    if not client_id:
        raise RuntimeError("Falta el Client ID de Microsoft en launcher-config.json.")
    old = selected_microsoft_account()
    if old is None:
        return microsoft_login(status)
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
    if not _microsoft_avatar_path(account["id"]).is_file():
        save_microsoft_avatar(account)
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
    if not 2048 <= memory_mb <= memory_limit_mb():
        raise ValueError(f"La memoria debe estar entre 2048 y {memory_limit_mb()} MiB.")
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
    if config.get("custom_resolution", False):
        width, height = int(config.get("resolution_width", 854)), int(config.get("resolution_height", 480))
        if not 640 <= width <= 7680 or not 360 <= height <= 4320:
            raise ValueError("La resolución guardada no es válida.")
        options.update(customResolution=True, resolutionWidth=str(width), resolutionHeight=str(height))
    command = mll.command.get_minecraft_command(FORGE_ID, game, options)
    subprocess.Popen(command, cwd=game, start_new_session=True)


def game_state() -> dict:
    config = read_config()
    local = (data_dir() / "minecraft/.planeta-panetones-manifest.json").is_file()
    manifest = data_dir() / "minecraft/.planeta-panetones-manifest.json"
    if not manifest.is_file() and config.get("manifest_url", "").startswith("file:"):
        manifest = APP_DIR / "publicar/manifest.json"
    try:
        mod_count = sum(entry["path"].startswith("mods/") for entry in json.loads(manifest.read_text(encoding="utf-8"))["files"])
    except (OSError, ValueError, KeyError, TypeError):
        mod_count = 0
    profiles = _read_profiles()
    selected = selected_profile()
    accounts = _read_accounts()
    selected_identifier = profiles.get("selected", "microsoft")
    if selected_identifier == "microsoft" and selected.get("id"):
        selected_identifier = "microsoft:" + selected["id"]
    profile_avatars = {}
    for account in accounts:
        path = _microsoft_avatar_path(account["id"])
        if not path.is_file() and len(accounts) == 1:
            path = data_dir() / "avatars/microsoft.png"
        if path.is_file():
            profile_avatars["microsoft:" + account["id"]] = path.as_uri() + f"?v={path.stat().st_mtime_ns}"
    for item in profiles["local"]:
        identifier = "local:" + item["name"]
        path = data_dir() / "avatars" / f"local-{item['name']}.png"
        if path.is_file():
            profile_avatars[identifier] = path.as_uri() + f"?v={path.stat().st_mtime_ns}"
    return {
        "account": selected["name"],
        "accountType": selected["type"],
        "selectedProfile": selected_identifier,
        "localProfiles": [item["name"] for item in profiles["local"]],
        "microsoftAccounts": [{"id": item["id"], "name": item["name"]} for item in accounts],
        "microsoftAccount": account_name(),
        "microsoftId": account_id(),
        "avatar": profile_avatars.get(selected_identifier),
        "profileAvatars": profile_avatars,
        "localSkinSet": selected["type"] == "local" and (data_dir() / "minecraft/CustomSkinLoader/LocalSkin/skins" / f"{selected['name']}.png").is_file(),
        "modCount": mod_count,
        "discordConfigured": bool(str(config.get("discord_application_id", "")).strip()),
        "packConfigured": bool(config.get("manifest_url")),
        "localManifest": config.get("manifest_url", "").startswith("file:"),
        "clientConfigured": bool(config.get("microsoft_client_id")),
        "installed": local,
        "gameDirectory": str(data_dir() / "minecraft"),
        "memoryMb": int(config.get("memory_mb", 8192)),
        "memoryLimitMb": memory_limit_mb(),
        "systemMemoryMb": system_memory_mb(),
        "resolutionWidth": int(config.get("resolution_width", 854)),
        "resolutionHeight": int(config.get("resolution_height", 480)),
        "customResolution": bool(config.get("custom_resolution", False)),
    }
