"""Project / bundle path helpers (dev repo and frozen .exe)."""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def resource_root() -> Path:
    """Read-only assets: repo root in dev, PyInstaller extract dir when frozen."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def exe_dir() -> Path | None:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return None


def user_data_root() -> Path:
    """Predictable writable home for packaged runs."""
    return Path.home() / "Documents" / "CCStudio"


def repo_root() -> Path:
    """Dev-only alias kept for older imports."""
    return resource_root()


def ccstudio_py() -> Path:
    return resource_root() / "ccstudio.py"


def template_candidates() -> list[Path]:
    roots: list[Path] = []
    ed = exe_dir()
    if ed is not None:
        roots.append(ed)
    roots.append(resource_root())

    paths: list[Path] = []
    for root in roots:
        paths.append(root / "templates" / "decor_vase" / "template.blend")
    # Dev fallback only (not bundled).
    if not is_frozen():
        paths.append(resource_root() / "fixtures" / "v0.1-vase" / "funcionasera.blend")
    return paths


def output_root() -> Path:
    if is_frozen():
        return user_data_root() / "output"
    return resource_root() / "output"
