"""Apply the Modrinth profile settings once per published template."""

import hashlib
from pathlib import Path


TEMPLATE = Path("config/planeta/profile-options.txt")
STAMP = ".planeta-profile-options-sha256"


def apply_profile_options(game_dir: Path) -> None:
    template_path = game_dir / TEMPLATE
    if not template_path.is_file():
        return
    template = template_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
    stamp = game_dir / STAMP
    if stamp.is_file() and stamp.read_text(encoding="ascii").strip() == digest:
        return
    options_path = game_dir / "options.txt"
    existing = options_path.read_text(encoding="utf-8") if options_path.is_file() else ""
    defaults = dict(line.split(":", 1) for line in template.splitlines() if ":" in line)
    lines = []
    seen = set()
    for line in existing.splitlines():
        key = line.partition(":")[0]
        if key.startswith("key_key.jei."):
            continue
        if key in defaults:
            lines.append(key + ":" + defaults[key])
            seen.add(key)
        else:
            lines.append(line)
    for key, value in defaults.items():
        if key not in seen:
            lines.append(key + ":" + value)
    updated = "\n".join(lines) + "\n"
    if existing != updated:
        if options_path.is_file():
            backup = game_dir / "options.txt.before-planeta-profile"
            if not backup.exists():
                backup.write_text(existing, encoding="utf-8")
        temporary = game_dir / "options.txt.part"
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(options_path)
    stamp.write_text(digest + "\n", encoding="ascii")
