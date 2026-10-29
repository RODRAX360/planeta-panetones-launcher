#!/usr/bin/env python3
"""Publica una variante Forge 1.20.1 sin cosméticos ni efectos opcionales."""

import argparse
import json
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from publish_pack import SOURCE, ROOT, EXTRA_MODS, copy_and_hash, included

# Son complementos visuales, de emotes o de interfaz. Los mods de contenido,
# rendimiento y sus dependencias obligatorias permanecen en la variante ligera.
OPTIONAL_MOD_IDS = {
    "advancementplaques", "animatedhearts", "cinematic", "emojiful",
    "immersiveui", "resourcify", "shouldersurfing", "sounds",
    "subtle_effects", "customskyboxes", "chatanimation", "eatinganimation",
    "entity_model_features", "entity_texture_features", "epicdeathscreen",
    "explosiveenhancement", "holdmyitems", "immersivehotbar",
    "notenoughanimations", "obscure_tooltips", "oculus", "particlerain",
    "particular", "skinlayers3d", "smoothswapping", "sodiumdynamiclights",
    "sodiumoptionsapi", "spatial_gui", "visuality", "watervision",
    "emotecraft", "emotecraft_borrow_their_emote",
    "emotecraft_fix_animate_texture", "stretch_emotecraft_compat",
    "cpm", "bendy_customnpcs_compat", "bendylib", "ruletahud", "gml",
    "mru", "mossylib", "iceberg", "fzzy_config",
    "yet_another_config_lib_v3", "watermedia_youtube_plugin", "chunky",
}

SKIP_CONFIG_PREFIXES = (
    "cubosu", "advancementplaques", "animatedhearts", "animation_overhaul",
    "betterthirdperson", "chat_heads", "chatanimation", "cinematic", "customskyboxes",
    "emojiful", "emotecraft", "entity_model_features", "entity_texture_features",
    "etf_warnings", "explosiveenhancement", "fzzy_config", "gml-script",
    "holdmyitems", "immersive-hotbar", "immersiveui", "notenoughanimations",
    "obscure", "oculus", "particlerain", "particular", "resourcify",
    "shouldersurfing", "skinlayers", "smoothswapping", "sodiumdynamiclights",
    "sounds", "spatial-gui", "subtle_effects", "visuality", "watervision",
    "yacl", "epicdeathscreen", "fml.toml.before", "gachaaddiction_lootr_seen",
)


def mod_details(path: Path) -> tuple[set[str], set[str]]:
    with zipfile.ZipFile(path) as archive:
        try:
            metadata = tomllib.loads(archive.read("META-INF/mods.toml").decode("utf-8-sig"))
        except KeyError as exc:
            if path.name.startswith("gml-"):
                return {"gml"}, set()
            if path.name.startswith("kotlinforforge-"):
                return {"kotlinforforge"}, set()
            raise ValueError(f"No se puede clasificar el mod {path.name}: falta mods.toml") from exc
    ids = {item["modId"] for item in metadata.get("mods", [])}
    required = {
        dependency["modId"]
        for mod_id in ids
        for dependency in metadata.get("dependencies", {}).get(mod_id, [])
        if dependency.get("mandatory") and dependency.get("modId") not in {"minecraft", "forge"}
    }
    return ids, required


def choose_mods(mods_folder: Path) -> tuple[list[Path], list[Path]]:
    records = [(path, *mod_details(path)) for path in sorted(mods_folder.glob("*.jar"))]
    by_id = {mod_id: path for path, ids, _ in records for mod_id in ids}
    kept = {path for path, ids, _ in records if not ids.intersection(OPTIONAL_MOD_IDS)}
    changed = True
    while changed:
        changed = False
        for path, _, dependencies in records:
            if path in kept:
                for mod_id in dependencies:
                    dependency = by_id.get(mod_id)
                    if dependency and dependency not in kept:
                        kept.add(dependency)
                        changed = True
    return sorted(kept), sorted(path for path, _, _ in records if path not in kept)


def publish(destination: Path, version: str) -> dict:
    if not SOURCE.is_dir():
        raise FileNotFoundError(f"No se encontró el perfil Forge 1.20.1 de Modrinth: {SOURCE}")
    selected_mods, removed_mods = choose_mods(SOURCE / "mods")
    selected = list(selected_mods)
    for folder in ("config", "defaultconfigs", "customnpcs"):
        for path in (SOURCE / folder).rglob("*"):
            if not included(path):
                continue
            relative = path.relative_to(SOURCE)
            if folder == "config" and relative.parts[1].lower().startswith(SKIP_CONFIG_PREFIXES):
                continue
            selected.append(path)
    selected.extend(sorted(EXTRA_MODS.glob("*.jar")))
    files = []
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(selected):
        relative = path.relative_to(EXTRA_MODS) if path.parent == EXTRA_MODS else path.relative_to(SOURCE)
        if path.parent == EXTRA_MODS:
            relative = Path("mods") / relative
        digest, size = copy_and_hash(path, destination / "files" / relative)
        files.append({"path": relative.as_posix(), "sha256": digest, "size": size})
    files.sort(key=lambda item: item["path"])
    active = {item["path"] for item in files}
    for old in (destination / "files").rglob("*"):
        if old.is_file() and old.relative_to(destination / "files").as_posix() not in active:
            old.unlink()
    manifest = {
        "schema": 1,
        "edition": "optimizada",
        "name": "Planeta Panetones Optimizada",
        "version": version,
        "minecraft": "1.20.1",
        "forge": "47.4.20",
        "published_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    temporary = destination / "manifest.json.part"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination / "manifest.json")
    print(f"Optimizada: {len(selected_mods) + len(list(EXTRA_MODS.glob('*.jar')))} mods, "
          f"{len(removed_mods)} opcionales excluidos, {len(files)} archivos, "
          f"{sum(item['size'] for item in files) / 1048576:.1f} MiB")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=datetime.now().strftime("%Y.%m.%d.1"))
    parser.add_argument("--dest", type=Path, default=ROOT / "publicar/optimizado")
    args = parser.parse_args()
    publish(args.dest.resolve(), args.version)
