#!/usr/bin/env python3
"""Prepara un directorio estático para subir a un servidor HTTPS."""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path.home() / ".var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/Forge 1.20.1"
ROOT = Path(__file__).resolve().parent
DEFAULT_DEST = ROOT / "publicar"
FOLDERS = ("mods", "config", "defaultconfigs", "resourcepacks", "shaderpacks", "emotes", "customnpcs")


def included(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    relative = path.relative_to(SOURCE)
    parts = relative.parts
    if not parts or parts[0] not in FOLDERS:
        return False
    if parts[0] == "mods":
        return len(parts) == 2 and path.suffix.lower() == ".jar"
    if parts[0] == "config" and ("cubosu_server" in parts or path.name in
            {"player-volumes.properties", "voicechat-server.properties", "watut-server.toml"}):
        return False
    if any(part.startswith(".") or part.lower() in {"world", "cache", "logs", "backups"} for part in parts):
        return False
    if any(word in path.name.lower() for word in ("cache", "history", "secret", "token", "password")):
        return False
    if path.suffix.lower() in {".bak", ".log", ".tmp", ".lock"}:
        return False
    return True


def copy_and_hash(source: Path, destination: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    with source.open("rb") as reader, temporary.open("wb") as writer:
        while chunk := reader.read(1024 * 1024):
            digest.update(chunk)
            writer.write(chunk)
            size += len(chunk)
    temporary.replace(destination)
    shutil.copymode(source, destination)
    return digest.hexdigest(), size


def publish(destination: Path, version: str) -> dict:
    if not SOURCE.is_dir():
        raise FileNotFoundError(f"No se encontró la instancia: {SOURCE}")
    destination.mkdir(parents=True, exist_ok=True)
    selected = sorted(path for folder in FOLDERS for path in (SOURCE / folder).rglob("*") if included(path))
    files = []
    total = 0
    for index, source in enumerate(selected, 1):
        relative = source.relative_to(SOURCE)
        sha256, size = copy_and_hash(source, destination / "files" / relative)
        files.append({"path": relative.as_posix(), "sha256": sha256, "size": size})
        total += size
        if index % 25 == 0 or index == len(selected):
            print(f"Preparados {index}/{len(selected)} archivos", flush=True)
    active = {entry["path"] for entry in files}
    files_dir = destination / "files"
    for stale in files_dir.rglob("*"):
        if stale.is_file() and stale.relative_to(files_dir).as_posix() not in active:
            stale.unlink()
    manifest = {
        "schema": 1,
        "name": "Planeta Panetones",
        "version": version,
        "minecraft": "1.20.1",
        "forge": "47.4.20",
        "published_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    temporary = destination / "manifest.json.part"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination / "manifest.json")
    print(f"Listo: {len(files)} archivos, {total / 1024 / 1024:.1f} MiB en {destination}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=datetime.now().strftime("%Y.%m.%d.1"))
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    options = parser.parse_args()
    publish(options.dest.resolve(), options.version)
