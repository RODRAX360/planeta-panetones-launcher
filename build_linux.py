"""Build a portable x86_64 Linux AppImage without the Minecraft pack."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from build_release_windows import verify_pack_manifest
from version import VERSION

ROOT = Path(__file__).resolve().parent


def build(appimagetool: Path) -> Path:
    if not sys.platform.startswith("linux"):
        raise SystemExit("Compila el AppImage en Linux.")
    config = json.loads((ROOT / "launcher-config.json").read_text(encoding="utf-8"))
    for key, edition in (("manifest_url", "principal"), ("optimized_manifest_url", "optimizada")):
        url = str(config.get(key, ""))
        if not url.startswith("https://"):
            raise SystemExit(f"Configura {key} con una URL HTTPS pública.")
        verify_pack_manifest(url, edition)
    if not appimagetool.is_file():
        raise SystemExit(f"No se encontró appimagetool: {appimagetool}")
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Instala PyInstaller antes de compilar.") from exc

    resources = ["index.html", "app.js", "style.css", "launcher-config.json", "assets"]
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
               "--onedir", "--name", "PlanetaPanetones", "--distpath", str(ROOT / "dist"),
               "--workpath", str(ROOT / "build"), "--specpath", str(ROOT)]
    for name in resources:
        command += ["--add-data", f"{ROOT / name}:{name if name == 'assets' else '.'}"]
    command.append(str(ROOT / "main.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    bundle = ROOT / "dist/PlanetaPanetones"
    if any((bundle / "_internal" / name).exists() for name in ("publicar", "bundled_mods", "minecraft")):
        raise SystemExit("El ejecutable contiene archivos del modpack.")

    appdir = ROOT / "build/PlanetaPanetones.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    destination = appdir / "usr/opt/PlanetaPanetones"
    shutil.copytree(bundle, destination)
    (appdir / "AppRun").write_text(
        '#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\n'
        'exec "$HERE/usr/opt/PlanetaPanetones/PlanetaPanetones" "$@"\n',
        encoding="utf-8",
    )
    (appdir / "AppRun").chmod(0o755)
    (appdir / "planeta-panetones.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Planeta Panetones\n"
        "Comment=Launcher de Minecraft Forge 1.20.1\nExec=AppRun\n"
        "Icon=planeta-panetones\nTerminal=false\nCategories=Game;\n",
        encoding="utf-8",
    )
    shutil.copy2(ROOT / "assets/icono.png", appdir / "planeta-panetones.png")
    output = ROOT / "dist" / f"PlanetaPanetones-{VERSION}-x86_64.AppImage"
    environment = os.environ.copy()
    environment.update(ARCH="x86_64", APPIMAGE_EXTRACT_AND_RUN="1", VERSION=VERSION)
    subprocess.run([str(appimagetool), str(appdir), str(output)], env=environment, check=True)
    output.chmod(0o755)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appimagetool", required=True, type=Path)
    args = parser.parse_args()
    print(build(args.appimagetool.resolve()))


if __name__ == "__main__":
    main()
