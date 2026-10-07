"""Detect Blender 4.4.x and the validated decorative template."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app import ccstudio_py, output_root, template_candidates, user_data_root


@dataclass(frozen=True)
class EnvironmentCheck:
    ok: bool
    blender: Path | None
    blender_label: str
    template: Path | None
    template_label: str
    script: Path | None
    messages: tuple[str, ...]


def find_blender_44() -> Path | None:
    candidates = [
        Path(r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 4.4.3\blender.exe"),
    ]
    for path in candidates:
        if path.is_file():
            return path

    base = Path(r"C:\Program Files\Blender Foundation")
    if not base.is_dir():
        return None

    dirs = sorted(
        (d for d in base.iterdir() if d.is_dir() and re.match(r"^Blender 4\.4", d.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    for d in dirs:
        exe = d / "blender.exe"
        if exe.is_file():
            return exe
    return None


def find_template() -> Path | None:
    for path in template_candidates():
        if path.is_file():
            return path
    return None


def check_environment() -> EnvironmentCheck:
    messages: list[str] = []
    blender = find_blender_44()
    template = find_template()
    script = ccstudio_py() if ccstudio_py().is_file() else None

    if blender:
        messages.append(f"Blender encontrado: {blender}")
    else:
        messages.append("Blender 4.4.x não encontrado em Program Files.")

    if template:
        messages.append(f"Template encontrado: {template}")
    else:
        messages.append("Template decorativo não encontrado (templates/decor_vase/template.blend).")

    if script:
        messages.append(f"Motor encontrado: {script}")
    else:
        messages.append("ccstudio.py não encontrado no bundle/aplicação.")

    messages.append(f"Saída: {output_root()}")
    messages.append(f"Dados do usuário: {user_data_root()}")

    ok = bool(blender and template and script)
    return EnvironmentCheck(
        ok=ok,
        blender=blender,
        blender_label=str(blender) if blender else "(não encontrado)",
        template=template,
        template_label=str(template) if template else "(não encontrado)",
        script=script,
        messages=tuple(messages),
    )
