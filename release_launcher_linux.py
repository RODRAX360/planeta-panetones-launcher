"""Write the public Linux update manifest after the AppImage is built."""

import hashlib
import json
from pathlib import Path

from version import VERSION

ROOT = Path(__file__).resolve().parent
REPOSITORY = "RODRAX360/planeta-panetones-launcher"


def main() -> None:
    artifact = ROOT / "dist" / f"PlanetaPanetones-{VERSION}-x86_64.AppImage"
    digest = hashlib.sha256()
    with artifact.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    manifest = {"version": VERSION, "installer": {
        "url": f"https://github.com/{REPOSITORY}/releases/download/launcher-linux-v{VERSION}/{artifact.name}",
        "size": artifact.stat().st_size,
        "sha256": digest.hexdigest(),
    }}
    output = ROOT / "dist/launcher-update-linux.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
