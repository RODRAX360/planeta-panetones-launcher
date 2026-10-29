"""Prepare GitHub Release ZIP assets and small manifests for the launcher."""

import argparse
import json
import re
import zipfile
from pathlib import Path

from updater import sha256_file

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist" / "github-pack"


def prepare(edition: str, repository: str, tag: str) -> tuple[Path, Path]:
    source = ROOT / "publicar" / ("optimizado" if edition == "optimizada" else "")
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("edition", "principal") != edition:
        raise ValueError(f"El manifiesto de {edition} no corresponde a esa instancia.")
    assets = source / "files"
    output_manifest = OUTPUT / ("optimizado" if edition == "optimizada" else "") / "manifest.json"
    archive = OUTPUT / f"pack-{edition}.zip"
    temporary = archive.with_suffix(".zip.part")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for entry in manifest["files"]:
                relative = Path(entry["path"])
                file = assets / relative
                if not file.is_file() or file.stat().st_size != entry["size"] or sha256_file(file) != entry["sha256"]:
                    raise ValueError(f"El archivo del pack cambió: {edition}/{relative}")
                bundle.write(file, arcname=relative.as_posix())
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    manifest["archive"] = {
        "url": f"https://github.com/{repository}/releases/download/{tag}/{archive.name}",
        "size": archive.stat().st_size,
        "sha256": sha256_file(archive),
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return archive, output_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="RODRAX360/planeta-panetones-launcher")
    parser.add_argument("--tag", default="pack-2026.10.2")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("Usa un repositorio en formato usuario/nombre.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.tag):
        parser.error("La etiqueta de la Release contiene caracteres inválidos.")
    for edition in ("principal", "optimizada"):
        archive, manifest = prepare(edition, args.repository, args.tag)
        print(f"{archive} ({archive.stat().st_size / 1024**2:.1f} MiB)")
        print(manifest)


if __name__ == "__main__":
    main()
