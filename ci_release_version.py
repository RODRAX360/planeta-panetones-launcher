"""Choose one new launcher version for both release jobs in GitHub Actions.

``prepare`` reads the source version, both update feeds, and historical release
tags. The public ``launcher`` release stays at one URL and its tag has no
version; only the feeds need an increasing internal version. ``stamp`` changes
only the temporary CI checkout before building.
"""

import argparse
import ast
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "version.py"
VERSION_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
LEGACY_RELEASE_TAG_PATTERN = re.compile(r"launcher(?:-linux)?-v([0-9]+\.[0-9]+\.[0-9]+)\Z")
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
FEEDS = ("launcher-update.json", "launcher-update-linux.json")


def version_parts(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
        raise ValueError(f"Versión de launcher no válida: {value!r}")
    return tuple(int(part) for part in value.split("."))


def _version_assignment(source: str) -> ast.Assign:
    assignments = [node for node in ast.parse(source).body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "VERSION"
                           for target in node.targets)]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Constant) \
            or not isinstance(assignments[0].value.value, str):
        raise ValueError("version.py debe asignar VERSION a un único texto literal.")
    if assignments[0].lineno != assignments[0].end_lineno:
        raise ValueError("La asignación de VERSION debe ocupar una sola línea.")
    return assignments[0]


def source_version(path: Path = VERSION_FILE) -> str:
    source = path.read_text(encoding="utf-8")
    value = _version_assignment(source).value.value
    version_parts(value)
    return value


def stamp_version(version: str, path: Path = VERSION_FILE) -> None:
    version_parts(version)
    source = path.read_text(encoding="utf-8")
    assignment = _version_assignment(source)
    lines = source.splitlines(keepends=True)
    line = lines[assignment.lineno - 1]
    # Restrict rewriting to a straightforward assignment, never another statement.
    if not re.fullmatch(r"VERSION\s*=\s*(['\"])[0-9]+\.[0-9]+\.[0-9]+\1\s*", line):
        raise ValueError("La línea de VERSION tiene un formato inesperado.")
    ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    lines[assignment.lineno - 1] = f'VERSION = "{version}"{ending}'
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text("".join(lines), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _github_json(url: str, token: str):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "PlanetaPanetones-release",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def published_versions(repository: str, token: str) -> list[tuple[int, int, int]]:
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ValueError("GITHUB_REPOSITORY debe tener formato propietario/repositorio.")
    if not token:
        raise ValueError("Falta GH_TOKEN para consultar las publicaciones.")
    base = f"https://api.github.com/repos/{repository}"
    versions = []
    page = 1
    while True:
        releases = _github_json(f"{base}/releases?per_page=100&page={page}", token)
        if not isinstance(releases, list):
            raise ValueError("GitHub no devolvió una lista de publicaciones.")
        for release in releases:
            if not isinstance(release, dict):
                continue
            match = LEGACY_RELEASE_TAG_PATTERN.fullmatch(str(release.get("tag_name", "")))
            if match:
                versions.append(version_parts(match.group(1)))
        if len(releases) < 100:
            break
        page += 1

    for feed in FEEDS:
        url = f"{base}/contents/{urllib.parse.quote(feed)}?ref=main"
        try:
            item = _github_json(url, token)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        if not isinstance(item, dict) or item.get("encoding") != "base64":
            raise ValueError(f"GitHub no devolvió el contenido de {feed}.")
        try:
            manifest = json.loads(base64.b64decode(item["content"], validate=False))
            versions.append(version_parts(manifest["version"]))
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise ValueError(f"El manifiesto {feed} no tiene una versión válida.") from exc
    return versions


def next_release_version(repository: str, token: str, path: Path = VERSION_FILE) -> str:
    base = max((version_parts(source_version(path)), *published_versions(repository, token)))
    return f"{base[0]}.{base[1]}.{base[2] + 1}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("prepare", help="Calcular la nueva versión y escribir GITHUB_OUTPUT")
    stamp = subcommands.add_parser("stamp", help="Aplicar la versión al checkout temporal")
    stamp.add_argument("version")
    args = parser.parse_args()
    if args.command == "stamp":
        stamp_version(args.version)
        print(f"Compilando launcher {args.version}.")
        return
    version = next_release_version(os.environ.get("GITHUB_REPOSITORY", ""),
                                   os.environ.get("GH_TOKEN", ""))
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise SystemExit("Falta GITHUB_OUTPUT.")
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"version={version}\n")
    print(f"Versión preparada: {version}.")


if __name__ == "__main__":
    main()
