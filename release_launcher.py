"""Create the release manifest after building the Windows installer."""

import argparse
import json
import urllib.parse
from pathlib import Path

from launcher_updates import VERSION, _hash_file
from standalone import read_config

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="HTTPS directory where the installer will be uploaded")
    parser.add_argument("--installer-base-url", help="HTTPS GitHub Release directory for the installer")
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        parser.error("La URL base debe usar HTTPS.")
    expected = str(read_config().get("launcher_update_url", "")).strip()
    manifest_url = args.base_url.rstrip("/") + "/launcher-update.json"
    if manifest_url != expected:
        parser.error(f"La URL de publicación debe coincidir con la configurada en el launcher: {expected or 'sin configurar'}")
    installer = ROOT / "dist" / f"PlanetaPanetones-Setup-{VERSION}.exe"
    if not installer.is_file():
        parser.error(f"No existe el instalador: {installer}")
    installer_base = (args.installer_base_url or args.base_url).rstrip("/")
    installer_location = urllib.parse.urlsplit(installer_base)
    if (installer_location.scheme != "https" or not installer_location.netloc
            or installer_location.username or installer_location.password
            or installer_location.query or installer_location.fragment):
        parser.error("La URL del instalador debe ser una carpeta HTTPS pública.")
    manifest = {"version": VERSION, "installer": {
        "url": installer_base + "/" + installer.name,
        "size": installer.stat().st_size,
        "sha256": _hash_file(installer),
    }}
    destination = ROOT / "dist" / "launcher-update.json"
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
