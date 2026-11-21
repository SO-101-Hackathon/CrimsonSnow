"""Find what SenseCraft Robotics (Seeed's desktop app) stores on this computer: its trained models
and the arm calibration its recordings were made with.

Why it matters: a policy trained on SenseCraft recordings learned joint angles measured with
SenseCraft's calibration file. Driving the arm with a different calibration (e.g. the team's
`crimson_follower`) shifts every joint target, by tens of degrees on some joints. So `so demo
--sensecraft` drives the follower with SenseCraft's own calibration file, read in place.

Nothing here writes to SenseCraft's folders.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APP = "SenseCraft Robotics"


def data_root() -> Path | None:
    """SenseCraft's storage folder, or None when SenseCraft is not installed (or not on Windows)."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        pointer = Path(local) / APP / "data-location.json"
        try:
            root = Path(json.loads(pointer.read_text(encoding="utf-8"))["data_root"])
            if root.is_dir():
                return root
        except (OSError, KeyError, ValueError):
            pass
    roaming = os.environ.get("APPDATA")
    if roaming:
        root = Path(roaming) / APP / "backend-storage"
        if root.is_dir():
            return root
    return None


@dataclass
class Calibration:
    folder: Path  # pass as --robot.calibration_dir
    robot_id: str  # pass as --robot.id: LeRobot reads <folder>/<robot_id>.json


def follower_calibration(root: Path | None = None) -> Calibration | None:
    """SenseCraft's follower calibration (it names the follower `so100_follower`)."""
    root = root or data_root()
    if root is None:
        return None
    folder = root / "calibration" / "lerobot" / "robots" / "so_follower"
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if len(files) != 1:
        return None  # none, or several and we cannot tell which one the recordings used
    return Calibration(folder=folder, robot_id=files[0].stem)


@dataclass
class Model:
    name: str
    steps: int | None
    path: Path  # the pretrained_model folder: pass as --policy.path
    updated: str
    dataset_id: str
    task: str = ""  # the task text of the recordings it was trained on


def models(root: Path | None = None) -> list[Model]:
    """Trained models SenseCraft has on this computer, newest first."""
    root = root or data_root()
    if root is None:
        return []
    found: list[Model] = []
    for state_file in root.glob("projects/*/models/*/state.json"):
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        load_path = Path(str(state.get("load_path") or ""))
        if state.get("status") != "ready" or not (load_path / "config.json").is_file():
            continue
        found.append(Model(
            name=str(state.get("display_name") or state.get("name") or state_file.parent.name),
            steps=state.get("steps"),
            path=load_path,
            updated=str(state.get("updated_at") or state.get("created_at") or ""),
            dataset_id=str(state.get("source_dataset_id") or state.get("dataset_id") or ""),
            task=str(state.get("task_text") or ""),
        ))
    return sorted(found, key=lambda m: m.updated, reverse=True)


def pick_model(name: str | None, root: Path | None = None) -> Model:
    """The newest model, or the newest one whose name contains `name` (case-insensitive)."""
    all_models = models(root)
    if not all_models:
        raise SystemExit("[so] No trained SenseCraft model found on this computer "
                         "(train one in SenseCraft and let it download, or pass --policy).")
    if name:
        matches = [m for m in all_models if name.lower() in m.name.lower()]
        if not matches:
            listing = "\n".join(f"   {m.name}  ({m.steps} steps, {m.updated[:16]})" for m in all_models)
            raise SystemExit(f"[so] No SenseCraft model named like '{name}'. Models on this computer:\n{listing}")
        return matches[0]
    return all_models[0]


def is_running() -> bool:
    """SenseCraft keeps the arms' serial ports and the cameras open while it runs."""
    if sys.platform != "win32":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq sensecraft-robotics.exe", "/NH"],
                             capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "sensecraft-robotics.exe" in out.lower()
