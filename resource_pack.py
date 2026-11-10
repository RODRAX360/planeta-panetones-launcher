"""Install Punchy Moves animations from their creator's official download."""

import hashlib
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


# The creator does not permit redistribution. Download this pinned public release
# directly from Modrinth for each player; never put it in our modpack archives.
ANIMATION_PACK_NAME = "Fluid & Foolish 1.0.1.zip"
COMPATIBLE_PACK_NAME = "Fluid & Foolish 1.0.1-Planeta-Compat.zip"
ANIMATION_PACK_URL = (
    "https://cdn.modrinth.com/data/fQdwNxte/versions/UAp4jRDk/"
    "Fluid%20%26%20Foolish%201.0.1.zip"
)
ANIMATION_PACK_SHA512 = (
    "09544efccdb63bbd6a2f583184bea82cfe01c78cd36f9bf9343cd8cc0243b19d"
    "7993aa280481d42c68c4b19e6abb3b52346d93115d48b50e1e37be9c53efafb9"
)
ANIMATION_PACK_SIZE = 1881476
SETTINGS_PACK_NAME = "Planeta-Panetones-Punchy-Ajustes.zip"

# Keep the same priority as the resource pack list in the Forge 1.20.1 profile.
# Entries for files are enabled only when the pack was included in the edition.
PROFILE_PACK_ORDER = (
    "mod/punchy:punchy",
    "vanilla",
    "mod_resources",
    "file/FreshAnimations_v1.10.4.zip",
    "generated/fragmentum_layer",
    "file/Icons v.1.14.zip",
    "file/cubic-sun-moon-v1.8.5.zip",
    "file/[1.6] Enhanced Boss Bars.zip",
    "file/SPEMOTES_TRANSLATIONS_v1.1.zip",
)


def _verified_pack(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size != ANIMATION_PACK_SIZE:
        return False
    digest = hashlib.sha512()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest() == ANIMATION_PACK_SHA512


def _download_official_pack(destination: Path) -> None:
    if _verified_pack(destination):
        return
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    digest = hashlib.sha512()
    size = 0
    try:
        with urllib.request.urlopen(ANIMATION_PACK_URL, timeout=45) as response:
            if urllib.parse.urlparse(response.geturl()).scheme != "https":
                raise ValueError("La descarga de animaciones salió de HTTPS.")
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > ANIMATION_PACK_SIZE:
                        raise ValueError("El paquete de animaciones supera el tamaño publicado.")
                    digest.update(chunk)
                    output.write(chunk)
        if size != ANIMATION_PACK_SIZE or digest.hexdigest() != ANIMATION_PACK_SHA512:
            raise ValueError("El paquete de animaciones no coincide con el archivo del autor.")
        with zipfile.ZipFile(temporary) as archive:
            if ("pack.mcmeta" not in archive.namelist() or
                    "assets/punchy_moves/compat/develop.json" not in archive.namelist()):
                raise ValueError("El paquete oficial no contiene las animaciones esperadas.")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _write_settings_pack(destination: Path) -> None:
    """Disable the broken random idle event while keeping normal idle and movement."""
    contents = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": 15,
                                           "description": "Ajustes de animación de Planeta Panetones"}}),
        "assets/punchy_moves/compat/zz_planeta_idle.json": json.dumps({
            "format_version": 2,
            "defaults": {"animations": {"idle_events": {
                "variants": ["idle_event_one_backup"], "chance": 0
            }}}
        }),
    }
    temporary = destination.with_name(destination.name + ".part")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in contents.items():
                archive.writestr(name, content)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _write_compatible_pack(source: Path, destination: Path) -> None:
    """Fix only invalid Punchy Moves metadata in a local copy of the creator's pack."""
    temporary = destination.with_name(destination.name + ".part")
    try:
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(temporary, "w") as patched:
            for info in original.infolist():
                content = original.read(info.filename)
                if info.filename == "assets/punchy_moves/compat/develop.json":
                    data = json.loads(content)
                    for group, animation in (("TRIDENT", "idle"), ("SHIELD", "use_item")):
                        data.get("item_groups", {}).get(group, {}).get("animations", {}).get(animation, {}).pop(
                            "base_pose_retain", None)
                    idle = data.get("defaults", {}).get("animations", {}).get("idle_events", {})
                    if not idle.get("variants"):
                        idle["variants"] = ["idle_event_one_backup", "idle_event_two_backup"]
                    content = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                patched.writestr(info, content)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _activate_packs(options_path: Path) -> None:
    raw = options_path.read_text(encoding="utf-8") if options_path.is_file() else ""
    lines = raw.splitlines()
    index = next((i for i, line in enumerate(lines) if line.startswith("resourcePacks:")), None)
    if index is None:
        selected = ["vanilla", "mod_resources"]
    else:
        try:
            selected = json.loads(lines[index].partition(":")[2])
        except json.JSONDecodeError as exc:
            raise ValueError("Minecraft tiene una lista de paquetes de recursos dañada.") from exc
        if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
            raise ValueError("Minecraft tiene una lista de paquetes de recursos inválida.")
    folder = options_path.parent / "resourcepacks"
    selected = [item for item in selected if not (
        item.startswith("file/Fluid & Foolish ") or
        item == "file/" + SETTINGS_PACK_NAME or
        item in PROFILE_PACK_ORDER
    )]
    selected = [item for item in PROFILE_PACK_ORDER
                if not item.startswith("file/") or (folder / item[5:]).is_file()] + selected
    selected.extend(("file/" + COMPATIBLE_PACK_NAME, "file/" + SETTINGS_PACK_NAME))
    entry = "resourcePacks:" + json.dumps(selected, ensure_ascii=True, separators=(",", ":"))
    if index is None:
        lines.append(entry)
    else:
        lines[index] = entry
    updated = "\n".join(lines) + "\n"
    if updated != raw:
        temporary = options_path.with_name(options_path.name + ".part")
        try:
            temporary.write_text(updated, encoding="utf-8")
            temporary.replace(options_path)
        finally:
            temporary.unlink(missing_ok=True)


def ensure_animation_pack(game_dir: Path) -> None:
    folder = game_dir / "resourcepacks"
    folder.mkdir(parents=True, exist_ok=True)
    _download_official_pack(folder / ANIMATION_PACK_NAME)
    _write_compatible_pack(folder / ANIMATION_PACK_NAME, folder / COMPATIBLE_PACK_NAME)
    _write_settings_pack(folder / SETTINGS_PACK_NAME)
    _activate_packs(game_dir / "options.txt")
