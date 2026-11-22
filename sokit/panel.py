"""Control panel for the demo: a local web page with big buttons, the live score and the last check photo.

    so panel                     opens http://127.0.0.1:8765 in the browser
    so panel --mock              no robot needed: a simulated session, to rehearse the presentation
    python -m sokit.panel        the same without the `so` launcher

The page runs the same commands as the terminal (`so demo`, `so try`, `so teleop`, `so cameras`,
`so doctor`), one at a time, and answers their keyboard prompts for you: Start attempt = Enter,
Stop arm = Enter during a run, Finish = q, and in `so try` Success / Fail / Skip = s / f / x.
So whatever the panel starts is journalled in journal/ exactly as when it is typed.

Safety: the arm moves for real, so someone stays at the robot. Stop arm and Finish let the arm
return to its start pose; Abort interrupts the process (Ctrl+Break on Windows, SIGINT elsewhere)
and kills it 5 s later if it is still running.

Access: this computer only (127.0.0.1) unless started with --host 0.0.0.0 (e.g. a phone as remote
control on the local network). Every API call needs a token that is made new at each start; the
page carries it, and with --host 0.0.0.0 it is part of the printed link. Standard library only.
"""

from __future__ import annotations

import argparse
import codecs
import csv
import hmac
import ipaddress
import json
import math
import os
import queue
import re
import secrets
import shutil
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from collections import OrderedDict, deque
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import config as C
from . import runner as R
from . import sensecraft as SC
from .demo import GRIP_WORDS, LOCATIONS, Check, camera_role, decide

ROOT = C.ROOT
HTML_FILE = Path(__file__).with_name("panel.html")
DEMO_DIR = C.OUTPUTS_DIR / "demo"          # photos `so demo` checked (read only)
MOCK_DIR = C.OUTPUTS_DIR / "panel-mock"    # photos of simulated sessions (mock mode only)
DEMO_CSV = C.JOURNAL_DIR / "demo.csv"
EVAL_CSV = C.JOURNAL_DIR / "eval.csv"
ENV_FILE = ROOT / ".env"

DEFAULT_PORT = 8765
COMMANDS = ("demo", "try", "teleop", "cameras", "doctor")
CHECKS = ("auto", "local", "openai", "claude", "grip")
SOURCES = ("sensecraft", "policy", "last")
EXPECTS = ("attempt", "running", "result", "any")
SENSECRAFT_BUSY = "SenseCraft holds the arm and cameras: close it before a robot command."
SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD")
SESSION_RE = re.compile(r"^\d{8}_\d{6}$")
FRAME_RE = re.compile(r"^attempt(\d+)_run(\d+)_([A-Za-z0-9_-]+)\.(?:jpe?g|png)$", re.IGNORECASE)
PHOTO_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
MAX_BODY = 8192
MAX_LINE = 2000
LOG_LINES = 3000


class PanelError(Exception):
    """A request the panel refuses, with the HTTP status to answer."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ----------------------------------------------------------------------------- commands (pure)
@dataclass
class Command:
    argv: list[str]       # what is executed
    shown: str            # what the page and the log show (`so ...`)
    cmd: str
    dry_run: bool
    mocked: bool          # the simulated program runs instead of the real one
    attempts: int = 0
    tries: int = 0

    @property
    def hardware(self) -> bool:
        """True when it opens the arms' ports or the cameras."""
        return not (self.dry_run or self.mocked)

    @property
    def prompts(self) -> bool:
        """True for the programs that are driven through keyboard prompts (`so demo`, `so try`)."""
        return self.cmd in ("demo", "try") and not self.dry_run


def _whole(req: dict, key: str, default: int, lo: int, hi: int) -> int:
    value = req.get(key, default)
    if value is None or value == "":
        value = default
    if isinstance(value, bool):
        raise PanelError(400, f"{key}: expected a whole number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise PanelError(400, f"{key}: expected a whole number") from None
    if not math.isfinite(number) or not number.is_integer() or not lo <= number <= hi:
        raise PanelError(400, f"{key} must be a whole number from {lo} to {hi}")
    return int(number)


def _number(req: dict, key: str, default: float, lo: float, hi: float) -> float:
    value = req.get(key, default)
    if value is None or value == "":
        value = default
    if isinstance(value, bool):
        raise PanelError(400, f"{key}: expected a number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise PanelError(400, f"{key}: expected a number") from None
    if not math.isfinite(number) or not lo <= number <= hi:
        raise PanelError(400, f"{key} must be between {lo:g} and {hi:g}")
    return number


def _text(value, what: str, max_len: int = 300) -> str:
    """One argument for a `so` option: no control characters, and no leading '-' (it would turn
    into an option of its own: `so` passes unknown --flags on to LeRobot)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PanelError(400, f"{what}: expected text")
    text = value.strip()
    if len(text) > max_len:
        raise PanelError(400, f"{what}: at most {max_len} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise PanelError(400, f"{what}: control characters are not allowed")
    if text.startswith("-"):
        raise PanelError(400, f"{what} may not start with '-'")
    return text


def _shown(flag: str) -> str:
    return f'"{flag}"' if " " in flag else flag


def build_command(req: dict, *, mock: bool = False, mock_speed: float = 1.0, mock_photos: bool = True,
                  python: str | None = None) -> Command:
    """The `so` command (or, in mock mode, the simulated program) for a request from the page."""
    python = python or sys.executable
    cmd = req.get("cmd")
    if cmd not in COMMANDS:
        raise PanelError(400, f"unknown command (one of: {', '.join(COMMANDS)})")
    dry = bool(req.get("dry_run"))
    if dry and cmd == "doctor":
        raise PanelError(400, "`so doctor` has no dry run: it opens the arms and the cameras. Turn dry run "
                              "off (and close SenseCraft) to run it.")
    flags: list[str] = []
    attempts = tries = 0
    check = "auto"
    label = cmd
    if cmd in ("demo", "try"):
        source = req.get("source") or "sensecraft"
        if source not in SOURCES:
            raise PanelError(400, f"source must be one of: {', '.join(SOURCES)}")
        if source == "sensecraft":
            name = _text(req.get("sensecraft"), "SenseCraft model name", 200)
            flags.append(f"--sensecraft={name}")  # empty = the newest model
            label = f"sensecraft:{name or 'newest'}"
        elif source == "policy":
            path = _text(req.get("policy"), "policy", 500)
            if not path:
                raise PanelError(400, "policy: give a folder or a Hugging Face model id")
            flags.append(f"--policy={path}")
            label = path
        else:
            label = "last trained run"
        if cmd == "demo":
            tries = _whole(req, "tries", 3, 1, 9)
            attempts = _whole(req, "attempts", 5, 0, 99)
            check = req.get("check") or "auto"
            if check not in CHECKS:
                raise PanelError(400, f"check must be one of: {', '.join(CHECKS)}")
            flags += [f"--tries={tries}", f"--attempts={attempts}"]
            if check != "auto":  # auto: the RETRY_CHECK choice in .env applies
                flags.append(f"--check={check}")
        seconds = _number(req, "seconds", 40, 5, 600)
        flags.append(f"--seconds={seconds:g}")
        if req.get("record_video") is True:
            flags.append("--record-video")  # the whole test on video: outputs/demo/<session>/test.mp4
    elif cmd == "teleop" and req.get("no_cameras"):
        flags.append("--no-cameras")
    shown = " ".join(["so", *(["--dry-run"] if dry else []), cmd, *(_shown(f) for f in flags)])
    if mock and not dry:
        argv = [python, "-u", "-m", "sokit.panel", "--mock-child", cmd, f"--speed={mock_speed:g}",
                f"--attempts={attempts}", f"--tries={tries}", f"--check={check}", f"--label=mock {label}"]
        if not mock_photos:
            argv.append("--no-photos")
        return Command(argv, shown, cmd, dry, True, attempts, tries)
    argv = [python, "-u", "-m", "sokit", *(["--dry-run"] if dry else []), cmd, *flags]
    return Command(argv, shown, cmd, dry, False, attempts, tries)


# ----------------------------------------------------------------------------- reading the output (pure)
RE_POLICY = re.compile(r"^\[(?:demo|try)\] Policy: (.*)$")
RE_SETUP = re.compile(r"^\[demo\] Up to (\d+) runs? per attempt\. Check: (.*)$")
RE_DEMO_PROMPT = re.compile(r"^\[demo\] Attempt (\d+): put the battery on its place")
RE_RUN = re.compile(r"^\[demo\] {3}run (\d+): ([\d.]+) s \((.*?)\) \| grip: (\S+) \| camera: (.*)$")
RE_VERDICT = re.compile(r"^\[demo\] {3}-> (SUCCESS|not done): (.*)$")
RE_EXPLAIN = re.compile(r"^\[demo\] {6}(\S.*?): (.*)$")
RE_AGAIN = re.compile(r"^\[demo\] {3}running the policy again")
RE_ATTEMPT_END = re.compile(r"^\[demo\] Attempt (\d+): (SUCCESS|FAILED) in ([\d.]+) s \((\d+) runs?\)")
RE_SUMMARY = re.compile(r"^\[demo\] (\d+)/(\d+) attempts succeeded, (\d+) of them thanks to a retry")
RE_STOPPING = re.compile(r"^\[demo\] stopping")
RE_TRY_PROMPT = re.compile(r"^\[try\] Attempt (\d+): set up the scene, then press Enter")
RE_TRY_RUN = re.compile(r"^\[try\] {3}([\d.]+) s \((.*?)\), gripper: (.*?)\. The arm is back")
RE_TRY_RESULT = re.compile(r"^\[try\] {3}Result\? ")
RE_TRY_SUMMARY = re.compile(r"^\[try\] (\d+)/(\d+) successes this session")


@dataclass
class RunInfo:
    n: int
    seconds: float | None = None
    ended_by: str = ""
    grip: str = ""
    camera: str = ""
    success: bool | None = None
    reason: str = ""
    model: str = ""
    explanation: str = ""


@dataclass
class AttemptInfo:
    n: int
    runs: list[RunInfo] = field(default_factory=list)
    success: bool | None = None   # None while running (or skipped in `so try`)
    seconds: float | None = None
    rescued: bool = False         # succeeded thanks to a retry
    result: str = ""              # `so try`: s, f or x
    note: str = ""


class SessionParser:
    """Turns the output of `so demo` / `so try` (and the lines the panel sent) into what the page shows.

    phase: starting | attempt (waits for Enter) | running | checked | between | result (waits for
    s/f/x) | logged | stopping | done | exited.  prompt: what the program waits for right now
    (attempt, running, result or None); the page enables the matching buttons only.
    """

    def __init__(self, mode: str, attempts_total: int = 0, tries: int = 0):
        self.mode = mode
        self.attempts_total = attempts_total
        self.tries = tries
        self.policy = ""
        self.check = ""
        self.phase = "starting"
        self.prompt: str | None = None
        self.attempt = 0
        self.run = 0
        self.stop_requested = False
        self.attempts: list[AttemptInfo] = []
        self.last: RunInfo | None = None
        self.summary: dict | None = None
        self.streak = 0
        self.best_streak = 0
        self.exit_code: int | None = None
        self.runs_seen = 0

    # -- helpers -------------------------------------------------------------
    def _attempt(self, n: int) -> AttemptInfo:
        for att in reversed(self.attempts):
            if att.n == n and att.success is None and not att.result:
                return att
        att = AttemptInfo(n)
        self.attempts.append(att)
        return att

    @staticmethod
    def _run_of(att: AttemptInfo, k: int) -> RunInfo:
        for run in att.runs:
            if run.n == k:
                return run
        run = RunInfo(k)
        att.runs.append(run)
        return run

    def _score(self, ok: bool) -> None:
        self.streak = self.streak + 1 if ok else 0
        self.best_streak = max(self.best_streak, self.streak)

    # -- what the program printed ----------------------------------------------
    def feed(self, raw: str) -> None:
        line = raw.rstrip()
        if not line.startswith(("[demo]", "[try]")):
            return
        if m := RE_POLICY.match(line):
            self.policy = m[1].strip()
        elif m := RE_SETUP.match(line):
            self.tries, self.check = int(m[1]), m[2].strip()
        elif m := RE_DEMO_PROMPT.match(line) or RE_TRY_PROMPT.match(line):
            self.attempt, self.run = int(m[1]), 0
            self.phase, self.prompt, self.stop_requested = "attempt", "attempt", False
        elif m := RE_RUN.match(line):
            att = self._attempt(self.attempt)
            run = self._run_of(att, int(m[1]))
            run.seconds, run.ended_by, run.grip, run.camera = float(m[2]), m[3], m[4], m[5].strip()
            self.run, self.last = run.n, run
            self.phase, self.prompt, self.stop_requested = "checked", None, False
            self.runs_seen += 1
        elif m := RE_VERDICT.match(line):
            if self.last is not None:
                self.last.success, self.last.reason = m[1] == "SUCCESS", m[2].strip()
        elif m := RE_EXPLAIN.match(line):
            if self.last is not None and not self.last.explanation:
                self.last.model, self.last.explanation = m[1].strip(), m[2].strip()
        elif RE_AGAIN.match(line):
            self.run += 1
            self.phase, self.prompt, self.stop_requested = "running", "running", False
        elif m := RE_ATTEMPT_END.match(line):
            att = self._attempt(int(m[1]))
            att.success, att.seconds = m[2] == "SUCCESS", float(m[3])
            att.rescued = att.success and int(m[4]) > 1
            self._score(att.success)
            self.phase, self.prompt = "between", None
        elif m := RE_SUMMARY.match(line):
            self.summary = {"ok": int(m[1]), "total": int(m[2]), "rescued": int(m[3])}
            self.phase, self.prompt = "done", None
        elif RE_STOPPING.match(line):
            self.phase, self.prompt = "stopping", None
        elif m := RE_TRY_RUN.match(line):
            att = self.attempts[-1] if self.attempts and not self.attempts[-1].result else self._attempt(self.attempt)
            run = self._run_of(att, 1)
            run.seconds, run.ended_by, run.grip = float(m[1]), m[2], m[3].strip()
            self.last = run
            self.phase, self.prompt, self.stop_requested = "checked", None, False
            self.runs_seen += 1
        elif RE_TRY_RESULT.match(line):
            self.phase, self.prompt = "result", "result"
        elif m := RE_TRY_SUMMARY.match(line):
            self.summary = {"ok": int(m[1]), "total": int(m[2]), "rescued": 0}
            self.phase, self.prompt = "done", None

    # -- what the panel typed --------------------------------------------------
    def on_input(self, text: str) -> None:
        word = text.strip().lower()
        if self.prompt == "attempt":
            if word in ("q", "quit", "exit"):
                self.phase, self.prompt = "stopping", None
                return
            if self.mode == "try":
                self.attempts.append(AttemptInfo(self.attempt))
            else:
                self._attempt(self.attempt)
            self.run = 1
            self.phase, self.prompt, self.stop_requested = "running", "running", False
        elif self.prompt == "running":
            self.stop_requested = True  # any line stops the run in `so demo` / `so try`
        elif self.prompt == "result":
            key, _, note = text.strip().partition(" ")
            key = key.lower()
            if key not in ("s", "f", "x") or not self.attempts:
                return  # the program asks again
            att = self.attempts[-1]
            att.result, att.note = key, note.strip()
            if key != "x":
                att.success = key == "s"
                self._score(att.success)
            self.phase, self.prompt = "logged", None

    def on_exit(self, code: int) -> None:
        self.exit_code, self.prompt = code, None
        if self.phase != "done":
            self.phase = "exited"

    def snapshot(self) -> dict:
        return {
            "mode": self.mode, "policy": self.policy, "check": self.check, "tries": self.tries,
            "attempts_total": self.attempts_total, "phase": self.phase, "prompt": self.prompt,
            "attempt": self.attempt, "run": self.run, "stop_requested": self.stop_requested,
            "attempts": [asdict(a) for a in self.attempts], "last": asdict(self.last) if self.last else None,
            "summary": self.summary, "streak": self.streak, "best_streak": self.best_streak,
            "exit_code": self.exit_code, "runs_seen": self.runs_seen,
        }


# ----------------------------------------------------------------------------- journal and photos (read only)
def _read_csv(path: Path) -> list[dict]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def summarize_demo_log(path: Path = DEMO_CSV) -> list[dict]:
    """journal/demo.csv per policy: attempts, successes, rescued by a retry, best streak."""
    groups: "OrderedDict[str, dict]" = OrderedDict()
    for row in _read_csv(path):
        policy = (row.get("policy") or "?").strip()
        g = groups.setdefault(policy, {"policy": policy, "attempts": 0, "successes": 0, "rescued": 0,
                                       "runs": 0, "streak": 0, "best_streak": 0, "last": ""})
        ok = (row.get("success") or "").strip() == "1"
        g["attempts"] += 1
        g["successes"] += ok
        g["rescued"] += (row.get("rescued_by_retry") or "").strip() == "1"
        try:
            g["runs"] += int(row.get("runs") or 0)
        except ValueError:
            pass
        g["streak"] = g["streak"] + 1 if ok else 0
        g["best_streak"] = max(g["best_streak"], g["streak"])
        g["last"] = f"{row.get('date', '')} {row.get('time', '')}".strip()
    return sorted(groups.values(), key=lambda g: g["last"], reverse=True)


def summarize_eval_log(path: Path = EVAL_CSV) -> list[dict]:
    """journal/eval.csv (`so try`, `so eval`) per policy: tries, successes, failures."""
    groups: "OrderedDict[str, dict]" = OrderedDict()
    for row in _read_csv(path):
        policy = (row.get("policy") or "?").strip()
        g = groups.setdefault(policy, {"policy": policy, "tries": 0, "successes": 0, "fails": 0, "last": ""})
        ok = (row.get("result") or "").strip() == "success"
        g["tries"] += 1
        g["successes"] += ok
        g["fails"] += not ok
        g["last"] = (row.get("timestamp") or "").strip()
    return sorted(groups.values(), key=lambda g: g["last"], reverse=True)


def _frames(session: Path) -> list[tuple[int, int, str, Path]]:
    out = []
    try:
        entries = list(session.iterdir())
    except OSError:
        return out
    for f in entries:
        m = FRAME_RE.match(f.name)
        if m and f.is_file():
            out.append((int(m[1]), int(m[2]), m[3], f))
    return out


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def latest_check_photo(roots: list[Path], root: Path = ROOT) -> dict | None:
    """The photos of the newest checked run: newest session folder (YYYYMMDD_HHMMSS), then the
    highest attempt/run in it. Scene camera = top/front/..., wrist camera = wrist/gripper."""
    sessions = []
    for base in roots:
        if base.is_dir():
            sessions += [d for d in base.iterdir() if d.is_dir() and SESSION_RE.match(d.name)]
    for session in sorted(sessions, key=lambda d: d.name, reverse=True):
        frames = _frames(session)
        if not frames:
            continue
        attempt, run = max((a, r) for a, r, _, _ in frames)
        found = {"scene": None, "wrist": None}
        mtime = 0.0
        for a, r, cam, f in frames:
            if (a, r) != (attempt, run):
                continue
            role = camera_role(cam) or "scene"
            if found[role] is None:
                found[role] = _rel(f, root)
                try:
                    mtime = max(mtime, f.stat().st_mtime)
                except OSError:
                    pass
        return {"session": session.name, "attempt": attempt, "run": run, "mtime": round(mtime, 3), **found}
    return None


def resolve_photo(rel: str, allowed: list[Path], root: Path = ROOT) -> Path | None:
    """The file behind a photo link, only if it is an image inside one of the allowed folders."""
    if not rel or "\x00" in rel or len(rel) > 400:
        return None
    candidate = Path(rel)
    if candidate.is_absolute() or candidate.drive or candidate.anchor:
        return None
    try:
        full = (root / candidate).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if full.suffix.lower() not in PHOTO_TYPES or not full.is_file():
        return None
    for folder in allowed:
        try:
            full.relative_to(folder.resolve())
            return full
        except (ValueError, OSError):
            continue
    return None


def labelled_frames(demo_dir: Path = DEMO_DIR, demo_csv: Path = DEMO_CSV) -> dict[str, list[tuple[Path, Path | None]]]:
    """(overhead, wrist) photos of real checked runs, grouped by the camera verdict journal/demo.csv
    logged for them: {'in_box': [...], 'on_mat': [...], ...}. The simulated session shows them."""
    if not demo_dir.is_dir():
        return {}
    sessions = sorted(d for d in demo_dir.iterdir() if d.is_dir() and SESSION_RE.match(d.name))
    out: dict[str, list[tuple[Path, Path | None]]] = {}
    for row in _read_csv(demo_csv):
        stamp = (row.get("date") or "").replace("-", "") + "_" + (row.get("time") or "").replace(":", "")
        started = [s for s in sessions if s.name <= stamp] if SESSION_RE.match(stamp) else []
        if not started:
            continue
        try:
            attempt = int(row.get("attempt") or 0)
        except ValueError:
            continue
        frames = _frames(started[-1])
        for part in (row.get("details") or "").split("; "):
            m = re.match(r"run (\d+):.*?\bcamera ([a-z_]+)", part)
            if not m or m[2] not in LOCATIONS:
                continue
            here = [(cam, f) for a, r, cam, f in frames if (a, r) == (attempt, int(m[1]))]
            scene = next((f for cam, f in here if camera_role(cam) != "wrist"), None)
            wrist = next((f for cam, f in here if camera_role(cam) == "wrist"), None)
            if scene is not None:
                out.setdefault(m[2], []).append((scene, wrist))
    return out


# ----------------------------------------------------------------------------- settings (read only, no secrets)
def env_setting(name: str, env_file: Path = ENV_FILE) -> str | None:
    """A non-secret setting from the environment or the repository's .env (the environment wins,
    as in sokit.demo.load_env_file). Refuses names that look like keys or tokens."""
    if any(word in name.upper() for word in SECRET_WORDS):
        raise ValueError(f"{name} looks like a secret: the panel does not read it")
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    try:
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        if key.strip() == name:
            value = value.split(" #", 1)[0].strip().strip('"').strip("'").strip()
            return value or None
    return None


def keys_present(env_file: Path = ENV_FILE) -> dict[str, bool]:
    """Whether an OpenAI / Anthropic key is configured. Only yes/no ever leaves this function."""
    names = {"openai": ("OPENAI_API_KEY", "gpt_api_key"), "claude": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    found = {k: any((os.environ.get(n) or "").strip() for n in ns) for k, ns in names.items()}
    try:
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        for provider, ns in names.items():
            if key.strip() in ns and value.strip().strip('"').strip("'"):
                found[provider] = True
    return found


# ----------------------------------------------------------------------------- access rules (pure)
LOOPBACK_NAMES = ("localhost", "127.0.0.1", "::1")


def _split_host(host: str) -> tuple[str, str] | None:
    host = host.strip().lower()
    if host.startswith("["):
        end = host.find("]")
        if end < 0:
            return None
        name, rest = host[1:end], host[end + 1:]
        if rest and not rest.startswith(":"):
            return None
        return name, rest[1:]
    name, _, port = host.partition(":")
    return name, port


def host_allowed(host_header: str | None, port: int, lan: bool, extra_names: tuple[str, ...] = ()) -> bool:
    """Host header check against DNS rebinding: loopback names always; on the local network
    (--host 0.0.0.0) also IP addresses and this computer's own name."""
    if not host_header:
        return False
    parts = _split_host(host_header)
    if parts is None:
        return False
    name, given_port = parts
    if given_port != str(port) and not (given_port == "" and port == 80):
        return False
    if name in LOOPBACK_NAMES:
        return True
    if not lan:
        return False
    if name in extra_names:
        return True
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


def origin_allowed(origin: str | None, port: int, lan: bool, extra_names: tuple[str, ...] = ()) -> bool:
    if origin is None:
        return True  # not a browser, or a same-origin GET
    parts = urlsplit(origin)
    if parts.scheme != "http" or not parts.netloc:
        return False
    return host_allowed(parts.netloc, port, lan, extra_names)


# ----------------------------------------------------------------------------- the running program
class LogBuffer:
    """The last output lines, numbered so the page can ask only for the new ones."""

    def __init__(self, maxlen: int = LOG_LINES):
        self.lines: deque[tuple[int, str]] = deque(maxlen=maxlen)
        self.seq = 0
        self.lock = threading.Lock()

    def add(self, text: str) -> None:
        with self.lock:
            self.seq += 1
            self.lines.append((self.seq, text[:MAX_LINE]))

    def since(self, n: int) -> tuple[int, list[list], bool]:
        with self.lock:
            first = self.lines[0][0] if self.lines else self.seq + 1
            truncated = n < first - 1
            return self.seq, [[s, t] for s, t in self.lines if s > n], truncated


class Child:
    """One program started by the panel, with its output read line by line."""

    def __init__(self, command: Command, on_line, on_exit, cwd: Path = ROOT):
        self.command = command
        self.on_line, self.on_exit = on_line, on_exit
        self.cwd = cwd
        self.proc: subprocess.Popen | None = None
        self.started = 0.0
        self.exit_code: int | None = None
        self._stdin_lock = threading.Lock()

    def start(self) -> None:
        env = R.child_env({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
        kwargs: dict = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            cwd=str(self.cwd), env=env)
        if R.IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # so Ctrl+Break reaches only it
        else:
            kwargs["start_new_session"] = True  # its own process group, for SIGINT / kill
        self.proc = subprocess.Popen(self.command.argv, **kwargs)
        self.started = time.time()
        threading.Thread(target=self._pump, name="panel-output", daemon=True).start()

    def _pump(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        out = self.proc.stdout
        buf = ""
        while True:
            try:
                chunk = out.read1(65536)
            except (OSError, ValueError):
                chunk = b""
            if not chunk:
                break
            buf += decoder.decode(chunk)
            parts = re.split(r"\r\n|\n|\r(?=.)", buf, flags=re.S)
            buf = parts.pop()
            for part in parts:
                self.on_line(part)
        buf += decoder.decode(b"", final=True)
        if buf.strip("\r"):
            self.on_line(buf.strip("\r"))
        self.exit_code = self.proc.wait()
        with self._stdin_lock:
            for pipe in (self.proc.stdin, self.proc.stdout):
                try:
                    pipe.close()
                except (OSError, ValueError, AttributeError):
                    pass
        self.on_exit(self.exit_code)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def write(self, text: str) -> None:
        if not self.alive():
            raise PanelError(409, "nothing is running")
        assert self.proc is not None and self.proc.stdin is not None
        with self._stdin_lock:
            try:
                self.proc.stdin.write((text + "\n").encode("utf-8"))
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as e:
                raise PanelError(409, "the program no longer reads input") from e

    def interrupt(self) -> None:
        """Ctrl+Break (Windows) / SIGINT (macOS, Linux) to the program and everything it started."""
        if not self.alive():
            return
        assert self.proc is not None
        try:
            if R.IS_WINDOWS:
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(self.proc.pid, signal.SIGINT)
        except (OSError, ValueError):
            pass

    def kill_tree(self) -> None:
        if not self.alive():
            return
        assert self.proc is not None
        if R.IS_WINDOWS:
            try:
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                               capture_output=True, timeout=15)
            except (OSError, subprocess.SubprocessError):
                pass
        else:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            self.proc.kill()
        except OSError:
            pass


# ----------------------------------------------------------------------------- camera preview (optional)
def _import_cv2():
    import cv2  # noqa: PLC0415 - optional; only the preview needs it

    return cv2


def _cv2_installed() -> bool:
    import importlib.util  # noqa: PLC0415

    return importlib.util.find_spec("cv2") is not None


class _Feed:
    """One camera, read in a thread; viewers get the newest JPEG."""

    def __init__(self, name: str, cam: dict, cv2):
        self.name, self.cam, self.cv2 = name, cam, cv2
        self.viewers = 0
        self.stop = threading.Event()
        self.cond = threading.Condition()
        self.jpeg: bytes | None = None
        self.seq = 0
        self.failed: str | None = None
        self.thread = threading.Thread(target=self._loop, name=f"panel-camera-{name}", daemon=True)

    def _open(self):
        cv2 = self.cv2
        source = self.cam.get("index_or_path", 0)
        if R.IS_WINDOWS and isinstance(source, int):
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)  # MSMF fails to open these cameras
        else:
            cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"camera {source} did not open (in use, or a wrong number in hackathon.local.toml)")
        fourcc = self.cam.get("fourcc")
        if isinstance(fourcc, str) and len(fourcc) == 4:  # only when configured: not every camera has MJPG
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        for prop, key in ((cv2.CAP_PROP_FRAME_WIDTH, "width"), (cv2.CAP_PROP_FRAME_HEIGHT, "height"),
                          (cv2.CAP_PROP_FPS, "fps")):
            if self.cam.get(key):
                cap.set(prop, float(self.cam[key]))
        return cap

    def _loop(self) -> None:
        cap = None
        try:
            cap = self._open()
            misses = 0
            while not self.stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    misses += 1
                    if misses > 40:
                        raise RuntimeError("the camera stopped sending pictures")
                    self.stop.wait(0.05)
                    continue
                misses = 0
                ok, buf = self.cv2.imencode(".jpg", frame, [int(self.cv2.IMWRITE_JPEG_QUALITY), 75])
                if ok:
                    with self.cond:
                        self.jpeg, self.seq = bytes(buf), self.seq + 1
                        self.cond.notify_all()
                self.stop.wait(1 / 15)
        except Exception as e:  # noqa: BLE001 - shown on the page
            self.failed = str(e)
        finally:
            if cap is not None:
                cap.release()
            with self.cond:
                self.cond.notify_all()

    def wait_newer(self, seq: int, timeout: float) -> tuple[int, bytes | None]:
        with self.cond:
            if self.seq == seq and self.failed is None and not self.stop.is_set():
                self.cond.wait(timeout)
            return self.seq, (self.jpeg if self.seq != seq else None)


class CameraManager:
    """Live preview of the cameras, off by default. Never while a command runs (the command needs
    the cameras), never in mock mode, never while SenseCraft holds them."""

    def __init__(self, panel: "Panel", cv2_loader=_import_cv2):
        self.panel = panel
        self.enabled = False
        self.feeds: dict[str, _Feed] = {}
        self.lock = threading.Lock()
        self._cv2_loader = cv2_loader

    def blocked(self) -> str | None:
        if self.panel.mock:
            return "no camera preview in mock mode"
        if self.panel.running():
            return "a command is running and uses the cameras"
        if self.panel.sensecraft_running():
            return SENSECRAFT_BUSY
        if self._cv2_loader is _import_cv2 and not _cv2_installed():
            return "OpenCV (cv2) is not installed"
        return None

    def set_enabled(self, on: bool) -> None:
        if on:
            reason = self.blocked()
            if reason:
                raise PanelError(409, reason)
            self.enabled = True
        else:
            self.release_all()

    def check_stream(self, name: str) -> dict:
        cams = self.panel.camera_configs()
        if name not in cams:
            raise PanelError(404, f"no camera named '{name}' in hackathon.toml")
        if not self.enabled:
            raise PanelError(409, "press Show cameras first")
        reason = self.blocked()
        if reason:
            raise PanelError(409, reason)
        return cams[name]

    def stream(self, name: str, cam: dict, write_frame) -> None:
        """Send frames through write_frame(jpeg) until the preview is switched off or the viewer leaves."""
        with self.lock:
            feed = self.feeds.get(name)
            if feed is None or feed.failed or not feed.thread.is_alive():
                feed = _Feed(name, cam, self._cv2_loader())
                self.feeds[name] = feed
                feed.thread.start()
            feed.viewers += 1
        try:
            seq = 0
            while self.enabled and not feed.stop.is_set() and feed.failed is None:
                seq, jpeg = feed.wait_newer(seq, 1.0)
                if jpeg is not None:
                    write_frame(jpeg)
        finally:
            with self.lock:
                feed.viewers -= 1
                last = feed.viewers <= 0
                if last:
                    feed.stop.set()
                    if self.feeds.get(name) is feed:
                        del self.feeds[name]
            if last:
                feed.thread.join(timeout=3)  # the camera is free again before anyone else asks for it

    def release_all(self) -> None:
        self.enabled = False
        with self.lock:
            feeds, self.feeds = list(self.feeds.values()), {}
        for feed in feeds:
            feed.stop.set()
        for feed in feeds:
            feed.thread.join(timeout=3)

    def status(self) -> dict:
        return {"enabled": self.enabled, "blocked": self.blocked(),
                "failed": {n: f.failed for n, f in list(self.feeds.items()) if f.failed}}


# ----------------------------------------------------------------------------- the panel
class Panel:
    def __init__(self, *, mock: bool = False, mock_speed: float = 1.0, mock_photos: bool = True,
                 host: str = "127.0.0.1", port: int = DEFAULT_PORT, token: str | None = None,
                 sensecraft_probe=SC.is_running, cv2_loader=_import_cv2):
        self.mock, self.mock_speed, self.mock_photos = mock, mock_speed, mock_photos
        self.host, self.port = host, port
        self.lan = host not in LOOPBACK_NAMES
        self.token = token or secrets.token_urlsafe(24)
        self.nonce = secrets.token_urlsafe(16)
        names = {socket.gethostname().lower()}
        self.extra_names = tuple(sorted(names | {n + ".local" for n in names}))
        self.lock = threading.RLock()
        self.log = LogBuffer()
        self.parser: SessionParser | None = None
        self.child: Child | None = None
        self.run_id = 0
        self.finishing = False
        self._finish_sent_for: tuple | None = None
        self._probe = sensecraft_probe
        self._sc_value = False
        self._sc_time = -1e9
        self._sc_lock = threading.Lock()
        self._photo_cache: tuple[float, int, dict | None] = (-1e9, -1, None)
        self._settings_cache: tuple[float, dict] = (-1e9, {})
        self.cameras = CameraManager(self, cv2_loader)
        self._html: str | None = None

    # -- facts ------------------------------------------------------------------
    def running(self) -> bool:
        child = self.child
        return child is not None and child.alive()

    def sensecraft_running(self, fresh: bool = False) -> bool:
        with self._sc_lock:
            now = time.monotonic()
            if fresh or now - self._sc_time > 5:
                try:
                    self._sc_value = bool(self._probe())
                except Exception:  # noqa: BLE001 - a status light must never break the page
                    self._sc_value = False
                self._sc_time = now
            return self._sc_value

    def camera_configs(self) -> dict:
        try:
            cams = C.load_config().get("cameras", {})
        except (SystemExit, Exception):  # noqa: BLE001 - shown as "no cameras"
            return {}
        return {n: dict(c) for n, c in cams.items() if isinstance(c, dict)}

    def photo_roots(self) -> list[Path]:
        return [MOCK_DIR, DEMO_DIR] if self.mock else [DEMO_DIR]

    def latest_photo(self) -> dict | None:
        runs_seen = self.parser.runs_seen if self.parser else -1
        stamp, seen, value = self._photo_cache
        if time.monotonic() - stamp < 1.0 and seen == runs_seen:
            return value
        value = latest_check_photo(self.photo_roots())
        self._photo_cache = (time.monotonic(), runs_seen, value)
        return value

    def _settings(self) -> dict:
        """Files the status bar shows (.env choice, cameras), re-read at most every 3 s."""
        stamp, value = self._settings_cache
        if time.monotonic() - stamp < 3.0:
            return value
        try:
            check = env_setting("RETRY_CHECK")
        except ValueError:
            check = None
        cams = self.camera_configs()
        value = {"retry_check": (check or "").lower() or None, "keys": keys_present(),
                 "cameras": [{"name": n, "index": str(c.get("index_or_path", ""))} for n, c in cams.items()]}
        self._settings_cache = (time.monotonic(), value)
        return value

    def status(self) -> dict:
        return {"sensecraft": self.sensecraft_running(), "mock": self.mock, "lan": self.lan,
                **self._settings(), "camera_preview": self.cameras.status()}

    def models(self) -> dict:
        try:
            found = SC.models()
        except Exception:  # noqa: BLE001 - SenseCraft missing or its files unreadable
            found = []
        local = []  # models trained on this computer (so train, or lerobot-train into outputs/train)
        for cfg_file in sorted((ROOT / "outputs" / "train").glob("*/checkpoints/last/pretrained_model/config.json"),
                               key=lambda p: p.stat().st_mtime, reverse=True):
            run = cfg_file.parents[3]
            steps = [int(p.name) for p in (run / "checkpoints").iterdir() if p.name.isdigit()]
            local.append({"name": run.name, "steps": max(steps) if steps else None, "kind": "local",
                          "path": cfg_file.parent.relative_to(ROOT).as_posix()})
        return {"models": local + [{"name": m.name, "steps": m.steps, "updated": m.updated[:16], "kind": "sensecraft"}
                                   for m in found]}

    def results(self) -> dict:
        return {"demo": summarize_demo_log(), "eval": summarize_eval_log()}

    # -- state for the page -----------------------------------------------------------
    def state(self, since: int) -> dict:
        seq, lines, truncated = self.log.since(since)
        with self.lock:
            child = self.child
            session = self.parser.snapshot() if self.parser else None
            proc = None
            if child is not None:
                proc = {"cmd": child.command.cmd, "shown": child.command.shown, "running": child.alive(),
                        "pid": child.proc.pid if child.proc else None, "started": child.started,
                        "exit_code": child.exit_code, "mocked": child.command.mocked,
                        "dry_run": child.command.dry_run, "prompts": child.command.prompts,
                        "finishing": self.finishing}
        return {"seq": seq, "lines": lines, "truncated": truncated, "run_id": self.run_id, "proc": proc,
                "session": session, "photo": self.latest_photo(), "status": self.status()}

    # -- actions ------------------------------------------------------------------
    def start_command(self, req: dict) -> dict:
        command = build_command(req, mock=self.mock, mock_speed=self.mock_speed, mock_photos=self.mock_photos)
        with self.lock:
            if self.running():
                raise PanelError(409, "a command is already running: Finish or Abort it first")
            if command.hardware and self.sensecraft_running(fresh=True):
                raise PanelError(409, SENSECRAFT_BUSY)
            self.cameras.release_all()  # the command needs the cameras
            self.run_id += 1
            rid = self.run_id
            self.parser = SessionParser(command.cmd, attempts_total=command.attempts, tries=command.tries)
            self.finishing, self._finish_sent_for = False, None
            self.log.add(f"──── {command.shown}{'   (simulated: no robot)' if command.mocked else ''} ────")
            child = Child(command, on_line=lambda line: self._on_line(rid, line),
                          on_exit=lambda code: self._on_exit(rid, code))
            try:
                child.start()
            except OSError as e:
                self.parser.on_exit(-1)
                raise PanelError(500, f"could not start {command.shown}: {e}") from e
            self.child = child
        return {"shown": command.shown, "run_id": rid, "mocked": command.mocked}

    def _on_line(self, rid: int, line: str) -> None:
        self.log.add(line)
        with self.lock:
            if rid != self.run_id or self.parser is None:
                return
            self.parser.feed(line)
            self._keep_finishing()

    def _on_exit(self, rid: int, code: int) -> None:
        with self.lock:
            if rid == self.run_id and self.parser is not None:
                self.parser.on_exit(code)
                self.finishing = False
            cmd = self.child.command.shown if self.child else "the command"
        self.log.add(f"[panel] {cmd} ended (exit code {code})")

    def _keep_finishing(self) -> None:
        """After Finish: stop each new run and answer q at the next prompt (lock held)."""
        if not self.finishing or self.parser is None or self.child is None:
            return
        p = self.parser
        key = (p.prompt, p.attempt, p.run)
        if key == self._finish_sent_for:
            return
        try:
            if p.prompt == "attempt":
                self.child.write("q")
                p.on_input("q")
            elif p.prompt == "running" and not p.stop_requested:
                self.child.write("")
                p.on_input("")
            else:
                return
        except PanelError:
            return
        self._finish_sent_for = key

    def send_input(self, req: dict) -> dict:
        text = req.get("text", "")
        expect = req.get("expect", "any")
        if not isinstance(text, str) or len(text) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in text):
            raise PanelError(400, "text: one line of at most 200 characters")
        if expect not in EXPECTS:
            raise PanelError(400, f"expect must be one of: {', '.join(EXPECTS)}")
        with self.lock:
            child = self.child
            if child is None or not child.alive():
                raise PanelError(409, "nothing is running")
            prompt = self.parser.prompt if self.parser else None
            if expect != "any" and prompt != expect:
                # e.g. a double click: the second Enter would stop the run the first one started
                raise PanelError(409, "the program is not waiting for that right now")
            child.write(text)
            if self.parser is not None:
                self.parser.on_input(text)
        return {}

    def finish(self, req: dict | None = None) -> dict:
        with self.lock:
            child = self.child
            if child is None or not child.alive():
                raise PanelError(409, "nothing is running")
            if not child.command.prompts:  # teleop, cameras, doctor, dry runs: no prompts to answer
                child.interrupt()
                self.log.add("[panel] Finish: interrupt sent")
                return {}
            if self.parser is not None and self.parser.prompt == "result":
                raise PanelError(409, "mark this run first: Success, Fail or Skip")
            self.finishing = True
            self.log.add("[panel] Finish: the arm stops after this run, returns to its start pose and the session ends")
            self._keep_finishing()
        return {}

    def abort(self, req: dict | None = None) -> dict:
        with self.lock:
            child = self.child
            if child is None or not child.alive():
                raise PanelError(409, "nothing is running")
            child.interrupt()
        self.log.add("[panel] Abort: interrupt sent (Ctrl+Break / SIGINT); killed in 5 s if still running")

        def kill_later() -> None:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and child.alive():
                time.sleep(0.1)
            if child.alive():
                child.kill_tree()
                self.log.add("[panel] still running after 5 s: process tree killed")

        threading.Thread(target=kill_later, name="panel-abort", daemon=True).start()
        return {}

    def set_cameras(self, req: dict) -> dict:
        self.cameras.set_enabled(bool(req.get("on")))
        return {"camera_preview": self.cameras.status()}

    def close(self, wait: float = 12.0) -> None:
        """Panel shutdown: end the running program the gentle way first."""
        self.cameras.release_all()
        child = self.child
        if child is None or not child.alive():
            return
        try:
            if child.command.prompts:
                with self.lock:
                    if self.parser is not None and self.parser.prompt == "result":
                        child.write("x")
                        self.parser.on_input("x")
                self.finish()
            else:
                child.interrupt()
        except PanelError:
            pass
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline and child.alive():
            time.sleep(0.1)
        if child.alive():
            child.interrupt()
            time.sleep(3)
            child.kill_tree()

    # -- access ---------------------------------------------------------------------
    def check_host(self, host: str | None) -> None:
        if not host_allowed(host, self.port, self.lan, self.extra_names):
            raise PanelError(403, "unexpected Host header")

    def check_origin(self, origin: str | None) -> None:
        if not origin_allowed(origin, self.port, self.lan, self.extra_names):
            raise PanelError(403, "requests from other web sites are not accepted")

    def token_ok(self, given: str | None) -> bool:
        return bool(given) and hmac.compare_digest(given.encode(), self.token.encode())

    def check_token(self, given: str | None) -> None:
        if not self.token_ok(given):
            raise PanelError(403, "missing or wrong access token: reload the page from the link the panel printed")

    def page(self) -> str:
        if self._html is None:
            self._html = HTML_FILE.read_text(encoding="utf-8")
        cfg = {"mock": self.mock, "lan": self.lan, "defaults": {"tries": 3, "attempts": 5, "seconds": 40}}
        cfg_json = json.dumps(cfg).replace("<", "\\u003c")
        return (self._html.replace("__PANEL_TOKEN__", self.token).replace("__PANEL_NONCE__", self.nonce)
                .replace("__PANEL_CONFIG__", cfg_json))


# ----------------------------------------------------------------------------- HTTP
class _Handler(BaseHTTPRequestHandler):
    server_version = "CrimsonSnowPanel/1"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - the page polls several times a second
        pass

    @property
    def panel(self) -> Panel:
        return self.server.panel  # type: ignore[attr-defined]

    def _headers(self, status: int, ctype: str, length: int, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, status: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        extra = {"Connection": "close"} if status >= 400 else None
        if status >= 400:
            self.close_connection = True
        self._headers(status, "application/json; charset=utf-8", len(body), extra)
        self.wfile.write(body)

    def _fail(self, e: PanelError) -> None:
        self._json(e.status, {"ok": False, "error": e.message})

    def _query(self) -> tuple[str, dict]:
        url = urlsplit(self.path)
        return url.path, parse_qs(url.query)

    def do_GET(self):  # noqa: N802
        path, query = self._query()
        try:
            self.panel.check_host(self.headers.get("Host"))
            if path == "/":
                return self._page(query)
            if path == "/favicon.ico":
                self._headers(204, "text/plain", 0)
                return None
            if not path.startswith("/api/"):
                raise PanelError(404, "not found")
            self.panel.check_token(self.headers.get("X-Panel-Token") or (query.get("t") or [""])[0])
            if path == "/api/state":
                try:
                    since = int((query.get("since") or ["0"])[0] or 0)
                except ValueError:
                    since = 0
                return self._json(200, self.panel.state(since))
            if path == "/api/results":
                return self._json(200, self.panel.results())
            if path == "/api/models":
                return self._json(200, self.panel.models())
            if path == "/api/photo":
                return self._photo((query.get("path") or [""])[0])
            if path.startswith("/api/camera/"):
                return self._camera(path[len("/api/camera/"):])
            raise PanelError(404, "not found")
        except PanelError as e:
            self._fail(e)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        return None

    def do_POST(self):  # noqa: N802
        path, _ = self._query()
        try:
            self.panel.check_host(self.headers.get("Host"))
            self.panel.check_origin(self.headers.get("Origin"))
            self.panel.check_token(self.headers.get("X-Panel-Token"))
            routes = {"/api/run": self.panel.start_command, "/api/input": self.panel.send_input,
                      "/api/finish": self.panel.finish, "/api/abort": self.panel.abort,
                      "/api/cameras": self.panel.set_cameras}
            action = routes.get(path)
            if action is None:
                raise PanelError(404, "not found")
            result = action(self._body())
            self._json(200, {"ok": True, **(result or {})})
        except PanelError as e:
            self._fail(e)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise PanelError(400, "bad Content-Length") from None
        if length > MAX_BODY or length < 0:
            raise PanelError(413, "request too large")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise PanelError(415, "send JSON")
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise PanelError(400, "invalid JSON") from None
        if not isinstance(data, dict):
            raise PanelError(400, "expected a JSON object")
        return data

    def _page(self, query: dict) -> None:
        if self.panel.lan and not self.panel.token_ok((query.get("t") or [""])[0]):
            raise PanelError(403, "open the link the panel printed (it carries the access token)")
        body = self.panel.page().encode("utf-8")
        csp = (f"default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; "
               f"script-src 'nonce-{self.panel.nonce}'; connect-src 'self'; base-uri 'none'; "
               f"form-action 'none'; frame-ancestors 'none'")
        self._headers(200, "text/html; charset=utf-8", len(body), {"Content-Security-Policy": csp})
        self.wfile.write(body)

    def _photo(self, rel: str) -> None:
        full = resolve_photo(rel, self.panel.photo_roots())
        if full is None:
            raise PanelError(404, "no such photo")
        data = full.read_bytes()
        self._headers(200, PHOTO_TYPES[full.suffix.lower()], len(data))
        self.wfile.write(data)

    def _camera(self, name: str) -> None:
        cam = self.panel.cameras.check_stream(name)
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        def write_frame(jpeg: bytes) -> None:
            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                             + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
            self.wfile.flush()

        try:
            self.panel.cameras.stream(name, cam, write_frame)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = not R.IS_WINDOWS  # on Windows it would let two panels share a port

    def __init__(self, panel: Panel):
        self.panel = panel
        super().__init__((panel.host, panel.port), _Handler)
        panel.port = self.server_address[1]  # the real one when port 0 was asked for

    def server_bind(self):
        # HTTPServer.server_bind looks the host name up in DNS, which can stall for seconds.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = str(self.server_address[0]), self.server_address[1]


def _lan_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent: this only picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


# ----------------------------------------------------------------------------- simulated programs (--mock)
MOCK_RUN_FACTOR = 0.25  # a simulated run lasts a quarter of the seconds it reports
# What the simulated attempts do, run by run: (seconds, ended_by, grip, camera verdict, explanation).
MOCK_SCRIPT = (
    [(19.6, "arm back at rest", "held", "in_box", "The battery lies inside the cardboard box.")],
    [(21.2, "arm back at rest", "missed", "on_mat", "The battery is still on the mat, next to the gripper."),
     (18.4, "arm back at rest", "held", "in_box", "The battery is in the box now.")],
    [(20.3, "arm back at rest", "held", "in_box", "The battery is inside the box.")],
    [(9.8, "arm back at rest", "never_opened", "on_mat", "The battery is still standing on the mat."),
     (24.0, "arm back at rest", "held", "elsewhere", "The battery fell on the table beside the mat.")],
    [(18.9, "arm back at rest", "held", "in_box", "The battery is in the box.")],
)
MOCK_CHECK_MODEL = {"local": "local model", "openai": "gpt-5.5", "claude": "claude-opus-5-5"}


class _Mock:
    def __init__(self, args):
        self.args = args
        self.speed = max(args.speed, 0.0)
        self.lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, name="mock-stdin", daemon=True).start()
        self.session_dir: Path | None = None
        self.pool: dict = {}
        if not args.no_photos:
            self.pool = labelled_frames()
            if self.pool:
                self.session_dir = MOCK_DIR / time.strftime("%Y%m%d_%H%M%S")
                self._tidy()

    def _read(self) -> None:
        for line in sys.stdin:
            self.lines.put(line)
        self.lines.put(None)

    def _tidy(self, keep: int = 4) -> None:
        if not MOCK_DIR.is_dir():
            return
        old = sorted(d for d in MOCK_DIR.iterdir() if d.is_dir() and SESSION_RE.match(d.name))
        for d in old[: max(len(old) - keep, 0)]:
            shutil.rmtree(d, ignore_errors=True)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds * self.speed)

    def ask(self, prompt: str) -> str | None:
        print(prompt, flush=True)
        return self.lines.get()

    def run_arm(self, seconds: float, ended_by: str) -> tuple[float, str]:
        """A simulated run; Enter (any line) stops it early, like the real one."""
        while True:  # an Enter typed before the run must not stop it
            try:
                if self.lines.get_nowait() is None:
                    self.lines.put(None)
                    break
            except queue.Empty:
                break
        wall = seconds * MOCK_RUN_FACTOR * self.speed
        t0 = time.monotonic()
        while time.monotonic() - t0 < wall:
            try:
                line = self.lines.get(timeout=0.02)
            except queue.Empty:
                continue
            if line is None:
                self.lines.put(None)
                continue
            done = (time.monotonic() - t0) / (MOCK_RUN_FACTOR * self.speed) if self.speed else 0.0
            return min(done, seconds), "stopped by you"
        return seconds, ended_by

    def photo(self, attempt: int, run: int, location: str | None) -> None:
        if self.session_dir is None:
            return
        choices = self.pool.get(location or "") or [p for v in self.pool.values() for p in v]
        if not choices:
            return
        scene, wrist = choices[(attempt * 3 + run) % len(choices)]
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            for src in (scene, wrist):
                if src is not None:
                    cam = FRAME_RE.match(src.name)[3]
                    shutil.copyfile(src, self.session_dir / f"attempt{attempt:02d}_run{run}_{cam}{src.suffix.lower()}")
        except (OSError, TypeError):
            pass

    # -- `so demo` -----------------------------------------------------------------
    def demo(self) -> int:
        a = self.args
        check = a.check if a.check != "auto" else (env_setting("RETRY_CHECK") or "auto").lower()
        model = MOCK_CHECK_MODEL.get(check, "")
        words = (f"{model} looks at camera 'top' + gripper position" if model
                 else "gripper position only (no API key found: the box is not checked)")
        tries = max(a.tries, 1)
        print("[mock] No robot, no cameras: a simulated `so demo` session with the same prompts and output.", flush=True)
        print(f"\n[demo] Policy: {a.label}\n[demo] Up to {tries} runs per attempt. Check: {words}\n"
              f"[demo] Ctrl+C stops the arm and ends the session.", flush=True)
        results: list[tuple[bool, int]] = []
        while a.attempts == 0 or len(results) < a.attempts:
            n = len(results) + 1
            line = self.ask(f"\n[demo] Attempt {n}: put the battery on its place, then press Enter (q + Enter = finish)")
            if line is None or line.strip().lower() in ("q", "quit", "exit"):
                break
            script = MOCK_SCRIPT[(n - 1) % len(MOCK_SCRIPT)]
            reported = 0.0
            runs = 0
            success = False
            for run_no in range(1, tries + 1):
                seconds, ended_by, grip, location, explanation = script[min(run_no, len(script)) - 1]
                seconds, ended_by = self.run_arm(seconds, ended_by)
                self.sleep(1.2)  # return to the start pose + the check
                runs += 1
                reported += seconds + 4.0
                loc = location if model else None
                self.photo(n, run_no, location)
                success, retry, reason = decide(Check(grip=grip, location=loc))
                camera = f"camera: {loc.replace('_', ' ')}" if loc else "camera: not used"
                print(f"[demo]   run {run_no}: {seconds:.1f} s ({ended_by}) | grip: {grip} | {camera}"
                      f"\n[demo]   -> {'SUCCESS' if success else 'not done'}: {reason}", flush=True)
                if model:
                    print(f"[demo]      {model}: {explanation}", flush=True)
                if success or not retry:
                    break
                if run_no < tries:
                    print("[demo]   running the policy again from the start pose...", flush=True)
            results.append((success, runs))
            print(f"[demo] Attempt {n}: {'SUCCESS' if success else 'FAILED'} in {reported:.0f} s"
                  f" ({runs} run{'s' if runs > 1 else ''})", flush=True)
        if results:
            ok = sum(s for s, _ in results)
            rescued = sum(s and r > 1 for s, r in results)
            print(f"\n[demo] {ok}/{len(results)} attempts succeeded, {rescued} of them thanks to a retry. "
                  f"(simulated: nothing was logged)", flush=True)
        return 0

    # -- `so try` ------------------------------------------------------------------
    def try_(self) -> int:
        print("[mock] No robot, no cameras: a simulated `so try` session with the same prompts and output.", flush=True)
        print(f"\n[try] Policy: {self.args.label}\n"
              "[try] Each attempt: set up the scene, press Enter, watch. Press Enter during a run to stop the arm.\n"
              "[try] After each run type  s  (success) or  f  (fail), optionally with a note, e.g.  f missed grip place 3\n"
              "[try]   x = do not log this run, q = finish. Ctrl+C stops everything.", flush=True)
        results: list[tuple[str, str]] = []
        k = 0
        while True:
            line = self.ask(f"\n[try] Attempt {len(results) + 1}: set up the scene, then press Enter (q = finish)")
            if line is None or line.strip().lower() in ("q", "quit", "exit"):
                break
            seconds, ended_by, grip, _, _ = MOCK_SCRIPT[k % len(MOCK_SCRIPT)][0]
            k += 1
            seconds, ended_by = self.run_arm(seconds, ended_by)
            self.sleep(0.8)  # like the real `so try`: no photo is saved, you judge the run
            print(f"[try]   {seconds:.1f} s ({ended_by}), gripper: {GRIP_WORDS.get(grip, grip)}. "
                  "The arm is back at its start pose.", flush=True)
            answer = None
            while True:
                answer = self.ask("[try]   Result? s = success, f = fail (+ note), x = do not log")
                if answer is None:
                    break
                key, _, note = answer.strip().partition(" ")
                key = key.lower()
                if key in ("s", "f"):
                    results.append((key, note.strip()))
                    break
                if key == "x":
                    break
                print("[try]   type s, f or x", flush=True)
            if answer is None:
                break
        if results:
            ok = sum(k == "s" for k, _ in results)
            print(f"\n[try] {ok}/{len(results)} successes this session.", flush=True)
            fails = [note or "(no note)" for key, note in results if key == "f"]
            if fails:
                print("[try] Failures:\n" + "\n".join(f"[try]   - {n}" for n in fails), flush=True)
            print("[try] (simulated: nothing was logged)", flush=True)
        return 0

    def teleop(self) -> int:
        print("[mock] Simulated teleoperation: the follower would mirror the leader. Finish or Abort ends it.", flush=True)
        beat = 0
        while True:
            try:
                line = self.lines.get(timeout=max(2.0 * self.speed, 0.05))
            except queue.Empty:
                beat += 1
                print(f"[mock] teleop running ({beat * 2} s)", flush=True)
                continue
            if line is None or line.strip().lower() in ("q", "quit", "exit"):
                print("[mock] teleop stopped", flush=True)
                return 0

    def cameras(self) -> int:
        self.sleep(0.5)
        print("[mock] Simulated `so cameras`: 0 = laptop webcam, 1 = overhead camera, 2 = wrist camera", flush=True)
        return 0

    def doctor(self) -> int:
        for line in ("GPU            ok   (simulated)", "ffmpeg         ok   (simulated)",
                     "Arms           ok   follower + leader found (simulated)",
                     "Cameras        ok   top + wrist (simulated)", "0 problems, 0 warnings (simulated)"):
            self.sleep(0.25)
            print(f"[mock] {line}", flush=True)
        return 0


def mock_child(argv: list[str]) -> int:
    """The program --mock runs instead of a real `so` command (no robot, no cameras, nothing logged)."""
    p = argparse.ArgumentParser(prog="python -m sokit.panel --mock-child")
    p.add_argument("cmd", choices=COMMANDS)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--attempts", type=int, default=5)
    p.add_argument("--tries", type=int, default=3)
    p.add_argument("--check", default="auto")
    p.add_argument("--label", default="mock policy")
    p.add_argument("--no-photos", action="store_true")
    args = p.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    mock = _Mock(args)
    try:
        return {"demo": mock.demo, "try": mock.try_, "teleop": mock.teleop,
                "cameras": mock.cameras, "doctor": mock.doctor}[args.cmd]()
    except KeyboardInterrupt:
        print("\n[mock] stopping", flush=True)
        return 130


# ----------------------------------------------------------------------------- entry point
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="so panel", description="Local control panel for the robot demo: a web page "
                                "with big buttons, the live score and the last check photo.")
    p.add_argument("--host", default="127.0.0.1",
                   help="127.0.0.1 = this computer only (default); 0.0.0.0 = also phones/laptops on the local network")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default {DEFAULT_PORT}")
    p.add_argument("--mock", action="store_true",
                   help="no robot: commands are simulated (rehearse the presentation anywhere)")
    p.add_argument("--no-browser", action="store_true", help="do not open the browser")
    p.add_argument("--mock-speed", type=float, default=1.0, help=argparse.SUPPRESS)
    return p


def serve(panel: Panel, open_browser: bool = True) -> int:
    try:
        server = PanelServer(panel)
    except OSError as e:
        print(f"[panel] cannot listen on {panel.host}:{panel.port} ({e}). Another panel running? "
              f"Try: so panel --port {panel.port + 1}")
        return 1
    if panel.lan:
        url = f"http://{_lan_address()}:{panel.port}/?t={panel.token}"
        local = f"http://127.0.0.1:{panel.port}/?t={panel.token}"
        print("[panel] WARNING: reachable from the local network. Anyone with this link can move the arm:\n"
              f"[panel]   {url}")
    else:
        url = local = f"http://127.0.0.1:{panel.port}/"
        print(f"[panel] Control panel: {url}   (this computer only)")
    if panel.mock:
        print("[panel] MOCK mode: no robot and no cameras are used; every command is simulated.")
    else:
        if panel.sensecraft_running(fresh=True):
            print(f"[panel] {SENSECRAFT_BUSY}")
        print("[panel] The arm moves for real: someone stays at the robot.")
    print("[panel] Ctrl+C here closes the panel (a running session is finished first).")
    if open_browser:
        try:
            webbrowser.open(local)
        except Exception:  # noqa: BLE001 - the link is printed anyway
            pass
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n[panel] closing: ending the running command first (the arm returns to its start pose)")
    finally:
        panel.close()
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--mock-child"]:
        return mock_child(argv[1:])
    args = build_arg_parser().parse_args(argv)
    if not 0 <= args.port <= 65535:
        raise SystemExit("--port must be 0-65535")
    panel = Panel(mock=args.mock, mock_speed=args.mock_speed, host=args.host, port=args.port)
    return serve(panel, open_browser=not args.no_browser)


if __name__ == "__main__":
    sys.exit(main())
