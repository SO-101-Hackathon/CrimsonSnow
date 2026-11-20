"""Back up / restore the arms' calibration files.

LeRobot keeps calibration in its cache (~/.cache/huggingface/lerobot/calibration), keyed by
the arm `id`. A copy inside the repo protects against a wiped cache, lets a teammate's
laptop drive the same arms without recalibrating, and makes the repo reproducible.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .config import ROOT, lerobot_home

REPO_CALIB = ROOT / "calibration"


def _cache_dir() -> Path:
    if os.environ.get("HF_LEROBOT_CALIBRATION"):
        return Path(os.environ["HF_LEROBOT_CALIBRATION"]).expanduser()
    return lerobot_home() / "calibration"


def _find(base: Path, kind: str, arm_id: str) -> list[Path]:
    """Calibration files for an id, e.g. <base>/robots/so_follower/<id>.json"""
    root = base / kind
    return sorted(root.glob(f"*/{arm_id}.json")) if root.is_dir() else []


def _targets(cfg) -> list[tuple[str, str, str]]:
    return [("follower", "robots", cfg["robot"]["id"]), ("leader", "teleoperators", cfg["teleop"]["id"])]


def status(cfg) -> dict[str, bool]:
    cache = _cache_dir()
    out = {}
    for role, kind, arm_id in _targets(cfg):
        cached = _find(cache, kind, arm_id)
        backed = _find(REPO_CALIB, kind, arm_id)
        out[role] = bool(cached)
        where = str(cached[0]) if cached else "MISSING -> run: so calibrate " + role
        print(f"  {role:<9} id={arm_id:<14} cache: {where}")
        print(f"  {'':<9} {'':<17} repo backup: {'yes' if backed else 'no'}")
    return out


def backup(cfg, quiet: bool = True) -> int:
    cache = _cache_dir()
    n = 0
    for role, kind, arm_id in _targets(cfg):
        for src in _find(cache, kind, arm_id):
            dst = REPO_CALIB / kind / src.parent.name / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
            if not quiet:
                print(f"[so] calibration backup: {dst.relative_to(ROOT)}")
    if n == 0 and not quiet:
        print("[so] no calibration files found to back up yet")
    return n


def restore(cfg, force: bool = False) -> int:
    cache = _cache_dir()
    n = 0
    for role, kind, arm_id in _targets(cfg):
        for src in _find(REPO_CALIB, kind, arm_id):
            dst = cache / kind / src.parent.name / src.name
            if dst.exists() and not force:
                print(f"[so] {role}: calibration already present, keeping it (use --force to overwrite)")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
            print(f"[so] {role}: restored {dst}")
    if n == 0:
        print("[so] nothing restored")
    return n
