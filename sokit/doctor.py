"""`so doctor`: one screen that says whether this laptop is ready, and how to fix what is not."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from . import calib, ports, winlinks
from . import config as C
from . import runner as R

MIN_DRIVER = (580, 65)
WANT_LEROBOT = "0.7.0"
_results: list[str] = []


def _line(level: str, what: str, detail: str = "", fix: str = "") -> None:
    tag = {"ok": "[ OK ]", "warn": "[WARN]", "fail": "[FAIL]", "info": "[info]"}[level]
    print(f"{tag} {what}" + (f": {detail}" if detail else ""))
    if fix and level in ("warn", "fail"):
        print(f"         fix: {fix}")
    _results.append(level)


def _check_python() -> None:
    v = sys.version_info
    env = os.environ.get("CONDA_DEFAULT_ENV") or os.path.basename(sys.prefix)
    ok = v >= (3, 12)
    _line("ok" if ok else "fail", "Python", f"{v.major}.{v.minor}.{v.micro} (env: {env})",
          "use the lerobot conda env: conda activate lerobot")


def _check_lerobot() -> None:
    try:
        from importlib.metadata import version

        got = version("lerobot")
    except Exception as exc:  # noqa: BLE001
        _line("fail", "LeRobot", f"not importable ({exc})", "pip install 'lerobot[core_scripts,training,feetech]==0.7.0'")
        return
    _line("ok" if got == WANT_LEROBOT else "warn", "LeRobot", got,
          f"the hackathon guide is written for {WANT_LEROBOT}")


def _check_gpu() -> None:
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        _line("fail", "PyTorch", str(exc))
        return
    if not torch.cuda.is_available():
        elsewhere = "train on an NVIDIA computer, in Colab, or with `so train --cloud a10g-small`"
        if R.IS_MAC:
            mps = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
            _line("warn", "GPU", f"torch {torch.__version__}, " + ("Apple GPU (mps)" if mps else "CPU only"),
                  f"calibrating, recording and running a policy work here; training is slow: {elsewhere}")
        elif R.IS_WINDOWS:
            _line("fail", "GPU", f"torch {torch.__version__} cannot use CUDA",
                  "Windows needs the CUDA wheel: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu132")
        elif R.is_wsl():
            _line("fail", "GPU", f"torch {torch.__version__} cannot use CUDA",
                  "WSL uses the Windows NVIDIA driver: update it in Windows, then `nvidia-smi` must work inside WSL")
        else:
            _line("fail", "GPU", f"torch {torch.__version__} cannot use CUDA",
                  f"install the NVIDIA driver (`nvidia-smi` must work). No NVIDIA card: {elsewhere}")
        return
    name = torch.cuda.get_device_name(0)
    total = torch.cuda.get_device_properties(0).total_memory / 2**30
    _line("ok", "GPU", f"{name}, {total:.1f} GB, torch {torch.__version__} (CUDA {torch.version.cuda})")
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.run([smi, "--query-gpu=driver_version", "--format=csv,noheader"],
                                 capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
            parts = tuple(int(x) for x in out.split(".")[:2])
            _line("ok" if parts >= MIN_DRIVER else "fail", "NVIDIA driver", out,
                  "LeRobot needs driver 580.65 or newer: update via NVIDIA app / GeForce Experience")
        except Exception:  # noqa: BLE001
            _line("info", "NVIDIA driver", "could not query nvidia-smi")
    try:
        import psutil

        batt = psutil.sensors_battery()
        if batt is not None and not batt.power_plugged:
            _line("warn", "Power", f"on battery ({batt.percent:.0f}%)", "plug in: the GPU is heavily throttled on battery")
        elif batt is not None:
            _line("ok", "Power", "plugged in")
    except Exception:  # noqa: BLE001
        pass


def _check_ffmpeg() -> None:
    exe = shutil.which("ffmpeg")
    if not exe:
        _line("fail", "ffmpeg", "not on PATH", "conda install ffmpeg -c conda-forge (inside the lerobot env)")
        return
    enc = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    ver = subprocess.run([exe, "-hide_banner", "-version"], capture_output=True, text=True).stdout.split("\n")[0]
    has = "libsvtav1" in enc
    _line("ok" if has else "fail", "ffmpeg", ver.replace("ffmpeg version ", "").split(" Copyright")[0]
          + (" with libsvtav1" if has else " WITHOUT libsvtav1"), "conda install ffmpeg=7.1.1 -c conda-forge")
    try:
        import torchcodec  # noqa: F401
        from torchcodec.decoders import VideoDecoder  # noqa: F401

        _line("ok", "torchcodec", torchcodec.__version__)
    except Exception as exc:  # noqa: BLE001
        _line("warn", "torchcodec", f"{type(exc).__name__}: {str(exc)[:120]}",
              "LeRobot falls back to pyav (slower); check that ffmpeg comes from the conda env")


def _check_serial_access() -> None:
    """Linux only: the arms' serial ports belong to a group the user must be in."""
    if not R.IS_LINUX:
        return
    try:
        import grp

        need = next((g for g in ("dialout", "uucp") if any(x.gr_name == g for x in grp.getgrall())), None)
        mine = {grp.getgrgid(g).gr_name for g in os.getgroups()}
    except Exception:  # noqa: BLE001 - informative only
        return
    if os.geteuid() == 0 or need is None or need in mine:
        _line("ok", "Serial port access", f"user is in group '{need}'" if need in mine else "no group needed")
    else:
        _line("warn", "Serial port access", f"user is not in group '{need}': the arms' ports will be refused",
              f"sudo usermod -aG {need} $USER   then log out and in again (WSL: `wsl --shutdown`, reopen)")
    if R.is_wsl():
        _line("info", "WSL", "USB devices reach WSL only after `usbipd attach --wsl --busid <id>` in Windows "
              "(arms and cameras). See docs/SETUP.md")


def _check_symlinks() -> None:
    if not R.IS_WINDOWS:
        return  # symlinks always work here
    if winlinks.can_symlink():
        _line("ok", "Symlinks", "allowed (lerobot-train can write checkpoints/last)")
    else:
        script = C.ROOT / "admin-setup.ps1"
        _line("warn", "Symlinks", "not allowed for this account; `so train` uses a junction fallback, "
              "but plain `lerobot-train` will crash at its first checkpoint",
              f'powershell -ExecutionPolicy Bypass -File "{script}"   (turns on Windows Developer Mode; '
              "accept the admin prompt. Right-click > Run with PowerShell does NOT work)")


def _check_hf(cfg, state) -> None:
    user = C.hf_user(cfg, state)
    if user:
        _line("ok", "Hugging Face login", user)
    else:
        _line("warn", "Hugging Face login", "not logged in (recording/training still work, nothing is uploaded)",
              "hf auth login   with a WRITE token from https://huggingface.co/settings/tokens")


def _check_disk() -> None:
    for label, path in (("datasets/cache", C.lerobot_home()), ("outputs", C.ROOT)):
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        free = shutil.disk_usage(probe).free / 2**30
        _line("ok" if free >= 30 else "warn", f"Disk ({label})", f"{free:.0f} GB free at {probe}",
              "datasets store video for every episode: keep a few tens of GB free")


def _check_ports(cfg, state) -> None:
    present = ports.list_ports()
    arms = state.get("arms") or {}
    if not present:
        _line("info", "Arms", "no USB serial port present (arms not plugged in)")
        return
    for p in present:
        print(f"         {p.label()}")
    for role, key in (("follower", "robot"), ("leader", "teleop")):
        try:
            dev = ports.resolve(role, cfg[key].get("port", "auto"), state)
            _line("ok", f"{role} port", dev)
        except SystemExit as exc:
            first = str(exc).splitlines()[0]
            _line("warn", f"{role} port", first, "so ports assign" if role not in arms else "check cable/power")


def _check_calibration(cfg) -> None:
    print("Calibration:")
    status = calib.status(cfg)
    for role, ok in status.items():
        _line("ok" if ok else "info", f"{role} calibration", "present" if ok else "not calibrated yet")


def _check_cameras(cfg) -> None:
    try:
        from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
    except Exception as exc:  # noqa: BLE001
        _line("fail", "Cameras", f"cannot import lerobot cameras: {exc}")
        return
    try:
        found = OpenCVCamera.find_cameras()
    except Exception as exc:  # noqa: BLE001
        found = []
        _line("warn", "Camera scan", str(exc)[:160])
    ids = sorted(c.get("id") for c in found)
    _line("info", "Cameras detected", f"indices {ids}" if ids else "none")
    mine = sorted(C.local_overrides().get("cameras", {}))
    if mine:
        _line("info", "Camera numbers", f"{', '.join(mine)} set for this computer in {C.LOCAL_CONFIG_PATH.name}")
    for name, c in cfg["cameras"].items():
        kwargs = {k: c[k] for k in ("fps", "width", "height", "fourcc") if k in c}
        idx = c.get("index_or_path")
        try:
            cam = OpenCVCamera(OpenCVCameraConfig(index_or_path=idx, **kwargs))
            cam.connect()
            frame = cam.async_read(timeout_ms=2000)
            cam.disconnect()
            _line("ok", f"camera '{name}'", f"index {idx} -> {frame.shape[1]}x{frame.shape[0]}")
        except Exception as exc:  # noqa: BLE001
            _line("warn" if idx not in ids else "fail", f"camera '{name}'",
                  f"index {idx}: {type(exc).__name__}: {str(exc)[:140]}",
                  "so cameras  (find the right index), then set it in hackathon.local.toml")


def run(cfg, state) -> int:
    _results.clear()
    print(f"so doctor  -  project {C.ROOT}\n")
    _check_python()
    _check_lerobot()
    _check_gpu()
    _check_ffmpeg()
    _check_symlinks()
    _check_serial_access()
    _check_hf(cfg, state)
    _check_disk()
    _check_ports(cfg, state)
    _check_calibration(cfg)
    _check_cameras(cfg)
    fails, warns = _results.count("fail"), _results.count("warn")
    print(f"\n{fails} problem(s), {warns} warning(s).")
    return 1 if fails else 0
