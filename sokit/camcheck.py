"""Live camera view with a "ghost" of the reference framing.

A policy only works if the cameras see the scene the way they did while recording. Save a
reference frame per camera right before the first recording session; later (after a bump,
a re-plug, the next morning) overlay the live image on it and nudge the camera until the
two line up. It also shows immediately when two camera indices have been swapped.

Cameras are opened through LeRobot's own OpenCVCamera, so indices and settings behave
exactly as they will in lerobot-record / lerobot-rollout.

Keys:  s = save current frames as reference    m = cycle overlay mode (edges/blend/live)
       q or Esc = quit
"""

from __future__ import annotations

import time

import numpy as np

from .config import ROOT

REF_DIR = ROOT / "calibration" / "camera_refs"
MODES = ("edges", "blend", "live")


def _open_cameras(cfg):
    from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig

    cams, errors = {}, {}
    for name, c in cfg["cameras"].items():
        if c.get("type", "opencv") != "opencv":
            errors[name] = f"type {c.get('type')} not supported by camcheck"
            continue
        kwargs = {k: c[k] for k in ("fps", "width", "height", "fourcc") if k in c}
        try:
            cam = OpenCVCamera(OpenCVCameraConfig(index_or_path=c["index_or_path"], **kwargs))
            cam.connect()
            cams[name] = cam
        except Exception as exc:  # noqa: BLE001 - report every camera, keep going
            errors[name] = f"{type(exc).__name__}: {exc}"
    return cams, errors


def _load_ref(name: str):
    from PIL import Image

    path = REF_DIR / f"{name}.png"
    return np.asarray(Image.open(path).convert("RGB")) if path.is_file() else None


def _save_refs(frames: dict) -> None:
    from PIL import Image

    REF_DIR.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        Image.fromarray(frame).save(REF_DIR / f"{name}.png")
    print(f"[so] saved reference frame(s) for {', '.join(frames)} in {REF_DIR}")


def misalignment(live: np.ndarray, ref: np.ndarray) -> float:
    """0 = identical framing. Compares blurred low-res grayscale so lighting matters less."""
    import cv2

    def prep(img):
        g = cv2.cvtColor(cv2.resize(img, (160, 120)), cv2.COLOR_RGB2GRAY).astype(np.float32)
        g = cv2.GaussianBlur(g, (5, 5), 0)
        return (g - g.mean()) / (g.std() + 1e-6)

    return float(np.abs(prep(live) - prep(ref)).mean())


def _compose(live: np.ndarray, ref, mode: str) -> np.ndarray:
    import cv2

    if ref is None or mode == "live":
        return live
    if ref.shape != live.shape:
        ref = cv2.resize(ref, (live.shape[1], live.shape[0]))
    if mode == "blend":
        return cv2.addWeighted(live, 0.5, ref, 0.5, 0)
    edges = cv2.Canny(cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY), 60, 150)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    out = live.copy()
    out[edges > 0] = (0, 255, 0)  # reference outlines in green on top of the live image
    return out


def run(cfg, save_now: bool = False) -> int:
    cams, errors = _open_cameras(cfg)
    for name, err in errors.items():
        print(f"[FAIL] camera '{name}': {err}")
    if not cams:
        print("No camera could be opened. Check indices with `so cameras`.")
        return 1
    try:
        if save_now:
            time.sleep(1.0)  # let auto-exposure settle
            _save_refs({n: c.async_read(timeout_ms=2000) for n, c in cams.items()})
            return 0
        return _ui(cams)
    finally:
        for cam in cams.values():
            try:
                cam.disconnect()
            except Exception:  # noqa: BLE001
                pass


def _ui(cams) -> int:
    import tkinter as tk

    from PIL import Image, ImageTk

    refs = {n: _load_ref(n) for n in cams}
    state = {"mode": 0, "frames": {}, "running": True}
    root = tk.Tk()
    root.title("so camcheck  -  s: save reference   m: overlay mode   q: quit")
    panels, captions = {}, {}
    for col, name in enumerate(cams):
        captions[name] = tk.Label(root, text=name, font=("Segoe UI", 11, "bold"))
        captions[name].grid(row=0, column=col, padx=4, pady=2)
        panels[name] = tk.Label(root)
        panels[name].grid(row=1, column=col, padx=4, pady=4)
    status = tk.Label(root, text="", font=("Segoe UI", 10))
    status.grid(row=2, column=0, columnspan=max(1, len(cams)), pady=4)

    def on_key(event):
        key = (event.keysym or "").lower()
        if key in ("q", "escape"):
            state["running"] = False
            root.destroy()
        elif key == "m":
            state["mode"] = (state["mode"] + 1) % len(MODES)
        elif key == "s" and state["frames"]:
            _save_refs(state["frames"])
            for n, f in state["frames"].items():
                refs[n] = f.copy()

    def tick():
        if not state["running"]:
            return
        mode = MODES[state["mode"]]
        for name, cam in cams.items():
            try:
                frame = cam.async_read(timeout_ms=500)
            except Exception as exc:  # noqa: BLE001
                captions[name].config(text=f"{name}: NO FRAME ({type(exc).__name__})", fg="red")
                continue
            state["frames"][name] = frame
            ref = refs.get(name)
            if ref is None:
                text, colour = f"{name}: no reference yet (press s)", "black"
            else:
                score = misalignment(frame, ref)
                verdict = "aligned" if score < 0.25 else ("close" if score < 0.5 else "MOVED / wrong camera?")
                colour = "dark green" if score < 0.25 else ("dark orange" if score < 0.5 else "red")
                text = f"{name}: {verdict}  (difference {score:.2f})"
            captions[name].config(text=text, fg=colour)
            photo = ImageTk.PhotoImage(Image.fromarray(_compose(frame, ref, mode)))
            panels[name].config(image=photo)
            panels[name].image = photo  # keep a reference or Tk drops the image
        status.config(text=f"overlay: {mode}   |   green lines = reference outlines   |   s save   m mode   q quit")
        root.after(66, tick)

    root.bind("<Key>", on_key)
    root.protocol("WM_DELETE_WINDOW", lambda: (state.update(running=False), root.destroy()))
    root.after(100, tick)
    root.mainloop()
    return 0
