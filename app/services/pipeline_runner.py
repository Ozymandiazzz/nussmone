"""Call the frozen CC Studio pipeline (Blender + ccstudio.py). No motor logic here."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from app import is_frozen, output_root, resource_root
from app.services.detect import check_environment


LogFn = Callable[[str], None]


@dataclass
class PipelineResult:
    ok: bool
    status: str
    output_dir: Path | None
    blend: Path | None = None
    basecolor: Path | None = None
    report: Path | None = None
    log: Path | None = None
    message: str = ""
    exit_code: int | None = None
    lines: list[str] = field(default_factory=list)
    package: Path | None = None


def _safe_name(glb: Path) -> str:
    base = re.sub(r"[^\w\-.]+", "_", glb.stem).strip("_") or "run"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{stamp}"


def _unique_output_dir(glb: Path, name: str | None = None, create: bool = True) -> Path:
    """Create a unique output folder; never overwrite an existing one."""
    root = output_root()
    root.mkdir(parents=True, exist_ok=True)
    folder = name.strip() if name else _safe_name(glb)
    if re.search(r"[\\/:]", folder):
        raise ValueError("Nome de saída inválido (sem separadores de caminho).")

    out = root / folder
    if out.exists():
        # Auto-suffix instead of overwrite — desktop must never clobber silently.
        n = 2
        while True:
            candidate = root / f"{folder}_{n}"
            if not candidate.exists():
                out = candidate
                break
            n += 1
    if create:
        out.mkdir(parents=True, exist_ok=False)
    return out


def package_mode_available() -> bool:
    """The package prototype currently runs only from the local source checkout."""
    root = resource_root()
    return (not is_frozen() and
            (root / "experiments" / "v03_build_package.py").is_file() and
            (root / "recipes" / "decor_vase.json").is_file())


def run_package_pipeline(
    input_glb: Path,
    catalog_name: str,
    description: str,
    price: int,
    mesh_exporter: str = "s4s_local",
    donor: Path | None = None,
    blend_template: Path | None = None,
    rotate_x: float = 0.0,
    rotate_y: float = 0.0,
    rotate_z: float = 0.0,
    log: LogFn | None = None,
) -> PipelineResult:
    """Run the existing experimental package builder without changing the v0.1 engine."""
    def emit(message: str) -> None:
        if log:
            log(message)

    source = Path(input_glb).resolve()
    if not package_mode_available():
        return PipelineResult(False, "fail", None, message="Modo .package indisponível nesta instalação.")
    if not source.is_file() or source.suffix.lower() != ".glb":
        return PipelineResult(False, "fail", None, message=f"GLB inválido: {source}")
    if not catalog_name.strip() or not 0 <= price <= 1_000_000:
        return PipelineResult(False, "fail", None, message="Informe nome e preço entre 0 e 1.000.000.")
    if mesh_exporter not in ("s4s_local", "independent_local"):
        return PipelineResult(False, "fail", None, message="Motor de malha inválido.")

    root = resource_root()
    script = root / "experiments" / "v03_build_package.py"
    resource_args = ([] if donor is None else ["--donor", str(Path(donor).resolve())]) + (
        [] if blend_template is None else ["--blend-template", str(Path(blend_template).resolve())])
    try:
        check = subprocess.run(
            [sys.executable, str(script), "--check", "--mesh-exporter", mesh_exporter]
            + resource_args,
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        return PipelineResult(False, "fail", None, message=f"Não foi possível checar dependências: {exc}")
    try:
        readiness = json.loads(check.stdout)
    except json.JSONDecodeError:
        return PipelineResult(False, "fail", None,
                              message=f"Pré-checagem falhou: {check.stderr.strip() or check.stdout.strip()}")
    if not readiness.get("ok"):
        return PipelineResult(False, "fail", None,
                              message="Dependências pendentes: " + "; ".join(readiness.get("missing", [])))
    output = _unique_output_dir(source, create=False)
    command = [sys.executable, str(script), "--input", str(source),
               "--name", catalog_name.strip(), "--description", description,
               "--price", str(price), "--output", str(output),
               "--mesh-exporter", mesh_exporter,
               "--rotate-x", str(rotate_x), "--rotate-y", str(rotate_y),
               "--rotate-z", str(rotate_z)] + resource_args
    emit(f"Gerando .package: {output}")
    try:
        completed = subprocess.run(command, cwd=root, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        return PipelineResult(False, "fail", None, message=f"Não foi possível iniciar o construtor: {exc}")
    for line in (completed.stdout + completed.stderr).splitlines():
        emit(line)
    report = output / "build_report.json"
    package = output / "CCStudio.package"
    status = "missing_report"
    detail = ""
    if report.is_file():
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
            status = str(data.get("status", "unknown"))
            detail = str(data.get("error", ""))
        except (OSError, json.JSONDecodeError) as exc:
            detail = f"Relatório inválido: {exc}"
    ok = completed.returncode == 0 and status == "PROGRAMMATIC_PASS" and package.is_file()
    return PipelineResult(
        ok=ok, status=status, output_dir=output if output.is_dir() else None,
        blend=output / "stages/engine/sims_ready.blend" if ok else None,
        basecolor=output / "stages/engine/basecolor.png" if ok else None,
        report=report if report.is_file() else None,
        message=".package gerado (validação offline)." if ok else
                (detail or f"Construtor falhou (exit={completed.returncode}, status={status})."),
        exit_code=completed.returncode, package=package if ok else None,
    )


def run_pipeline(
    input_glb: Path,
    rotate_x: float = 0.0,
    rotate_y: float = 0.0,
    rotate_z: float = 0.0,
    name: str | None = None,
    log: LogFn | None = None,
) -> PipelineResult:
    """Invoke Blender headless with the existing ccstudio.py — same contract as ccstudio.ps1."""

    def emit(msg: str) -> None:
        if log:
            log(msg)

    input_glb = Path(input_glb).resolve()
    if not input_glb.is_file():
        return PipelineResult(ok=False, status="fail", output_dir=None, message=f"GLB não encontrado: {input_glb}")

    env = check_environment()
    for m in env.messages:
        emit(m)
    if not env.ok:
        return PipelineResult(
            ok=False,
            status="fail",
            output_dir=None,
            message="Ambiente incompleto (Blender / template / ccstudio.py).",
            lines=list(env.messages),
        )

    assert env.blender and env.template and env.script

    emit(f"Input: {input_glb}")
    try:
        out_dir = _unique_output_dir(input_glb, name)
    except Exception as exc:  # noqa: BLE001 — surface to UI
        return PipelineResult(ok=False, status="fail", output_dir=None, message=str(exc))

    emit(f"Output: {out_dir}")
    emit("Processando...")

    log_path = out_dir / "run.log"
    header = [
        "CC Studio desktop run",
        f"started: {datetime.now().isoformat()}",
        f"blender: {env.blender}",
        f"script:  {env.script}",
        f"input:   {input_glb}",
        f"template:{env.template}",
        f"output:  {out_dir}",
        f"rotate:  x={rotate_x} y={rotate_y} z={rotate_z}",
        "",
    ]
    log_path.write_text("\n".join(header) + "\n", encoding="utf-8")

    cmd = [
        str(env.blender),
        "--background",
        "--python",
        str(env.script),
        "--",
        "--input",
        str(input_glb),
        "--template",
        str(env.template),
        "--output",
        str(out_dir),
        "--rotate-x",
        str(rotate_x),
        "--rotate-y",
        str(rotate_y),
        "--rotate-z",
        str(rotate_z),
    ]

    lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        with log_path.open("a", encoding="utf-8") as lf:
            for line in proc.stdout:
                lf.write(line)
                text = line.rstrip("\n")
                lines.append(text)
                # Keep UI short: only forward a few useful markers.
                low = text.lower()
                if any(k in low for k in ("error", "traceback", "fail", "success", "wrote", "saved")):
                    emit(text[:240])
        exit_code = proc.wait()
    except OSError as exc:
        msg = f"Falha ao iniciar Blender: {exc}"
        emit(msg)
        return PipelineResult(ok=False, status="fail", output_dir=out_dir, log=log_path, message=msg, lines=lines)

    with log_path.open("a", encoding="utf-8") as lf:
        lf.write(f"\nexit_code: {exit_code}\n")
        lf.write(f"finished: {datetime.now().isoformat()}\n")

    blend = out_dir / "sims_ready.blend"
    basecolor = out_dir / "basecolor.png"
    report = out_dir / "report.json"

    status = "unknown"
    if report.is_file():
        try:
            status = str(json.loads(report.read_text(encoding="utf-8")).get("status", "unknown"))
        except json.JSONDecodeError:
            status = "bad_report"

    ok = (
        exit_code == 0
        and status == "success"
        and blend.is_file()
        and basecolor.is_file()
        and report.is_file()
    )

    if ok:
        emit("PASS")
        emit(f"sims_ready.blend  {blend}")
        emit(f"basecolor.png     {basecolor}")
        emit(f"report.json       {report}")
        emit(f"run.log           {log_path}")
        return PipelineResult(
            ok=True,
            status="success",
            output_dir=out_dir,
            blend=blend,
            basecolor=basecolor,
            report=report,
            log=log_path,
            message="Pipeline finished.",
            exit_code=exit_code,
            lines=lines,
        )

    msg = f"Pipeline falhou (exit={exit_code} status={status})."
    emit(f"FAIL {msg}")
    emit(f"Ver log: {log_path}")
    return PipelineResult(
        ok=False,
        status=status if status != "unknown" else "fail",
        output_dir=out_dir,
        blend=blend if blend.is_file() else None,
        basecolor=basecolor if basecolor.is_file() else None,
        report=report if report.is_file() else None,
        log=log_path,
        message=msg,
        exit_code=exit_code,
        lines=lines,
    )
