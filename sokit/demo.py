"""Demo with automatic retries: run the trained policy, check the result, run it again if it failed.

    python -m sokit.demo [--tries 3] [--attempts 5] [--check auto|claude|openai|local|grip] -- <lerobot-rollout flags>

The camera check is picked with --check, or (when --check is auto) with RETRY_CHECK in the
repository's .env: local = our own vision model (sokit/vision.py, offline), openai = ChatGPT,
claude = Claude, grip = the gripper position only.

Normally started with `so demo`, which builds the lerobot-rollout flags from hackathon.toml.

One demo attempt: someone puts the battery on the mat and presses Enter. From then on nobody
touches the robot:

1. the policy runs until the arm has gone out, come back to rest and stopped (or the time limit);
2. the arm returns exactly to the pose it started from;
3. the result is checked twice:
   - from the gripper's own position: holding the battery keeps it partly open (about 12-45 on
     its 0-100 scale in our recordings) while it is told to close; closing on nothing ends near 1;
   - by a vision model (Claude, or an OpenAI model when only an OpenAI key is set) looking at the
     overhead camera: is the battery in the box, still on the mat, ...;
4. if the battery is still on the mat (or the gripper missed), the policy runs again from the
   start pose, up to --tries runs per attempt.

Everything runs inside one LeRobot rollout (RolloutController, LeRobot 0.7.0): policy, arm and
cameras stay loaded between runs, and the camera frames for the check come from the same
connection the policy uses. Results go to journal/demo.csv, the checked frames to outputs/demo/.

No `from __future__ import annotations` here: LeRobot's config parser reads the type annotation
of the wrapped function at runtime.
"""

import argparse
import base64
import csv
import datetime as dt
import io
import json
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO_LOG = ROOT / "journal" / "demo.csv"
FRAMES_DIR = ROOT / "outputs" / "demo"

DEFAULT_MODELS = {
    "claude": "claude-opus-5-5",
    # Picked on 21 Nov 2026: 8/8 correct on overhead (+ wrist) frames of our recordings, ~3 s per answer.
    # gpt-5.4-mini was also 8/8 at ~1.3 s: pass --model gpt-5.4-mini for faster checks.
    "openai": "gpt-5.5",
    # Our own model (sokit/vision.py), trained on our recordings: `so vision prepare && so vision train`.
    "local": "outputs/vision/model/battery_check.pt",
}
MODEL_ENV = {"claude": "CLAUDE_CHECK_MODEL", "openai": "OPENAI_CHECK_MODEL", "local": "LOCAL_CHECK_MODEL"}
# RETRY_CHECK in .env picks the check when --check is auto; these words are accepted.
CHECK_NAMES = {"auto": "auto", "local": "local", "opencv": "local", "vision": "local", "own": "local",
               "openai": "openai", "chatgpt": "openai", "gpt": "openai", "claude": "claude",
               "anthropic": "claude", "grip": "grip", "gripper": "grip", "none": "grip"}

# ----------------------------------------------------------------------------- cameras (pure)
SCENE_WORDS = ("top", "front", "overhead", "scene", "base", "external", "table")
WRIST_WORDS = ("wrist", "gripper", "hand")


def camera_role(name: str) -> str | None:
    """'scene' for a fixed camera over the table, 'wrist' for the one on the gripper, else None."""
    n = name.lower()
    if any(w in n for w in WRIST_WORDS):
        return "wrist"
    if any(w in n for w in SCENE_WORDS):
        return "scene"
    return None


def policy_cameras(policy_path: str) -> list[str]:
    """Camera names a trained policy expects, read from its config.json ([] if not readable)."""
    cfg_file = Path(policy_path) / "config.json"
    try:
        features = json.loads(cfg_file.read_text(encoding="utf-8")).get("input_features", {})
    except (OSError, ValueError):
        return []
    prefix = "observation.images."
    return [k[len(prefix):] for k in features if k.startswith(prefix)]


def trained_on_sensecraft_data(policy_cams: list[str]) -> bool:
    """SenseCraft records the cameras as `front` and `gripper`; our own recordings use `top` and `wrist`."""
    return set(policy_cams) == {"front", "gripper"}


def parse_rename(text: str | None) -> dict[str, str]:
    """'top=front,wrist=gripper' -> {'top': 'front', 'wrist': 'gripper'}."""
    out: dict[str, str] = {}
    for part in (text or "").split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise SystemExit(f"--rename: expected ours=theirs pairs like top=front,wrist=gripper (got '{part}')")
        ours, theirs = (s.strip() for s in part.split("=", 1))
        out[ours] = theirs
    return out


def camera_rename(policy_cams: list[str], our_cams: list[str], explicit: dict[str, str] | None = None) -> dict[str, str]:
    """Map our camera names onto the names the policy was trained with, as LeRobot's --rename_map.

    SenseCraft records the overhead camera as `front` and the wrist camera as `gripper`; our
    configuration calls them `top` and `wrist`. Matching is by role (scene vs wrist), so a
    swapped camera can only come from a wrong camera *number*, which `so demo` prints first.
    """
    if explicit:
        mapping = dict(explicit)
    elif not policy_cams or set(policy_cams) == set(our_cams):
        return {}
    else:
        mapping = {}
        for theirs in policy_cams:
            role = camera_role(theirs)
            ours = [c for c in our_cams if role is not None and camera_role(c) == role]
            if len(ours) != 1:
                raise SystemExit(
                    f"[so] The policy expects cameras {policy_cams}, this computer has {our_cams}, and "
                    f"'{theirs}' cannot be matched by role. Pass the mapping, e.g. --rename top=front,wrist=gripper"
                )
            mapping[ours[0]] = theirs
    if policy_cams and sorted(mapping.values()) != sorted(policy_cams):
        raise SystemExit(f"[so] Camera mapping {mapping} does not cover the policy's cameras {policy_cams}")
    unknown = [c for c in mapping if c not in our_cams]
    if unknown:
        raise SystemExit(f"[so] --rename names cameras {unknown}, but hackathon.toml has {our_cams}")
    return {f"observation.images.{o}": f"observation.images.{t}" for o, t in mapping.items() if o != t}


def rename_map_arg(rename: dict[str, str]) -> str:
    """--rename_map value in the same YAML-like shape `so rollout` uses."""
    return "{" + ", ".join(f"{k}: {v}" for k, v in rename.items()) + "}"


# ----------------------------------------------------------------------------- gripper (pure)
# Gripper position is 0 (closed) .. 100 (open). Measured in our 108 battery recordings:
# rest 1.6; opened to 41-93 (median 60) before grabbing; while holding the battery the
# gripper is told to close (command ~0) but stays at 12-45 (median 36) because the battery
# is in the way. Closing on nothing goes all the way down to ~1.
GRIP_OPEN = 25.0      # the gripper has opened to grab
CLOSE_DROP = 10.0     # it started closing: this far below its widest opening
GRIP_EMPTY = 5.0      # closed on nothing
HOLD_MIN, HOLD_MAX = 8.0, 48.0  # stopped part-way: something is in the jaws
HOLD_WOBBLE = 4.0     # while holding, the position barely moves...
HOLD_SECONDS = 0.5    # ...for at least this long


def grip_verdict(samples: list[tuple[float, float | None]]) -> str:
    """'held', 'missed', 'never_opened' or 'unknown' from (seconds, gripper position) samples."""
    pts = [(t, float(g)) for t, g in samples if g is not None]
    if not pts:
        return "unknown"
    state, peak, low = "closed", 0.0, 0.0
    window: list[tuple[float, float]] = []
    missed = False
    for t, g in pts:
        if state == "closed":
            if g >= GRIP_OPEN:
                state, peak = "open", g
        elif state == "open":
            peak = max(peak, g)
            if g <= peak - CLOSE_DROP:
                state, low, window = "closing", g, []
        if state != "closing":
            continue
        low = min(low, g)
        if g >= GRIP_OPEN and g >= low + CLOSE_DROP:  # opened again: a new grab begins
            state, peak, window = "open", g, []
            continue
        if g <= GRIP_EMPTY:
            missed, window = True, []
            continue
        if not HOLD_MIN <= g <= HOLD_MAX:
            window = []
            continue
        window.append((t, g))
        while max(v for _, v in window) - min(v for _, v in window) > HOLD_WOBBLE:
            window.pop(0)
        if window[-1][0] - window[0][0] >= HOLD_SECONDS:
            return "held"
    if missed:
        return "missed"
    return "never_opened" if state == "closed" else "unknown"


# ----------------------------------------------------------------------------- end of a run (pure)
class MotionWatch:
    """Says when a run is over: the arm went out to work, came back to rest and stopped.

    Watches the two big joints, which differ most between reaching and the folded rest pose
    (in our recordings the rest pose varies by under 5 degrees on them).
    """

    JOINTS = ("shoulder_lift.pos", "elbow_flex.pos")

    def __init__(self, home: dict, out_deg: float = 20.0, back_deg: float = 15.0,
                 still_deg: float = 1.5, still_s: float = 1.0):
        self.home = {j: float(home[j]) for j in self.JOINTS if j in home}
        self.out_deg, self.back_deg, self.still_deg, self.still_s = out_deg, back_deg, still_deg, still_s
        self.went_out = False
        self._window: list[tuple[float, list[float]]] = []

    @property
    def usable(self) -> bool:
        return len(self.home) == len(self.JOINTS)

    def feed(self, t: float, positions: dict) -> bool:
        if not self.usable or any(j not in positions for j in self.JOINTS):
            return False
        values = [float(positions[j]) for j in self.JOINTS]
        away = max(abs(v - self.home[j]) for v, j in zip(values, self.JOINTS))
        if away > self.out_deg:
            self.went_out = True
        if not self.went_out or away > self.back_deg:
            self._window.clear()
            return False
        self._window.append((t, values))
        while self._window and t - self._window[0][0] > self.still_s:
            self._window.pop(0)
        spans = [max(v[i] for _, v in self._window) - min(v[i] for _, v in self._window) for i in range(len(self.JOINTS))]
        return t - self._window[0][0] >= self.still_s * 0.9 and max(spans) <= self.still_deg


# ----------------------------------------------------------------------------- verdict (pure)
LOCATIONS = ("in_box", "on_mat", "in_gripper", "elsewhere", "not_visible")


@dataclass
class Check:
    grip: str                    # held | missed | never_opened | unknown
    location: str | None = None  # Claude's answer (one of LOCATIONS), None when not asked
    explanation: str = ""
    error: str = ""              # why Claude gave no answer


def decide(check: Check) -> tuple[bool, bool, str]:
    """(success, worth running again, reason in plain words)."""
    loc = check.location
    if loc == "in_box":
        return True, False, "battery is in the box"
    if loc == "on_mat":
        return False, True, "battery is still on the mat"
    if loc == "in_gripper":
        return False, True, "battery is still in the gripper"
    if loc == "elsewhere":
        return False, False, "battery left the mat: put it back by hand"
    if loc == "not_visible":
        if check.grip == "held":
            return True, False, "gripper held the battery and it is no longer on the mat"
        return False, True, "battery not visible and no grip detected"
    # No camera verdict: the gripper alone (it cannot see the box).
    if check.grip == "held":
        return True, False, "gripper closed on the battery (box not checked)"
    if check.grip == "missed":
        return False, True, "gripper closed on nothing"
    if check.grip == "never_opened":
        return False, True, "the gripper never opened"
    return False, True, "no clear grip signal"


# ----------------------------------------------------------------------------- camera check (Claude or OpenAI)
CHECK_PROMPT = (
    "You check the result of one pick-and-place run of a robot arm. You get a photo from a camera "
    "fixed above the table, and sometimes one from a camera on the arm's gripper.\n"
    "The table: a dark grey mat in the middle, an open cardboard box on the left side of the overhead "
    "photo, and an orange robot arm at the bottom, folded at rest.\n"
    "The battery is a light wooden block about 5 cm long with a '+' and a '-' drawn on it. These objects "
    "are NOT the battery: a yellow rubber duck, a blue toy car, a pink cube with 'TNT' printed on it.\n"
    "Say where the battery is now:\n"
    "- in_box: inside the cardboard box\n"
    "- on_mat: anywhere on the dark mat\n"
    "- in_gripper: held in the robot's gripper\n"
    "- elsewhere: off the mat and not in the box (on the table, on the floor, on the edge of the box)\n"
    "- not_visible: you cannot see it in the photos\n"
    "Also list which of the other objects are inside the box, if any."
)

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "battery_location": {"type": "string", "enum": list(LOCATIONS)},
        "other_objects_in_box": {"type": "array", "items": {"type": "string", "enum": ["duck", "car", "tnt"]}},
    },
    "required": ["explanation", "battery_location", "other_objects_in_box"],
    "additionalProperties": False,
}


class CheckFailed(Exception):
    pass


def claude_available() -> bool:
    """True when the Anthropic SDK is installed and a credential is configured."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return (Path.home() / ".config" / "anthropic").is_dir()  # `ant auth login` profile


def ask_claude(scene_jpeg: bytes, wrist_jpeg: bytes | None, *, model: str, timeout: float) -> dict:
    """Claude's verdict as {'explanation', 'battery_location', 'other_objects_in_box'}."""
    import anthropic

    def image(data: bytes) -> dict:
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                            "data": base64.standard_b64encode(data).decode("ascii")}}

    content: list[dict] = [{"type": "text", "text": "Overhead camera:"}, image(scene_jpeg)]
    if wrist_jpeg:
        content += [{"type": "text", "text": "Gripper camera (the arm is folded at rest):"}, image(wrist_jpeg)]
    content.append({"type": "text", "text": "Where is the battery now?"})

    client = anthropic.Anthropic(timeout=timeout, max_retries=1)
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=4096,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=CHECK_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
        )
    except anthropic.AuthenticationError as e:
        raise CheckFailed("the Anthropic API key was refused") from e
    except anthropic.RateLimitError as e:
        raise CheckFailed("rate limited by the Anthropic API") from e
    except anthropic.APIStatusError as e:
        raise CheckFailed(f"Anthropic API error {e.status_code}") from e
    except anthropic.APITimeoutError as e:
        raise CheckFailed(f"no answer within {timeout:g} s") from e
    except anthropic.APIConnectionError as e:
        raise CheckFailed("no internet connection to the Anthropic API") from e
    if response.stop_reason in ("refusal", "max_tokens"):
        raise CheckFailed(f"no usable answer (stop reason: {response.stop_reason})")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        verdict = json.loads(text)
    except ValueError as e:
        raise CheckFailed("the answer was not valid JSON") from e
    if verdict.get("battery_location") not in LOCATIONS:
        raise CheckFailed(f"unexpected answer: {text[:120]}")
    return verdict


ENV_FILE = ROOT / ".env"  # git-ignored; keys stay on this computer
OPENAI_KEY_NAMES = ("OPENAI_API_KEY", "gpt_api_key")


def load_env_file(path: Path = ENV_FILE) -> None:
    """Put KEY=VALUE lines of the repository's .env into os.environ (never overriding a variable
    that is already set). The OpenAI key may be called OPENAI_API_KEY or gpt_api_key."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name and value and name not in os.environ:
            os.environ[name] = value
    if not os.environ.get("OPENAI_API_KEY"):
        for name in OPENAI_KEY_NAMES[1:]:
            if os.environ.get(name):
                os.environ["OPENAI_API_KEY"] = os.environ[name]
                break


def openai_available() -> bool:
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("OPENAI_API_KEY"))


def ask_openai(scene_jpeg: bytes, wrist_jpeg: bytes | None, *, model: str, timeout: float) -> dict:
    """Same question and answer format as ask_claude, through OpenAI's Chat Completions API."""
    import openai

    def image(data: bytes) -> dict:
        url = "data:image/jpeg;base64," + base64.standard_b64encode(data).decode("ascii")
        return {"type": "image_url", "image_url": {"url": url}}

    content: list[dict] = [{"type": "text", "text": "Overhead camera:"}, image(scene_jpeg)]
    if wrist_jpeg:
        content += [{"type": "text", "text": "Gripper camera (the arm is folded at rest):"}, image(wrist_jpeg)]
    content.append({"type": "text", "text": "Where is the battery now?"})
    request = dict(
        model=model,
        messages=[{"role": "system", "content": CHECK_PROMPT}, {"role": "user", "content": content}],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "battery_check", "strict": True, "schema": VERDICT_SCHEMA}},
        max_completion_tokens=4000,
    )
    if model.startswith(("gpt-5", "o")):
        request["reasoning_effort"] = "low"  # a quick look is enough; keeps the answer fast
    client = openai.OpenAI(timeout=timeout, max_retries=1)  # reads OPENAI_API_KEY
    try:
        response = client.chat.completions.create(**request)
    except openai.AuthenticationError as e:
        raise CheckFailed("the OpenAI API key was refused") from e
    except openai.RateLimitError as e:
        raise CheckFailed("rate limited or out of credit at OpenAI") from e
    except openai.APIStatusError as e:
        raise CheckFailed(f"OpenAI API error {e.status_code}") from e
    except openai.APITimeoutError as e:
        raise CheckFailed(f"no answer within {timeout:g} s") from e
    except openai.APIConnectionError as e:
        raise CheckFailed("no internet connection to the OpenAI API") from e
    choice = response.choices[0]
    if getattr(choice.message, "refusal", None):
        raise CheckFailed("the model refused to answer")
    if choice.finish_reason == "length":
        raise CheckFailed("the answer was cut off")
    text = choice.message.content or ""
    try:
        verdict = json.loads(text)
    except ValueError as e:
        raise CheckFailed("the answer was not valid JSON") from e
    if verdict.get("battery_location") not in LOCATIONS:
        raise CheckFailed(f"unexpected answer: {text[:120]}")
    return verdict


def local_available() -> bool:
    """True when our own vision model has been trained (sokit/vision.py) and torch is installed."""
    from . import vision

    return vision.available(os.environ.get("LOCAL_CHECK_MODEL") or None)


def ask_local(scene_jpeg: bytes, wrist_jpeg: bytes | None, *, model: str, timeout: float) -> dict:
    """Same answer format as ask_claude, from our own vision model: offline, no API key."""
    from . import vision

    try:
        return vision.verdict(scene_jpeg, model_path=model)
    except Exception as e:  # noqa: BLE001
        # `python -m sokit.demo` runs this file as __main__ while vision imports sokit.demo: two copies of
        # CheckFailed exist. Hand back our own copy so run_once() catches it and falls back to the gripper.
        if type(e).__name__ == "CheckFailed":
            raise CheckFailed(str(e)) from e
        raise


def default_model(provider: str | None) -> str:
    """The check's model: CLAUDE_/OPENAI_/LOCAL_CHECK_MODEL from the environment or .env, else the default."""
    name = MODEL_ENV.get(provider or "")
    return (os.environ.get(name, "").strip() if name else "") or DEFAULT_MODELS.get(provider or "", "")


def pick_provider(check: str) -> str | None:
    """'claude', 'openai', 'local' or None (gripper only) for --check auto|claude|openai|local|grip.

    With auto, RETRY_CHECK from the environment or .env decides when it is set; otherwise
    Claude if its key is set, else OpenAI if its key is set, else the gripper only."""
    if check == "auto":
        wanted = os.environ.get("RETRY_CHECK", "").strip().lower()
        if wanted and wanted not in CHECK_NAMES:
            raise SystemExit(f"[demo] RETRY_CHECK={wanted} in .env is not one of: local, openai, claude, grip, auto")
        check = CHECK_NAMES.get(wanted, "auto")
    if check == "local" and not local_available():
        raise SystemExit("[demo] The local camera check needs a trained model: run  so vision prepare  and  "
                         "so vision train  (or set LOCAL_CHECK_MODEL in .env to a model file).")
    if check == "auto":
        check = "claude" if claude_available() else "openai" if openai_available() else "grip"
    if check == "claude" and not claude_available():
        raise SystemExit("[demo] --check claude needs the Anthropic SDK and ANTHROPIC_API_KEY.")
    if check == "openai" and not openai_available():
        raise SystemExit("[demo] --check openai needs the OpenAI SDK and an OpenAI key "
                         "(OPENAI_API_KEY, or gpt_api_key in the repository's .env).")
    return None if check == "grip" else check


def jpeg(frame, quality: int = 85) -> bytes:
    """RGB frame (H x W x 3, uint8, as LeRobot cameras deliver it) -> JPEG bytes."""
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


# ----------------------------------------------------------------------------- the session
@dataclass
class Run:
    number: int
    seconds: float
    ended_by: str
    check: Check
    success: bool
    retry: bool
    reason: str


@dataclass
class Attempt:
    number: int
    runs: list[Run] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def success(self) -> bool:
        return bool(self.runs) and self.runs[-1].success


def _log_attempt(label: str, attempt: Attempt) -> None:
    DEMO_LOG.parent.mkdir(exist_ok=True)
    new = not DEMO_LOG.exists()
    with open(DEMO_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time", "policy", "attempt", "success", "runs", "rescued_by_retry", "seconds", "details"])
        now = dt.datetime.now()
        details = "; ".join(
            f"run {r.number}: {r.seconds:.0f} s ({r.ended_by}), grip {r.check.grip}, "
            f"camera {r.check.location or r.check.error or 'n/a'} -> {r.reason}" for r in attempt.runs
        )
        w.writerow([f"{now:%Y-%m-%d}", f"{now:%H:%M:%S}", label, attempt.number, int(attempt.success),
                    len(attempt.runs), int(attempt.success and len(attempt.runs) > 1), f"{attempt.seconds:.1f}", details])


class Demo:
    def __init__(self, controller, ctx, events: queue.Queue, ev, shutdown, opts):
        self.controller, self.ctx, self.events, self.ev, self.shutdown, self.opts = (
            controller, ctx, events, ev, shutdown, opts)
        self.robot = ctx.hardware.robot_wrapper
        self.home = dict(ctx.hardware.initial_position or {})
        cams = list(self.robot.cameras)
        self.scene_cam = opts.scene_camera or next((c for c in cams if camera_role(c) == "scene"), cams[0] if cams else None)
        self.wrist_cam = opts.wrist_camera or next((c for c in cams if camera_role(c) == "wrist"), None)
        self.provider = None if opts.manual else pick_provider(opts.check)
        self.model = opts.model or default_model(self.provider)
        self.model_label = "our vision model" if self.provider == "local" else self.model  # a file path reads badly
        if self.provider == "local":  # load our model now, so the first check is as quick as the others
            try:
                from . import vision

                vision.LocalChecker.load(self.model)
            except Exception as e:  # noqa: BLE001 - each check reports the problem again and falls back
                print(f"[demo] our vision model did not load: {e}", flush=True)
        self.frames = FRAMES_DIR / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.failures = {ev.ENGINE_FAILED, ev.STRATEGY_FAILED, ev.STOPPED}
        self._lines: queue.Queue = queue.Queue()
        self.video: TestVideo | None = None  # set by _session with --record-video

    def _status(self, text: str) -> None:
        """What the test video shows across the top (no-op without --record-video)."""
        video = getattr(self, "video", None)
        if video is not None:
            video.status = text

    # -- small helpers --------------------------------------------------------
    def _read_stdin(self) -> None:
        for line in sys.stdin:
            self._lines.put(line)
        self._lines.put(None)

    def ask(self, prompt: str) -> str | None:
        print(prompt, flush=True)
        while not self.shutdown.is_set():
            try:
                return self._lines.get(timeout=0.2)
            except queue.Empty:
                continue
        return None

    def _drain(self) -> None:
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                return

    def _next_event(self, timeout: float):
        try:
            event = self.events.get(timeout=timeout)
        except queue.Empty:
            return None
        if event in self.failures:
            reason = self.controller.failure_traceback or f"rollout {event.value}"
            raise RuntimeError(f"the rollout stopped: {reason}")
        return event

    def _wait_for(self, wanted: set, timeout: float):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.shutdown.is_set():
                raise KeyboardInterrupt
            event = self._next_event(0.1)
            if event in wanted:
                return event
        raise RuntimeError(f"timed out after {timeout:g} s waiting for {sorted(e.value for e in wanted)}")

    def _operator_pressed_enter(self) -> bool:
        try:
            return self._lines.get_nowait() is not None
        except queue.Empty:
            return False

    # -- one run of the policy ------------------------------------------------
    def _run_policy(self) -> tuple[float, str, str]:
        """Run the policy once and bring the arm back to its start pose.

        Returns (seconds, why the run ended, gripper reading). Enter typed during the run stops it.
        """
        ev = self.ev
        self._drain()
        while self._operator_pressed_enter():  # an Enter typed before the run must not stop it
            pass
        if not self.controller.start():
            raise RuntimeError("the policy could not be started (see the messages above)")
        self._wait_for({ev.SEGMENT_STARTED}, timeout=15)
        watch = MotionWatch(self.home)
        grip: list[tuple[float, float | None]] = []
        t0 = time.monotonic()
        ended_by = "time limit"
        while True:
            if self.shutdown.is_set():
                raise KeyboardInterrupt
            if self._next_event(0.05) == ev.SEGMENT_ENDED:
                break
            if self._operator_pressed_enter():
                ended_by = "stopped by you"
                break
            # The control loop refreshes these positions on every tick; reading them needs no
            # extra access to the hardware (LeRobot 0.7.0 ThreadSafeRobot internals).
            positions = dict(getattr(self.robot, "_observed_positions", None) or {})
            if positions:
                t = time.monotonic() - t0
                grip.append((t, positions.get("gripper.pos")))
                if watch.feed(t, positions):
                    ended_by = "arm back at rest"
                    break
        seconds = time.monotonic() - t0
        self.controller.reset()  # stop, return smoothly to the start pose, stay ready
        done = self._wait_for({ev.RESET_DONE, ev.RESET_SKIPPED, ev.RESET_FAILED}, timeout=30)
        if done == ev.RESET_FAILED:
            raise RuntimeError("the arm could not return to its start pose")
        return seconds, ended_by, grip_verdict(grip)

    def run_once(self, attempt: int, number: int) -> Run:
        seconds, ended_by, grip = self._run_policy()
        check = Check(grip=grip)
        observation = self.robot.get_observation()  # the arm is still now: nothing else reads the hardware
        scene = observation.get(self.scene_cam) if self.scene_cam else None
        wrist = observation.get(self.wrist_cam) if self.wrist_cam else None
        self.frames.mkdir(parents=True, exist_ok=True)
        scene_jpeg = jpeg(scene) if scene is not None else None
        wrist_jpeg = jpeg(wrist) if wrist is not None else None
        for cam, data in ((self.scene_cam, scene_jpeg), (self.wrist_cam, wrist_jpeg)):
            if data:
                (self.frames / f"attempt{attempt:02d}_run{number}_{cam}.jpg").write_bytes(data)
        if self.provider and scene_jpeg:
            ask = {"claude": ask_claude, "openai": ask_openai, "local": ask_local}[self.provider]
            try:
                verdict = ask(scene_jpeg, wrist_jpeg, model=self.model, timeout=self.opts.check_timeout)
                check.location = verdict["battery_location"]
                check.explanation = verdict.get("explanation", "")
                others = verdict.get("other_objects_in_box") or []
                if others:
                    check.explanation += f" (also in the box: {', '.join(others)})"
            except CheckFailed as e:
                check.error = str(e)
            except Exception as e:  # noqa: BLE001 - a broken check must never end the demo: fall back to the gripper
                check.error = f"camera check failed: {type(e).__name__}: {e}"[:200]
        success, retry, reason = decide(check)
        return Run(number, seconds, ended_by, check, success, retry, reason)

    # -- one demo attempt -------------------------------------------------------
    def attempt(self, number: int) -> Attempt:
        result = Attempt(number)
        t0 = time.monotonic()
        for run_no in range(1, self.opts.tries + 1):
            self._status(f"Attempt {number}  run {run_no}/{self.opts.tries}: arm running")
            run = self.run_once(number, run_no)
            result.runs.append(run)
            self._status(f"Attempt {number}  run {run_no}: {'SUCCESS' if run.success else 'not done'} - {run.reason}")
            camera = (f"camera: {run.check.location.replace('_', ' ')}" if run.check.location
                      else f"camera: {run.check.error or 'not used'}")
            print(f"[demo]   run {run_no}: {run.seconds:.1f} s ({run.ended_by}) | grip: {run.check.grip} | {camera}"
                  f"\n[demo]   -> {'SUCCESS' if run.success else 'not done'}: {run.reason}", flush=True)
            if run.check.explanation:
                print(f"[demo]      {self.model_label}: {run.check.explanation}", flush=True)
            if run.success or not run.retry:
                break
            if run_no < self.opts.tries:
                print("[demo]   running the policy again from the start pose...", flush=True)
        result.seconds = time.monotonic() - t0
        _log_attempt(self.opts.label, result)
        return result

    def loop(self) -> list[Attempt]:
        threading.Thread(target=self._read_stdin, name="demo-stdin", daemon=True).start()
        check = (f"{self.model_label} looks at camera '{self.scene_cam}' + gripper position" if self.provider
                 else "gripper position only (no API key found: the box is not checked)")
        print(f"\n[demo] Policy: {self.opts.label}\n[demo] Up to {self.opts.tries} runs per attempt. Check: {check}\n"
              f"[demo] Ctrl+C stops the arm and ends the session.", flush=True)
        if not MotionWatch(self.home).usable:
            print("[demo] No start pose captured: each run lasts the full time limit.", flush=True)
        attempts: list[Attempt] = []
        while self.opts.attempts == 0 or len(attempts) < self.opts.attempts:
            n = len(attempts) + 1
            ok_so_far = sum(a.success for a in attempts)
            self._status(f"Attempt {n}: setting up   ({ok_so_far}/{len(attempts)} so far)")
            line = self.ask(f"\n[demo] Attempt {n}: put the battery on its place, then press Enter (q + Enter = finish)")
            if line is None or line.strip().lower() in ("q", "quit", "exit"):
                break
            result = self.attempt(n)
            attempts.append(result)
            self._status(f"Attempt {n}: {'SUCCESS' if result.success else 'FAILED'} in {len(result.runs)} run(s)")
            print(f"[demo] Attempt {n}: {'SUCCESS' if result.success else 'FAILED'} in {result.seconds:.0f} s"
                  f" ({len(result.runs)} run{'s' if len(result.runs) > 1 else ''})", flush=True)
        if attempts:
            ok = sum(a.success for a in attempts)
            rescued = sum(a.success and len(a.runs) > 1 for a in attempts)
            print(f"\n[demo] {ok}/{len(attempts)} attempts succeeded, {rescued} of them thanks to a retry. "
                  f"Logged in {DEMO_LOG.relative_to(ROOT)}; frames in {self.frames.relative_to(ROOT)}", flush=True)
        return attempts

    # -- manual mode (`so try`): you judge every run --------------------------------
    def manual_loop(self, read_stdin: bool = True) -> None:
        """No checks, no retries: run, then you type s or f with a note. Logged in journal/eval.csv,
        the same log `so eval` writes, so `so eval --summary` compares models and lists failures."""
        from . import evallog

        if read_stdin:
            threading.Thread(target=self._read_stdin, name="try-stdin", daemon=True).start()
        print(f"\n[try] Policy: {self.opts.label}\n"
              "[try] Each attempt: set up the scene, press Enter, watch. Press Enter during a run to stop the arm.\n"
              "[try] After each run type  s  (success) or  f  (fail), optionally with a note, e.g.  f missed grip place 3\n"
              "[try]   x = do not log this run, q = finish. Ctrl+C stops everything.", flush=True)
        results: list[tuple[str, str]] = []
        while True:
            self._status(f"Trial {len(results) + 1}: setting up")
            line = self.ask(f"\n[try] Attempt {len(results) + 1}: set up the scene, then press Enter (q = finish)")
            if line is None or line.strip().lower() in ("q", "quit", "exit"):
                break
            self._status(f"Trial {len(results) + 1}: arm running")
            seconds, ended_by, grip = self._run_policy()
            self._status(f"Trial {len(results) + 1}: waiting for your verdict")
            print(f"[try]   {seconds:.1f} s ({ended_by}), gripper: {GRIP_WORDS.get(grip, grip)}. "
                  "The arm is back at its start pose.", flush=True)
            while True:
                answer = self.ask("[try]   Result? s = success, f = fail (+ note), x = do not log")
                if answer is None:
                    break
                key, _, note = answer.strip().partition(" ")
                key = key.lower()
                if key in ("s", "f"):
                    info = f"{seconds:.0f} s, {ended_by}, gripper {grip}"
                    evallog.add(self.opts.label, key, f"{note.strip()} [{info}]" if note.strip() else f"[{info}]")
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
            fails = [note or "(no note)" for k, note in results if k == "f"]
            if fails:
                print("[try] Failures:\n" + "\n".join(f"[try]   - {n}" for n in fails), flush=True)
            print("[try] All sessions and models: so eval --summary", flush=True)


GRIP_WORDS = {"held": "closed on something", "missed": "closed on nothing",
              "never_opened": "never opened", "unknown": "unclear"}


class TestVideo:
    """Films the whole session (`--record-video`) from the cameras the policy already uses, side by side,
    with the attempt, the run and each verdict written across the top. One H.264 file per session.

    Frames come from `read_latest()`, which peeks at the newest frame without taking it away from the
    control loop (LeRobot 0.7.0 OpenCVCamera), so recording never slows the arm down."""

    FPS = 15
    TILE = (640, 480)
    BANNER = 44

    def __init__(self, cameras: dict, names: list[str], path: Path, fps: int = FPS):
        self.cameras, self.names, self.path, self.fps = cameras, [n for n in names if n], path, fps
        self.status = "starting"
        self.frames = 0
        self.error = ""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="test-video", daemon=True)

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread.start()

    def stop(self) -> Path | None:
        self._stop.set()
        self._thread.join(timeout=15)
        return self.path if self.frames and self.path.is_file() else None

    def _grab(self, name: str):
        try:
            return self.cameras[name].read_latest(max_age_ms=1000)
        except Exception:  # noqa: BLE001 - a missing frame repeats the last one
            return None

    def _loop(self) -> None:
        from fractions import Fraction

        try:
            import av
            import cv2
            import numpy as np

            w, h = self.TILE
            width, height = w * max(1, len(self.names)), h + self.BANNER
            container = av.open(str(self.path), "w")
            stream = container.add_stream("libx264", rate=self.fps)
            stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
            stream.options = {"preset": "veryfast", "crf": "23"}
            last: dict = {}
            t0 = time.monotonic()
            last_pts = -1
            while not self._stop.is_set():
                for name in self.names:
                    frame = self._grab(name)
                    if frame is not None:
                        last[name] = frame
                canvas = np.full((height, width, 3), 24, dtype=np.uint8)
                for i, name in enumerate(self.names):
                    if name in last:
                        canvas[self.BANNER:, i * w:(i + 1) * w] = cv2.resize(last[name], (w, h))
                elapsed = time.monotonic() - t0
                text = f"CrimsonSnow  {int(elapsed // 60):02d}:{int(elapsed % 60):02d}   {self.status}"
                cv2.putText(canvas, text.encode("ascii", "replace").decode(), (14, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
                pts = max(last_pts + 1, round(elapsed * self.fps))  # real time, even if a frame was late
                video_frame = av.VideoFrame.from_ndarray(canvas, format="rgb24")
                video_frame.pts, video_frame.time_base = pts, Fraction(1, self.fps)
                for packet in stream.encode(video_frame):
                    container.mux(packet)
                last_pts = pts
                self.frames += 1
                self._stop.wait(max(0.0, (pts + 1) / self.fps - (time.monotonic() - t0)))
            for packet in stream.encode():
                container.mux(packet)
            container.close()
        except Exception as e:  # noqa: BLE001 - the demo goes on without a video
            self.error = str(e)
            print(f"[demo] the video recording stopped: {e}", flush=True)


def _session(cfg, opts) -> int:
    from lerobot.rollout import LinkedEvent, RolloutController, RolloutEvent, build_rollout_context, create_strategy
    from lerobot.utils import init_logging
    from lerobot.utils.process import ProcessSignalHandler

    init_logging(console_level=cfg.inference.log_level)
    handler = ProcessSignalHandler(use_threads=True, display_pid=False)
    shutdown = handler.shutdown_event
    ctx = build_rollout_context(cfg, LinkedEvent(shutdown))  # loads the policy, connects arm + cameras
    strategy = create_strategy(cfg.strategy)
    events: queue.Queue = queue.Queue()
    controller = None
    try:
        strategy.setup(ctx)
        controller = RolloutController(strategy, ctx, on_event=lambda event, _payload: events.put(event))
        serve = threading.Thread(target=controller.serve, name="rollout-serve", daemon=True)
        serve.start()
        video = None
        try:
            session = Demo(controller, ctx, events, RolloutEvent, shutdown, opts)
            if getattr(opts, "record_video", False):
                video = TestVideo(session.robot.cameras, [session.scene_cam, session.wrist_cam],
                                  session.frames / "test.mp4")
                session.video = video
                video.start()
                print(f"[demo] Recording the whole test on video: {session.frames.relative_to(ROOT).as_posix()}/test.mp4",
                      flush=True)
            session.manual_loop() if opts.manual else session.loop()
        except KeyboardInterrupt:
            print("\n[demo] stopping", flush=True)
        finally:
            controller.stop()
            serve.join(timeout=60)
            if video is not None:
                saved = video.stop()
                if saved:
                    print(f"[demo] Video saved: {saved.relative_to(ROOT).as_posix()} "
                          f"({video.frames / video.fps:.0f} s)", flush=True)
    finally:
        strategy.teardown(ctx)  # returns to the start pose, then releases the motors
    return 1 if controller is None or controller.failed else 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m sokit.demo", description=__doc__.split("\n\n")[0],
                                epilog="Everything after -- goes to LeRobot's rollout unchanged.")
    p.add_argument("--manual", action="store_true",
                   help="no checks and no retries: after each run you type s or f (logged in journal/eval.csv)")
    p.add_argument("--tries", type=int, default=3, help="policy runs per attempt at most (default 3)")
    p.add_argument("--attempts", type=int, default=5, help="attempts in this session; 0 = until q (default 5)")
    p.add_argument("--check", choices=["auto", "claude", "openai", "local", "grip"], default="auto",
                   help="auto = RETRY_CHECK from .env if set (local | openai | claude | grip), else Claude if "
                        "ANTHROPIC_API_KEY is set, else OpenAI if an OpenAI key is set, else the gripper "
                        "position only; local = our own vision model (so vision train)")
    p.add_argument("--model", help="model for the camera check (default: "
                                   + ", ".join(f"{k} {v}" for k, v in DEFAULT_MODELS.items()) + ")")
    p.add_argument("--check-timeout", type=float, default=30.0, help="seconds to wait for the camera check")
    p.add_argument("--scene-camera", help="camera that sees the whole table (default: by name, e.g. top)")
    p.add_argument("--wrist-camera", help="camera on the gripper (default: by name, e.g. wrist)")
    p.add_argument("--label", default="policy", help="name for the log")
    p.add_argument("--record-video", action="store_true",
                   help="film the whole session (overhead + wrist camera, status on top) to outputs/demo/<session>/test.mp4")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # a model name with a symbol must not crash a cp1252 console
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    ours, flags = (argv[: argv.index("--")], argv[argv.index("--") + 1 :]) if "--" in argv else (argv, [])
    opts = build_arg_parser().parse_args(ours)
    load_env_file()  # API keys from the repository's git-ignored .env
    if opts.tries < 1:
        raise SystemExit("--tries must be at least 1")
    given = {f.split("=", 1)[0] for f in flags}
    defaults = {"--strategy.type": "base", "--interactive": "true", "--play_sounds": "false"}
    flags = flags + [f"{k}={v}" for k, v in defaults.items() if k not in given]
    if "--duration" not in given:
        flags.append("--duration=40")  # per run; normally a run ends earlier, when the arm is back at rest

    # Same imports as lerobot-rollout: they register the robot, camera and teleop types.
    from lerobot.configs import parser
    from lerobot.rollout import RolloutConfig
    from lerobot.scripts import lerobot_rollout  # noqa: F401
    from lerobot.utils import register_third_party_plugins

    register_third_party_plugins()

    @parser.wrap()
    def _run(cfg: RolloutConfig):
        if cfg.strategy.type != "base":
            raise SystemExit("[demo] automatic retries use the base strategy (no recording)")
        return _session(cfg, opts)

    sys.argv = ["lerobot-rollout", *flags]
    return int(_run() or 0)


if __name__ == "__main__":
    sys.exit(main())
