"""
CC Studio v0.2.1 Desktop (packaged)

  python app/main.py
  python app/main.py --batch-fixtures
  CCStudio.exe
  CCStudio.exe --batch-fixtures --fixtures-root <repo>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python app/main.py` from repo root (dev).
if not getattr(sys, "frozen", False):
    _ROOT = Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))


def _enable_console_for_batch() -> None:
    """Windowed .exe has no stdout; attach a console when running batch tests."""
    if not getattr(sys, "frozen", False):
        return
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.AllocConsole()
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")  # noqa: SIM115
    except Exception:  # noqa: BLE001
        pass


def run_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("CC Studio")
    app.setOrganizationName("CC Studio")
    win = MainWindow()
    win.show()
    return app.exec()


def run_batch_fixtures(fixtures_root: Path | None = None) -> int:
    """Exercise the same PipelineRunner the GUI uses on the four validated fixtures."""
    from app.services.pipeline_runner import run_pipeline

    root = (fixtures_root or Path.cwd()).resolve()
    cases = [
        ("exe_vaso", root / "fixtures/v0.1-vase/teste.glb", 0.0, 0.0, 0.0),
        (
            "exe_caneca",
            root / "fixtures/future/A_handle_or_hollow/tmpfme2zl9i.glb",
            0.0,
            0.0,
            0.0,
        ),
        (
            "exe_assimetrico",
            root / "fixtures/future/B_asymmetric/model-1789699908959.glb",
            0.0,
            0.0,
            0.0,
        ),
        (
            "exe_bowl",
            root / "fixtures/future/C_short_wide/model-1789699931683.glb",
            90.0,
            0.0,
            0.0,
        ),
    ]

    failed = 0
    print("CC Studio — batch fixtures via pipeline_runner (same path as GUI)")
    print(f"fixtures-root: {root}")
    for name, glb, rx, ry, rz in cases:
        print(f"\n=== {name} rotate=({rx},{ry},{rz}) ===")
        if not glb.is_file():
            print(f"FAIL missing input: {glb}")
            failed += 1
            continue
        result = run_pipeline(
            glb,
            rotate_x=rx,
            rotate_y=ry,
            rotate_z=rz,
            name=name,
            log=print,
        )
        if result.ok:
            print(f"PASS {result.output_dir}")
        else:
            print(f"FAIL {result.message}")
            failed += 1

    print("\n---")
    if failed:
        print(f"RESULT: {failed} FAIL")
        return 1
    print("RESULT: 4/4 PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CC Studio Desktop")
    parser.add_argument(
        "--batch-fixtures",
        action="store_true",
        help="Run the four validated fixtures through pipeline_runner (no window).",
    )
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=None,
        help="Repo root containing fixtures/ (for packaged --batch-fixtures).",
    )
    args, _unknown = parser.parse_known_args()
    if args.batch_fixtures:
        _enable_console_for_batch()
        return run_batch_fixtures(args.fixtures_root)
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
