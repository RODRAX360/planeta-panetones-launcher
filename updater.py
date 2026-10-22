"""Descarga incremental y verificada de los archivos del modpack."""

import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Callable


def safe_relative(raw: str) -> Path:
    if not isinstance(raw, str) or "\\" in raw or ":" in raw or raw.startswith("/"):
        raise ValueError(f"Ruta inválida en el manifiesto: {raw}")
    posix = PurePosixPath(raw)
    if (posix.is_absolute() or not posix.parts or posix.parts[0] not in
            {"mods", "config", "defaultconfigs", "resourcepacks", "shaderpacks", "emotes", "customnpcs"}
            or len(posix.parts) < 2 or any(part in {"", ".", ".."} for part in raw.split("/"))):
        raise ValueError(f"Ruta inválida en el manifiesto: {raw}")
    return Path(*posix.parts)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(url: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"https", "file"}:
        raise ValueError("El manifiesto debe estar en HTTPS.")
    with urllib.request.urlopen(url, timeout=25) as response:
        if parsed.scheme == "https" and urllib.parse.urlparse(response.geturl()).scheme != "https":
            raise ValueError("El hosting redirigió el manifiesto fuera de HTTPS.")
        data = response.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("El manifiesto excede el tamaño permitido.")
    manifest = json.loads(data)
    if manifest.get("schema") != 1 or manifest.get("minecraft") != "1.20.1" or manifest.get("forge") != "47.4.20":
        raise ValueError("El manifiesto no corresponde al pack Forge 1.20.1.")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("El manifiesto no contiene la lista de archivos.")
    seen = set()
    for entry in files:
        relative = safe_relative(entry["path"])
        if relative.as_posix() in seen:
            raise ValueError("Hay archivos duplicados en el manifiesto.")
        seen.add(relative.as_posix())
        if (not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
                or type(entry["size"]) is not int or entry["size"] < 0):
            raise ValueError(f"Datos de integridad inválidos: {relative}")
    return manifest


def sync_pack(manifest_url: str, game_dir: Path, progress: Callable[[str, int, int], None]) -> dict:
    manifest = load_manifest(manifest_url)
    game_dir.mkdir(parents=True, exist_ok=True)
    root = game_dir.resolve()
    files = manifest["files"]
    for index, entry in enumerate(files, 1):
        relative = safe_relative(entry["path"])
        target = root / relative
        if target.is_symlink() or target.resolve().is_relative_to(root) is False:
            raise ValueError(f"Ruta insegura: {relative}")
        if target.is_file() and target.stat().st_size == entry["size"] and sha256_file(target) == entry["sha256"]:
            progress(f"Verificado: {relative.name}", index, len(files))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        parts = [urllib.parse.quote(part, safe="") for part in relative.parts]
        source_url = urllib.parse.urljoin(manifest_url, "files/" + "/".join(parts))
        temporary = target.with_name(target.name + ".part")
        digest = hashlib.sha256()
        size = 0
        progress(f"Descargando: {relative.name}", index, len(files))
        try:
            with urllib.request.urlopen(source_url, timeout=45) as response, temporary.open("wb") as output:
                if urllib.parse.urlparse(manifest_url).scheme == "https" and urllib.parse.urlparse(response.geturl()).scheme != "https":
                    raise ValueError(f"El hosting redirigió {relative} fuera de HTTPS.")
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
                    size += len(chunk)
                    if size > entry["size"]:
                        raise ValueError(f"La descarga de {relative} supera el tamaño esperado.")
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
            temporary.unlink(missing_ok=True)
            raise ValueError(f"La descarga de {relative} no coincide con el manifiesto.")
        temporary.replace(target)
    lockfile = root / ".planeta-panetones-manifest.json"
    previous = json.loads(lockfile.read_text(encoding="utf-8")) if lockfile.is_file() else {"files": []}
    current_paths = {entry["path"] for entry in files}
    for entry in previous.get("files", []):
        if entry["path"] not in current_paths:
            target = root / safe_relative(entry["path"])
            if target.is_file() and sha256_file(target) == entry["sha256"]:
                target.unlink()
    lockfile.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
