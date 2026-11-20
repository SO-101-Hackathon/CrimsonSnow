"""Config (hackathon.toml), machine state (.so101-state.json) and name resolution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "hackathon.toml"
STATE_PATH = ROOT / ".so101-state.json"
JOURNAL_DIR = ROOT / "journal"
OUTPUTS_DIR = ROOT / "outputs"

# lerobot-record appends _YYYYMMDD_HHMMSS to the dataset name.
STAMP_RE = re.compile(r"_(\d{8})_(\d{6})$")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Missing {CONFIG_PATH}")
    with open(CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)
    for section in ("robot", "teleop", "task", "cameras"):
        if section not in cfg:
            raise SystemExit(f"hackathon.toml: missing [{section}] section")
    names = list(cfg["cameras"])
    if any(not re.fullmatch(r"[a-z][a-z0-9_]*", n) for n in names):
        raise SystemExit(f"hackathon.toml: camera names must be lowercase identifiers, got {names}")
    if cfg["robot"]["id"] == cfg["teleop"]["id"]:
        raise SystemExit("hackathon.toml: robot.id and teleop.id must differ (leader != follower)")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", cfg["task"]["slug"]):
        raise SystemExit("hackathon.toml: task.slug may only contain letters, digits, _ . -")
    for key in ("record", "train", "rollout", "hf"):
        cfg.setdefault(key, {})
    return cfg


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"warning: {STATE_PATH.name} is corrupt, starting fresh")
    return {}


def save_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_PATH)


def lerobot_home() -> Path:
    """Where LeRobot stores datasets and calibration (same rule as lerobot.utils.constants)."""
    if os.environ.get("HF_LEROBOT_HOME"):
        return Path(os.environ["HF_LEROBOT_HOME"]).expanduser()
    hf_home = os.environ.get("HF_HOME") or (Path.home() / ".cache" / "huggingface")
    return Path(hf_home).expanduser() / "lerobot"


def hf_user(cfg: dict, state: dict) -> str | None:
    """Configured user, else the logged-in account (cached), else None."""
    if cfg["hf"].get("user"):
        return cfg["hf"]["user"]
    try:
        from huggingface_hub import get_token, whoami

        token = get_token()
        if not token:
            return None
        cached = state.get("hf_user_cache") or {}
        # A hash, never characters of the token itself: this ends up in a file on disk.
        fingerprint = hashlib.sha256(token.encode()).hexdigest()[:12]
        if cached.get("fp") == fingerprint and cached.get("name"):
            return cached["name"]
        name = whoami(token=token)["name"]
        state["hf_user_cache"] = {"fp": fingerprint, "name": name}
        save_state(state)
        return name
    except Exception as exc:  # offline, expired token...
        cached = state.get("hf_user_cache") or {}
        if cached.get("name"):
            return cached["name"]
        print(f"note: could not resolve Hugging Face user ({type(exc).__name__}); working locally")
        return None


def namespace(cfg: dict, state: dict) -> tuple[str, bool]:
    """(namespace, logged_in). Without login we use 'local' and never push."""
    user = hf_user(cfg, state)
    return (user, True) if user else ("local", False)


def cameras_arg(cfg: dict) -> str:
    """The --robot.cameras value, in the same shape as the official docs."""
    parts = []
    for name, cam in cfg["cameras"].items():
        fields = {"type": cam.get("type", "opencv")}
        fields.update({k: v for k, v in cam.items() if k != "type"})
        inner = ", ".join(f"{k}: {_yaml_scalar(v)}" for k, v in fields.items())
        parts.append(f"{name}: {{{inner}}}")
    return "{ " + ", ".join(parts) + " }"


def _yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # Plain words and paths (COM5, /dev/video2, C:\x) stay unquoted: embedded double quotes get
    # mangled when a command is pasted into Windows PowerShell 5.1.
    if re.fullmatch(r"[A-Za-z_/~][A-Za-z0-9_./\\:-]*", s):
        return s
    return json.dumps(s)


def local_datasets(ns: str, base: str | None = None) -> list[Path]:
    """Local dataset folders of a namespace, oldest first. `base` filters by name prefix."""
    root = lerobot_home() / ns
    if not root.is_dir():
        return []
    out = []
    for d in root.iterdir():
        if not (d / "meta" / "info.json").is_file():
            continue
        if base and not (d.name == base or (d.name.startswith(base + "_") and STAMP_RE.search(d.name))):
            continue
        out.append(d)
    return sorted(out, key=lambda p: (STAMP_RE.search(p.name).group(0) if STAMP_RE.search(p.name) else "", p.name))


def _namespaces(first: str) -> list[str]:
    """Local namespace folders to search: the current one, then 'local', then any other.

    A dataset stays in the folder of the account that was active when it was recorded
    ('local' = not logged in). Logging in or out half-way must not make earlier ones vanish.
    """
    home = lerobot_home()
    others = sorted(p.name for p in home.iterdir() if p.is_dir()) if home.is_dir() else []
    return list(dict.fromkeys([first, "local", *others]))


def resolve_dataset(cfg: dict, state: dict, explicit: str | None, *, base: str | None = None) -> tuple[str, Path]:
    """Return (repo_id, local_dir) for the dataset to use.

    explicit may be 'name', 'user/name' or omitted (= newest recording of the current task).
    A bare name that is not on this laptop is taken as a Hub dataset of the current account.
    """
    ns, _ = namespace(cfg, state)
    base = base or cfg["task"]["slug"]
    home = lerobot_home()
    if explicit:
        if "/" in explicit:
            repo_id = explicit
        else:
            holder = next((n for n in _namespaces(ns) if (home / n / explicit / "meta" / "info.json").is_file()), ns)
            repo_id = f"{holder}/{explicit}"
        return repo_id, home / repo_id
    for holder in _namespaces(ns):
        found = local_datasets(holder, base)
        if found:
            return f"{holder}/{found[-1].name}", found[-1]
    raise SystemExit(
        f"No local dataset named {ns}/{base}_<date>_<time> yet.\n"
        f"Record one with `so record`, or pass --dataset user/name (a Hub dataset is downloaded)."
    )


def dataset_info(path: Path) -> dict:
    try:
        return json.loads((path / "meta" / "info.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
