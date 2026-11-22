#!/usr/bin/env python3
"""Cut the final model's recorded tests into one short clip for the pitch deck (slide 7).

    python docs/presentation/build_demo_clip.py      # needs PyAV, numpy and Pillow (the lerobot env has them)

Reads the session videos that `so demo --record-video` saved in outputs/demo/ (team laptop only,
git-ignored) and writes, next to this script:

    video/final_model_3x.mp4   four runs of the final model, each from "arm running" to "in the box", 3x speed
    img/final_poster.jpg       its first frame (the slide shows it until the video is clicked)

Each run keeps the robot's own status line on top (attempt, run, the tally after the check) and gets a
caption below. The cut points are the moments that status line changes in each session video.
It also saves a poster for the voiced 1-minute video, if that video is on this computer
(outputs/video/CrimsonSnow-1min-ES-voz.jpg, used by `build_deck.py --voice`).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEMO = ROOT / "outputs" / "demo"
OUT = HERE / "video" / "final_model_3x.mp4"
POSTER = HERE / "img" / "final_poster.jpg"
VOICE = ROOT / "outputs" / "video" / "CrimsonSnow-1min-ES-voz.mp4"

# (session folder, run starts, status line changes after the check, caption). Model: act_battery_finetune_locations
# (fine-tuned from the 100k model with the 12 arc demonstrations), 22 Nov 2026. Every one is a first-run success
# logged in journal/demo.csv (05:11:22, 05:06:48, 05:09:20, 05:12:14), with nobody touching the mat during the run.
CLIPS = [
    ("20261122_051057", 1.80, 24.20, "Test 1 of 4"),
    ("20261122_050621", 2.47, 26.93, "Test 2 of 4"),
    ("20261122_050621", 140.87, 178.93, "Test 3 of 4"),
    ("20261122_051057", 54.60, 77.00, "Test 4 of 4  ·  cluttered mat"),
]
SPEED = 3.0
FPS = 30
AFTER = 0.6  # seconds of source after the status change, so the new tally is on screen
HOLD = 1.0  # seconds the last frame stays, with "in the box" in the caption
CAPTION_H = 64
BG, SNOW, MUTED, GREEN, CRIMSON = (22, 24, 29), (244, 246, 248), (169, 177, 188), (59, 178, 115), (232, 56, 79)


def font(size: int):
    from PIL import ImageFont

    for name in ("segoeuib.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def caption(width: int, label: str, done: bool):
    import numpy as np
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, CAPTION_H), BG)
    d = ImageDraw.Draw(img)
    big, small = font(28), font(22)
    x = 18
    for text, color, f in (("Final model", CRIMSON, big), ("   ·   " + label, SNOW, big)):
        d.text((x, CAPTION_H // 2), text, fill=color, font=f, anchor="lm")
        x += d.textlength(text, font=f)
    right, color = ("in the box, first run", GREEN) if done else (f"{SPEED:g}x speed", MUTED)
    d.text((width - 18, CAPTION_H // 2), right, fill=color, font=big if done else small, anchor="rm")
    return np.asarray(img)


def frames(path: Path, start: float, end: float):
    """(time, rgb array) of the decoded frames from just before `start` to `end`."""
    import av

    with av.open(str(path)) as c:
        s = c.streams.video[0]
        c.seek(int(max(0.0, start - 3.0) / s.time_base), stream=s)
        for f in c.decode(s):
            t = float(f.pts * f.time_base)
            if t > end:
                break
            yield t, f.to_ndarray(format="rgb24")


def build() -> int:
    from fractions import Fraction

    import av
    import numpy as np
    from PIL import Image

    missing = [DEMO / s / "test.mp4" for s, *_ in CLIPS if not (DEMO / s / "test.mp4").is_file()]
    if missing:
        print(f"not on this computer: {', '.join(p.relative_to(ROOT).as_posix() for p in missing)}")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    step = SPEED / FPS  # source seconds per output frame
    container = av.open(str(OUT), "w", options={"movflags": "+faststart"})
    stream = None
    n = 0

    def emit(img):
        nonlocal stream, n
        if stream is None:
            stream = container.add_stream("libx264", rate=FPS)
            stream.width, stream.height, stream.pix_fmt = img.shape[1], img.shape[0], "yuv420p"
            stream.options = {"preset": "slow", "crf": "24"}
            Image.fromarray(img).save(POSTER, quality=88)
        vf = av.VideoFrame.from_ndarray(img, format="rgb24")
        vf.pts, vf.time_base = n, Fraction(1, FPS)
        for packet in stream.encode(vf):
            container.mux(packet)
        n += 1

    for session, start, change, label in CLIPS:
        end = change + AFTER
        running, done = None, None
        t_out, last = start, None
        for t, img in frames(DEMO / session / "test.mp4", start, end):
            if running is None:
                running, done = caption(img.shape[1], label, False), caption(img.shape[1], label, True)
            while last is not None and t_out < t and t_out <= end:
                emit(np.vstack([last, running]))
                t_out += step
            last = img
        for _ in range(round(HOLD * FPS)):
            emit(np.vstack([last, done]))
        print(f"  {session}  {start:7.2f}-{change:7.2f} s  {label}")
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    print(f"saved {OUT.relative_to(ROOT).as_posix()}  ({n / FPS:.1f} s, {OUT.stat().st_size / 1e6:.1f} MB) "
          f"and {POSTER.relative_to(ROOT).as_posix()}")

    if VOICE.is_file():  # poster for `build_deck.py --voice`: the voiced video at 2 s
        for t, img in frames(VOICE, 2.0, 2.2):
            if t >= 2.0:
                Image.fromarray(img).save(VOICE.with_suffix(".jpg"), quality=88)
                print(f"saved {VOICE.with_suffix('.jpg').relative_to(ROOT).as_posix()}")
                break
    return 0


if __name__ == "__main__":
    sys.exit(build())
