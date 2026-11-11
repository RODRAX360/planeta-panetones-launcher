#!/usr/bin/env python3
"""Publish the second launcher edition with the same current Modrinth profile."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from publish_pack import ROOT, publish as publish_profile


def publish(destination: Path, version: str) -> dict:
    manifest = publish_profile(destination, version)
    manifest["edition"] = "optimizada"
    manifest["name"] = "Planeta Panetones Optimizada"
    temporary = destination / "manifest.json.part"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination / "manifest.json")
    print("Optimizada: mismos mods y recursos del perfil Modrinth actual (sin JEI).")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=datetime.now().strftime("%Y.%m.%d.1"))
    parser.add_argument("--dest", type=Path, default=ROOT / "publicar/optimizado")
    args = parser.parse_args()
    publish(args.dest.resolve(), args.version)
