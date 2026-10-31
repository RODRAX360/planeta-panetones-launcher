"""Write the public Linux update manifest after the AppImage is built."""

import hashlib
import json
import shutil
from pathlib import Path

from version import VERSION

ROOT = Path(__file__).resolve().parent
REPOSITORY = "RODRAX360/planeta-panetones-launcher"
STABLE_IMAGE_NAME = "PlanetaPanetones-x86_64.AppImage"


def main() -> None:
    built_image = ROOT / "dist" / f"PlanetaPanetones-{VERSION}-x86_64.AppImage"
    if not built_image.is_file():
        raise FileNotFoundError(f"No existe el AppImage compilado: {built_image}")
    artifact = ROOT / "dist" / STABLE_IMAGE_NAME
    shutil.copyfile(built_image, artifact)
    artifact.chmod(built_image.stat().st_mode)
    digest = hashlib.sha256()
    with artifact.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    manifest = {"version": VERSION, "installer": {
        "url": f"https://github.com/{REPOSITORY}/releases/download/launcher/{artifact.name}",
        "size": artifact.stat().st_size,
        "sha256": digest.hexdigest(),
    }}
    output = ROOT / "dist/launcher-update-linux.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
