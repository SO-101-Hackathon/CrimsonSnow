"""Run lerobot commands: show them, journal them, keep the laptop awake while they run."""

from __future__ import annotations

import ctypes
import datetime as dt
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import JOURNAL_DIR, ROOT

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
JOURNAL = JOURNAL_DIR / "commands.md"


def is_wsl() -> bool:
    """True inside Windows Subsystem for Linux (a Linux kernel built by Microsoft)."""
    if not IS_LINUX:
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False


def exe(name: str) -> str:
    """Absolute path of a console script that lives next to the running interpreter."""
    here = Path(sys.executable).parent
    for cand in (here / "Scripts" / f"{name}.exe", here / f"{name}.exe", here / name, here / "bin" / name):
        if cand.is_file():
            return str(cand)
    found = shutil.which(name)
    if found:
        return found
    how = "or run via .\\so.ps1" if IS_WINDOWS else "then run ./so from this folder"
    raise SystemExit(f"`{name}` not found. Activate the environment first (conda activate lerobot) {how}")


def ensure_env_on_path() -> None:
    """Make this Python environment's tools and DLLs visible to us and to child processes.

    `conda activate` normally does this. Doing it here as well means `so.exe` works even when
    it is started without activating the environment first (ffmpeg DLLs for torchcodec live in
    Library\\bin, the lerobot-* launchers in Scripts).
    """
    if not IS_WINDOWS:
        return
    prefix = Path(sys.prefix)
    wanted = [prefix, prefix / "Library" / "mingw-w64" / "bin", prefix / "Library" / "usr" / "bin",
              prefix / "Library" / "bin", prefix / "Scripts", prefix / "bin"]
    current = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    have = {p.lower().rstrip("\\/") for p in current}
    missing = [str(p) for p in wanted if p.is_dir() and str(p).lower().rstrip("\\/") not in have]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing + current)
    os.environ.setdefault("CONDA_PREFIX", str(prefix))


def shell_style() -> str:
    """Which shell launched us: decides how printed commands are quoted and continued."""
    if not IS_WINDOWS:
        return "bash"
    try:
        import psutil

        proc = psutil.Process(os.getppid())
        for _ in range(4):  # so.exe -> python.exe -> shell, depending on the launcher
            name = proc.name().lower()
            if name in ("powershell.exe", "pwsh.exe"):
                return "powershell"
            if name == "cmd.exe":
                return "cmd"
            if name in ("bash.exe", "sh.exe", "zsh.exe"):
                return "bash"
            proc = proc.parent()
            if proc is None:
                break
    except Exception:  # noqa: BLE001 - cosmetic only
        pass
    return "powershell"


def _ps_quote(arg: str) -> str:
    if arg and all(c.isalnum() or c in "-_./=:\\+,@%" for c in arg):
        return arg
    return "'" + arg.replace("'", "''") + "'"


def _cmd_quote(arg: str) -> str:
    if arg and all(c.isalnum() or c in "-_./=:\\+,@{}[]~" for c in arg):
        return arg
    return '"' + arg.replace('"', '\\"') + '"'


def format_cmd(argv: list[str], style: str | None = None) -> str:
    """Copy-pasteable multi-line command in the syntax of the shell you are using."""
    style = style or shell_style()
    head = Path(argv[0]).name
    if head.lower().endswith(".exe"):
        head = head[:-4]
    if style == "powershell":
        parts, cont = [head] + [_ps_quote(a) for a in argv[1:]], " `\n  "
    elif style == "cmd":
        parts, cont = [head] + [_cmd_quote(a) for a in argv[1:]], " ^\n  "
    else:
        parts, cont = [head] + [shlex.quote(a) for a in argv[1:]], " \\\n  "
    return cont.join(parts)


def keep_awake_command() -> list[str] | None:
    """The helper process that blocks idle sleep on this system, or None when there is none.

    macOS ships `caffeinate`; Linux desktops have `systemd-inhibit`. Inside WSL the Windows
    host decides about sleep, so nothing can be done from here.
    """
    if IS_MAC and shutil.which("caffeinate"):
        return ["caffeinate", "-i", "-w", str(os.getpid())]
    if IS_LINUX and not is_wsl() and shutil.which("systemd-inhibit"):
        return ["systemd-inhibit", "--what=idle:sleep", "--who=so", "--why=robot recording or training",
                "sleep", "infinity"]
    return None


class KeepAwake:
    """Stop the computer from idle-sleeping during long runs (does not override closing the lid).

    Windows: SetThreadExecutionState. macOS and Linux: a helper process (`keep_awake_command`).
    If the helper is missing or refused, the run carries on without it.
    """

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    _helper: subprocess.Popen | None = None

    def __enter__(self):
        if IS_WINDOWS:
            ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED)
            return self
        cmd = keep_awake_command()
        if cmd:
            try:
                self._helper = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self._helper = None
        return self

    def __exit__(self, *exc):
        if IS_WINDOWS:
            ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
        elif self._helper is not None:
            self._helper.terminate()
            self._helper = None
        return False


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else (f"{m}m{s:02d}s" if m else f"{s}s")


def _journal(text: str) -> None:
    JOURNAL_DIR.mkdir(exist_ok=True)
    new = not JOURNAL.exists()
    with open(JOURNAL, "a", encoding="utf-8") as f:
        if new:
            f.write(
                "# Command journal\n\n"
                "Every hardware / training command run through `so`, in order. This is the raw\n"
                "material for the README's reproduction steps and for the jury's questions.\n"
            )
        f.write(text)


def child_env(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")  # lerobot prints arrows/dots; never crash on a cp1252 pipe
    env.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if extra:
        env.update(extra)
    return env


def run(
    argv: list[str],
    *,
    label: str,
    shown: list[str] | None = None,
    dry_run: bool = False,
    journal: bool = True,
    keep_awake: bool = False,
    env: dict | None = None,
    cwd: Path | None = None,
) -> int:
    """Run argv. `shown` is the canonical command to print and journal when it differs from
    what is executed (e.g. a lerobot script routed through the sokit.lr launcher)."""
    pretty = format_cmd(shown or argv)
    print("\n" + pretty + "\n")
    if dry_run:
        return 0
    started = dt.datetime.now()
    if journal:
        # The journal is for the README / other people: always bash syntax, like the LeRobot docs.
        _journal(f"\n## {started:%Y-%m-%d %H:%M:%S}  {label}\n\n```bash\n{format_cmd(shown or argv, 'bash')}\n```\n")
    t0 = time.time()
    ctx = KeepAwake() if keep_awake else None
    if ctx:
        ctx.__enter__()
    try:
        proc = subprocess.Popen(argv, env=child_env(env), cwd=str(cwd or ROOT))
        interrupts = 0
        while True:
            try:
                code = proc.wait()
                break
            except KeyboardInterrupt:
                # The console already delivered Ctrl+C to lerobot; let it save and clean up.
                interrupts += 1
                if interrupts == 1:
                    print("\n[so] Ctrl+C -> waiting for lerobot to finish cleanly (again to force quit)")
                elif interrupts >= 3:
                    proc.kill()
    finally:
        if ctx:
            ctx.__exit__(None, None, None)
    took = _fmt_duration(time.time() - t0)
    if journal:
        _journal(f"\nexit code {code} after {took}\n")
    if code != 0:
        print(f"\n[so] {label} exited with code {code} after {took}")
    return code
