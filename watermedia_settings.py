"""Discard a stale VLC path copied from an older published pack."""

from pathlib import Path


def remove_invalid_vlc_path(game_dir: Path) -> None:
    setting = game_dir / "config/watermedia/custom_vlc_path.txt"
    if not setting.is_file():
        return
    location = setting.read_text(encoding="utf-8").strip()
    if location and Path(location).is_dir():
        return
    setting.unlink()
