#!/usr/bin/env python3
"""Prepara un directorio estático para subir a un servidor HTTPS."""

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path.home() / ".var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/Forge 1.20.1"
ROOT = Path(__file__).resolve().parent
DEFAULT_DEST = ROOT / "publicar"
EXTRA_MODS = ROOT / "bundled_mods"
FOLDERS = ("mods", "config", "defaultconfigs", "resourcepacks", "shaderpacks", "emotes", "customnpcs")
PROFILE_OPTIONS = Path("config/planeta/profile-options.txt")
SKIN_MOD_NAME = "CustomSkinLoader_ForgeV2-14.28.jar"
SKIN_COMPAT_NAME = "CustomSkinLoader_ForgeV2-14.28-PlanetaCompat.jar"
SKIN_COREMOD_OLD = ("'net/minecraft/client/renderer/entity/player/PlayerRenderer', "
                    "'net/minecraft/client/renderer/entity/layers/CapeLayer'")
SKIN_COREMOD_NEW = "'net/minecraft/client/renderer/entity/player/PlayerRenderer'"


def included(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    relative = path.relative_to(SOURCE)
    parts = relative.parts
    if not parts or parts[0] not in FOLDERS:
        return False
    if relative == PROFILE_OPTIONS:
        return False
    if parts[0] == "mods":
        return len(parts) == 2 and path.suffix.lower() == ".jar" and not path.name.lower().startswith("jei-")
    if parts[:2] == ("config", "jei"):
        return False
    if parts[0] == "resourcepacks" and path.name.startswith("Fluid & Foolish "):
        return False
    if parts[0] == "config" and ("cubosu_server" in parts or path.name in
            {"player-volumes.properties", "voicechat-server.properties", "watut-server.toml"}):
        return False
    if any(part.startswith(".") or part.lower() in {"world", "cache", "logs", "backups"}
           or part.lower().startswith("backup-") for part in parts):
        return False
    if any(word in path.name.lower() for word in
           ("cache", "history", "secret", "token", "password", ".before-", ".backup-")):
        return False
    if parts[:3] == ("config", "fancymenu", "customization") and \
            path.name == "com.github.alexthe666.iceandfire.client.gui.iceandfiremainmenu_layout.txt":
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


def write_profile_options(destination: Path) -> tuple[str, int]:
    """Publish game preferences, with JEI bindings and private server history removed."""
    source = (SOURCE / "options.txt").read_text(encoding="utf-8")
    excluded = ("resourcePacks:", "incompatibleResourcePacks:",
                "lastServer:", "key_key.jei.")
    cleaned = "\n".join(line for line in source.splitlines()
                        if not line.startswith(excluded)) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(cleaned, encoding="utf-8")
    data = cleaned.encode("utf-8")
    return hashlib.sha256(data).hexdigest(), len(data)


def copy_extra_mods(destination: Path) -> list[dict]:
    """Keep Custom Skin Loader; let Punchy Moves render capes to avoid a mixin failure."""
    entries = []
    for source in sorted(EXTRA_MODS.glob("*.jar")):
        if source.name == SKIN_MOD_NAME:
            relative = Path("mods") / SKIN_COMPAT_NAME
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".part")
            with zipfile.ZipFile(source) as original, zipfile.ZipFile(temporary, "w") as patched:
                for info in original.infolist():
                    if info.filename.upper().startswith("META-INF/") and info.filename.upper().endswith(
                            (".SF", ".DSA", ".RSA")):
                        continue
                    content = original.read(info.filename)
                    if info.filename == "META-INF/MANIFEST.MF":
                        # The original signature covers transformers.js. Strip its
                        # digest sections when publishing the modified GPL jar.
                        content = content.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
                    if info.filename == "transformers.js":
                        text = content.decode("utf-8")
                        if text.count(SKIN_COREMOD_OLD) != 1:
                            raise ValueError("Cambió el transformador de capas de Custom Skin Loader.")
                        content = text.replace(SKIN_COREMOD_OLD, SKIN_COREMOD_NEW).encode("utf-8")
                    patched.writestr(info, content)
            temporary.replace(target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            size = target.stat().st_size
        else:
            relative = Path("mods") / source.name
            digest, size = copy_and_hash(source, destination / relative)
        entries.append({"path": relative.as_posix(), "sha256": digest, "size": size})
    return entries


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
    extras = copy_extra_mods(destination / "files")
    files.extend(extras)
    sha256, size = write_profile_options(destination / "files" / PROFILE_OPTIONS)
    files.append({"path": PROFILE_OPTIONS.as_posix(), "sha256": sha256, "size": size})
    total += sum(entry["size"] for entry in extras) + size
    files.sort(key=lambda entry: entry["path"])
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
