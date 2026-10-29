"""Build a Windows installer and its update manifest for one HTTPS release URL."""

import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "launcher-config.json"


def release_urls(base_url: str) -> tuple[str, str, str]:
    base = base_url.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(base)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("La URL base debe ser una carpeta HTTPS pública sin usuario, consulta ni fragmento.")
    return (base + "/manifest.json", base + "/optimizado/manifest.json",
            base + "/launcher-update.json")


def verify_pack_manifest(url: str, edition: str) -> None:
    with urllib.request.urlopen(url, timeout=25) as response:
        if urllib.parse.urlsplit(response.geturl()).scheme != "https":
            raise ValueError("El manifiesto redirige fuera de HTTPS.")
        content = response.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("El manifiesto supera los 5 MiB.")
    manifest = json.loads(content)
    if (manifest.get("schema") != 1 or manifest.get("minecraft") != "1.20.1"
            or manifest.get("forge") != "47.4.20"
            or manifest.get("edition", "principal") != edition
            or not isinstance(manifest.get("files"), list)):
        raise ValueError(f"El manifiesto de {edition} no corresponde al pack esperado.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True,
                        help="Carpeta HTTPS pública que contendrá manifest.json y optimizado/manifest.json")
    parser.add_argument("--installer-base-url",
                        help="Carpeta HTTPS de la Release que contendrá el instalador (si es distinta)")
    args = parser.parse_args()
    try:
        manifest_url, optimized_url, update_url = release_urls(args.base_url)
        if args.installer_base_url:
            release_urls(args.installer_base_url)
    except ValueError as exc:
        parser.error(str(exc))
    if sys.platform != "win32":
        parser.error("El instalador .exe debe compilarse en Windows.")

    try:
        verify_pack_manifest(manifest_url, "principal")
        verify_pack_manifest(optimized_url, "optimizada")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(f"Publica ambos packs antes de compilar: {exc}")

    original = CONFIG.read_bytes()
    config = json.loads(original)
    config.update(manifest_url=manifest_url, optimized_manifest_url=optimized_url,
                  launcher_update_url=update_url)
    try:
        CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "build_windows.py")], cwd=ROOT, check=True)
        publish_command = [sys.executable, str(ROOT / "release_launcher.py"),
                           "--base-url", args.base_url.strip().rstrip("/")]
        if args.installer_base_url:
            publish_command += ["--installer-base-url", args.installer_base_url.strip().rstrip("/")]
        subprocess.run(publish_command, cwd=ROOT, check=True)
    finally:
        CONFIG.write_bytes(original)

    print("Instalador y launcher-update.json listos en dist/.")
    print("Sube primero el instalador; publica launcher-update.json al final.")


if __name__ == "__main__":
    main()
