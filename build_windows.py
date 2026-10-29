"""Build the Windows desktop app and per-user NSIS installer on Windows."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from build_release_windows import verify_pack_manifest
from launcher_updates import VERSION

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-only", action="store_true",
                        help="Crear la aplicación sin ejecutar NSIS (para compilar NSIS por separado)")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("El instalador de Windows debe compilarse en Windows.")
    config = json.loads((ROOT / "launcher-config.json").read_text(encoding="utf-8"))
    if not str(config.get("manifest_url", "")).startswith("https://"):
        raise SystemExit("Configura manifest_url con el hosting HTTPS antes de crear el instalador.")
    if not str(config.get("optimized_manifest_url", "")).startswith("https://"):
        raise SystemExit("Configura optimized_manifest_url con el hosting HTTPS antes de crear el instalador.")
    try:
        verify_pack_manifest(config["manifest_url"], "principal")
        verify_pack_manifest(config["optimized_manifest_url"], "optimizada")
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Los manifiestos del pack deben estar publicados antes de compilar: {exc}") from exc
    if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
        raise SystemExit("La versión del launcher debe ser X.Y.Z.")
    try:
        import PyInstaller  # noqa: F401
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Instala las dependencias de compilación: pip install pyinstaller pillow") from exc
    makensis = None if args.bundle_only else shutil.which("makensis")
    if not args.bundle_only and not makensis:
        raise SystemExit("Instala NSIS y añade makensis.exe al PATH.")
    icon = ROOT / "assets/launcher.ico"
    with Image.open(ROOT / "assets/icono.png") as image:
        image.convert("RGBA").save(icon, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    resources = [ROOT / name for name in ("index.html", "app.js", "style.css", "launcher-config.json", "assets")]
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
               "--name", "PlanetaPanetones", "--icon", str(icon), "--distpath", str(ROOT / "dist"),
               "--workpath", str(ROOT / "build"), "--specpath", str(ROOT)]
    for resource in resources:
        command += ["--add-data", f"{resource};{resource.name if resource.is_dir() else '.'}"]
    command.append(str(ROOT / "main.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    bundle = ROOT / "dist" / "PlanetaPanetones"
    unexpected = [base / name for base in (bundle, bundle / "_internal")
                  for name in ("publicar", "bundled_mods", "minecraft", "instances")
                  if (base / name).exists()]
    if unexpected:
        raise SystemExit("La compilación contiene archivos del pack. Borra dist/PlanetaPanetones y vuelve a compilar.")
    if not args.bundle_only:
        subprocess.run([makensis, f"/DAPP_VERSION={VERSION}", "windows.nsi"], cwd=ROOT / "installer", check=True)
        print(ROOT / "dist" / f"PlanetaPanetones-Setup-{VERSION}.exe")
    else:
        print(ROOT / "dist" / "PlanetaPanetones")


if __name__ == "__main__":
    main()
