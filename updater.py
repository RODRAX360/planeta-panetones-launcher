"""Descarga incremental y verificada de los archivos del modpack."""

import hashlib
import json
import re
import urllib.parse
import urllib.request
import zipfile
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
    archive = manifest.get("archive")
    if archive is not None:
        if not isinstance(archive, dict):
            raise ValueError("El paquete de la instancia es inválido.")
        archive_url = archive.get("url")
        parsed_archive = urllib.parse.urlparse(archive_url) if isinstance(archive_url, str) else None
        if (not parsed_archive or parsed_archive.scheme != "https" or not parsed_archive.netloc
                or parsed_archive.username or parsed_archive.password
                or not isinstance(archive.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", archive["sha256"])
                or type(archive.get("size")) is not int
                or not 0 < archive["size"] <= 2 * 1024 * 1024 * 1024):
            raise ValueError("La URL o integridad del paquete es inválida.")
    return manifest


def install_archive(archive: dict, pending: list, root: Path,
                    progress: Callable[[str, int, int], None]) -> None:
    """Download one release asset, verify it, then install only missing pack files."""
    temporary_archive = root / ".planeta-panetones-pack.zip.part"
    if temporary_archive.is_symlink():
        raise ValueError("Ruta insegura para la descarga del paquete.")
    digest = hashlib.sha256()
    size = 0
    try:
        progress("Descargando paquete de la instancia…", 0, archive["size"])
        with urllib.request.urlopen(archive["url"], timeout=45) as response, temporary_archive.open("wb") as output:
            if urllib.parse.urlparse(response.geturl()).scheme != "https":
                raise ValueError("La descarga del paquete redirigió fuera de HTTPS.")
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > archive["size"]:
                    raise ValueError("El paquete supera el tamaño publicado.")
                digest.update(chunk)
                output.write(chunk)
                progress("Descargando paquete de la instancia…", size, archive["size"])
        if size != archive["size"] or digest.hexdigest() != archive["sha256"]:
            raise ValueError("El paquete descargado no coincide con su SHA-256.")
        with zipfile.ZipFile(temporary_archive) as bundle:
            for index, (entry, relative, target) in enumerate(pending, 1):
                try:
                    member = bundle.getinfo(relative.as_posix())
                except KeyError as exc:
                    raise ValueError(f"Falta {relative} en el paquete.") from exc
                if member.is_dir() or member.file_size != entry["size"]:
                    raise ValueError(f"Tamaño incorrecto de {relative} en el paquete.")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink() or not target.resolve().is_relative_to(root):
                    raise ValueError(f"Ruta insegura: {relative}")
                temporary_file = target.with_name(target.name + ".part")
                if temporary_file.is_symlink():
                    raise ValueError(f"Ruta insegura: {relative}")
                file_digest = hashlib.sha256()
                file_size = 0
                try:
                    with bundle.open(member) as source, temporary_file.open("wb") as output:
                        while chunk := source.read(1024 * 1024):
                            file_size += len(chunk)
                            if file_size > entry["size"]:
                                raise ValueError(f"El archivo {relative} supera el tamaño esperado.")
                            file_digest.update(chunk)
                            output.write(chunk)
                    if file_size != entry["size"] or file_digest.hexdigest() != entry["sha256"]:
                        raise ValueError(f"El archivo {relative} no coincide con el manifiesto.")
                    temporary_file.replace(target)
                finally:
                    temporary_file.unlink(missing_ok=True)
                progress(f"Instalando: {relative.name}", index, len(pending))
    finally:
        temporary_archive.unlink(missing_ok=True)


def sync_pack(manifest_url: str, game_dir: Path, progress: Callable[[str, int, int], None], *,
              verify_all: bool = False, expected_edition: str | None = None) -> dict:
    manifest = load_manifest(manifest_url)
    if expected_edition and manifest.get("edition", "principal") != expected_edition:
        raise ValueError("El manifiesto no corresponde a la instancia seleccionada.")
    game_dir.mkdir(parents=True, exist_ok=True)
    root = game_dir.resolve()
    files = manifest["files"]
    cache_path = root / ".planeta-panetones-checksums.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached, dict):
            cached = {}
    except (OSError, ValueError):
        cached = {}
    verified = {}
    pending = []
    archive = manifest.get("archive")
    for index, entry in enumerate(files, 1):
        relative = safe_relative(entry["path"])
        target = root / relative
        if target.is_symlink() or target.resolve().is_relative_to(root) is False:
            raise ValueError(f"Ruta insegura: {relative}")
        if target.is_file():
            info = target.stat()
            fresh = (not verify_all and cached.get(entry["path"]) ==
                     [entry["sha256"], entry["size"], info.st_mtime_ns])
            if info.st_size == entry["size"] and (fresh or sha256_file(target) == entry["sha256"]):
                verified[entry["path"]] = [entry["sha256"], entry["size"], info.st_mtime_ns]
                progress(f"Verificado: {relative.name}", index, len(files))
                continue
        if archive:
            pending.append((entry, relative, target))
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
        verified[entry["path"]] = [entry["sha256"], entry["size"], target.stat().st_mtime_ns]
    if archive and pending:
        install_archive(archive, pending, root, progress)
        for entry, _relative, target in pending:
            verified[entry["path"]] = [entry["sha256"], entry["size"], target.stat().st_mtime_ns]
    lockfile = root / ".planeta-panetones-manifest.json"
    previous = json.loads(lockfile.read_text(encoding="utf-8")) if lockfile.is_file() else {"files": []}
    current_paths = {entry["path"] for entry in files}
    for entry in previous.get("files", []):
        if entry["path"] not in current_paths:
            target = root / safe_relative(entry["path"])
            if target.is_file() and sha256_file(target) == entry["sha256"]:
                target.unlink()
    lockfile.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cache_temp = cache_path.with_suffix(".json.part")
    cache_temp.write_text(json.dumps(verified, separators=(",", ":")), encoding="utf-8")
    cache_temp.replace(cache_path)
    return manifest
