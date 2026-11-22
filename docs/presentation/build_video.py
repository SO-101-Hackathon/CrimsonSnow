"""Builds the team's 1-minute video for the judges (no sound: the voice-over is added afterwards).

    python docs/presentation/build_video.py [--intro FRAMES_DIR] [--out outputs/video/CrimsonSnow-1min.mp4]

Everything in it is our own material:
  0:00-0:10  the need      Blender intro (a battery thrown in a kitchen bin catches fire) + three sourced facts
  0:10-0:23  the task      the clutter test from `so demo --record-video` (overhead + wrist camera)
  0:23-0:42  the data      start frames of the recorded episodes, the first model's failure, the variations
  0:42-0:56  innovation    a real retry from `so demo`, the gripper signal that labels our vision model
  0:56-1:00  close         the battery in the box, 24/24, the repository

Needs the lerobot environment (PyAV, OpenCV, Pillow, pandas) and the git-ignored outputs/ folder of the team
laptop: outputs/demo (check photos and the test video), outputs/vision (cached dataset and frames).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sokit import vision  # noqa: E402

W, H, FPS = 1920, 1080, 30
LANG = "en"  # "es": Spanish version (--lang es)


def T(en: str, es: str) -> str:
    return es if LANG == "es" else en


FACTS_ES = [(1.9, 4.05, "España: arde una planta de residuos cada 3,5 días",
             "109 incendios en 2023 · las baterías de litio, una causa en aumento", "Fuente: TECNIFUEGO / IFEMA SICUR"),
            (4.05, 6.1, "Llegan en la basura de casa", "móviles, vapeadores, juguetes… y pueden arder si se aplastan",
             "Fuente: FER, Federación Española de la Recuperación y el Reciclaje"),
            (6.1, 8.0, "UE: recoger el 73 % de las pilas en 2030", "y cada una hay que separarla de la basura",
             "Fuente: Reglamento (UE) 2023/1542")]
DURATION = 60.0
TRASH = ROOT / "outputs" / "demo" / "test video trash" / "test.mp4"
DATASET = ROOT / "outputs" / "vision" / "cache" / "ds_af51284a6c"
FRAMES = ROOT / "outputs" / "vision" / "frames"
RETRY = ROOT / "outputs" / "demo" / "20261121_160918"          # attempt 1: run 1 on the mat, run 2 in the box
FAILED = ROOT / "outputs" / "demo" / "20261121_162022" / "attempt01_run2_top.jpg"  # first model: never opened
SAMPLES = ROOT / "outputs" / "vision" / "samples.jpg"
PANEL = ROOT / "docs" / "images" / "panel.jpg"

CRIMSON = (215, 38, 61)
SNOW = (245, 247, 250)
INK = (16, 18, 24)
GREEN = (46, 204, 113)
AMBER = (247, 183, 51)
MUTED = (170, 178, 190)

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu"), Path("/System/Library/Fonts/Supplemental")]
FONT_FILES = {"bold": ["segoeuib.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"],
              "semi": ["seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"],
              "regular": ["segoeui.ttf", "DejaVuSans.ttf", "Arial.ttf"]}
_fonts: dict = {}


def font(weight: str, size: int):
    key = (weight, size)
    if key not in _fonts:
        for d in FONT_DIRS:
            for name in FONT_FILES[weight]:
                if (d / name).is_file():
                    _fonts[key] = ImageFont.truetype(str(d / name), size)
                    break
            if key in _fonts:
                break
        else:
            _fonts[key] = ImageFont.load_default(size=size)
    return _fonts[key]


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def fade(t: float, start: float, end: float, edge: float = 0.3) -> float:
    """0..1 visibility of something shown from start to end, fading in and out."""
    if t < start or t > end:
        return 0.0
    return min(ease((t - start) / edge), ease((end - t) / edge))


# ----------------------------------------------------------------------------- drawing helpers
def cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale and crop to fill `size`."""
    w, h = size
    s = max(w / img.width, h / img.height)
    im = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def fit(img: Image.Image, box: tuple[int, int]) -> Image.Image:
    s = min(box[0] / img.width, box[1] / img.height)
    return img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)


def text(canvas: Image.Image, xy, s: str, size: int, weight="bold", fill=SNOW, alpha=1.0, anchor="la", shadow=True):
    if alpha <= 0:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(weight, size)
    if shadow:
        d.text((xy[0] + 3, xy[1] + 3), s, font=f, fill=(0, 0, 0, int(170 * alpha)), anchor=anchor)
    d.text(xy, s, font=f, fill=(*fill, int(255 * alpha)), anchor=anchor)
    canvas.alpha_composite(layer)


def band(canvas: Image.Image, y0: int, y1: int, alpha: float, color=(10, 12, 16), strength=0.72):
    if alpha <= 0:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle((0, y0, W, y1), fill=(*color, int(255 * strength * alpha)))
    canvas.alpha_composite(layer)


def accent(canvas: Image.Image, x: int, y: int, h: int, alpha: float, color=CRIMSON, w: int = 8):
    if alpha <= 0:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle((x, y, x + w, y + h), fill=(*color, int(255 * alpha)))
    canvas.alpha_composite(layer)


def paste(canvas: Image.Image, img: Image.Image, xy, alpha=1.0, radius=14, border=None):
    if alpha <= 0:
        return
    im = img.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=int(255 * alpha))
    canvas.paste(im, xy, mask)
    if border:
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((xy[0], xy[1], xy[0] + im.width - 1, xy[1] + im.height - 1),
                                                radius=radius, outline=(*border, int(255 * alpha)), width=5)
        canvas.alpha_composite(layer)


def lower_third(canvas, t, start, end, title, sub=None, source=None, y=800):
    a = fade(t, start, end)
    if a <= 0:
        return
    slide = (1 - ease((t - start) / 0.4)) * 40
    band(canvas, y - 30, y + (170 if sub else 110), a)
    accent(canvas, 90, y, 70 if not sub else 130, a)
    text(canvas, (125 - slide, y - 6), title, 62, "bold", alpha=a)
    if sub:
        text(canvas, (125 - slide, y + 72), sub, 38, "semi", fill=MUTED, alpha=a)
    if source:
        text(canvas, (W - 60, H - 40), source, 22, "regular", fill=MUTED, alpha=a, anchor="rs")


# ----------------------------------------------------------------------------- sources
class Clip:
    """Sequential reader of a video: frame(t) returns the frame at source time t (t never goes back)."""

    def __init__(self, path: Path, start: float = 0.0):
        self.container = av.open(str(path))
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"
        if start > 0:
            self.container.seek(int(max(0, start - 1) / self.stream.time_base), stream=self.stream, backward=True)
        self.frames = self.container.decode(self.stream)
        self.current = None
        self.next = None
        self.next_t = -1.0

    def frame(self, t: float) -> Image.Image:
        while self.next_t < t:
            try:
                f = next(self.frames)
            except StopIteration:
                break
            self.current = self.next if self.next is not None else f.to_image()
            self.next, self.next_t = f.to_image(), float(f.time or 0)
            if self.next_t <= t:
                self.current = self.next
        return self.current if self.current is not None else self.next


def episode_info(e: int) -> tuple[Path, float, float, list[float]]:
    import pandas as pd

    info = json.loads((DATASET / "meta" / "info.json").read_text(encoding="utf-8"))
    eps = pd.concat([pd.read_parquet(p) for p in sorted((DATASET / "meta" / "episodes").rglob("*.parquet"))])
    ep = eps[eps["episode_index"] == e].iloc[0]
    key = "observation.images.front"
    video = DATASET / info["video_path"].format(video_key=key, chunk_index=int(ep[f"videos/{key}/chunk_index"]),
                                                 file_index=int(ep[f"videos/{key}/file_index"]))
    data = pd.concat([pd.read_parquet(p, columns=["episode_index", "frame_index", "observation.state"])
                      for p in sorted((DATASET / "data").rglob("*.parquet"))])
    rows = data[data["episode_index"] == e].sort_values("frame_index")
    gi = info["features"]["observation.state"]["names"].index("gripper.pos")
    grip = [float(s[gi]) for s in rows["observation.state"]]
    return video, float(ep[f"videos/{key}/from_timestamp"]), float(ep[f"videos/{key}/to_timestamp"]), grip


def battery_angle(img: np.ndarray):
    """(angle in degrees from straight, centre, box) of the light-wood stick on the dark mat, or None."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    mask = ((hsv[..., 0] >= 8) & (hsv[..., 0] <= 28) & (hsv[..., 1] >= 35) & (hsv[..., 1] <= 150) & (hsv[..., 2] >= 130))
    mask[:, :195] = False  # the cardboard box is on the left
    mask[:85] = False
    mask[430:] = False
    m = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cnts:
        a = cv2.contourArea(c)
        if not 250 <= a <= 2500:
            continue
        (cx, cy), (w, h), ang = cv2.minAreaRect(c)
        long, short = max(w, h), min(w, h)
        if short < 6 or long / short < 2.2:
            continue
        theta = ang if w < h else ang - 90  # angle of the long side from vertical
        theta = (theta + 90) % 180 - 90
        if best is None or a > best[3]:
            best = (theta, (cx, cy), (long, short), a)
    return best


def variation_examples():
    """Start frames where the stick lies straight, turned left and turned right (found by measuring it)."""
    found = []
    for p in sorted((FRAMES / "ds_af51284a6c").glob("ep*_f0000_on_mat.jpg")):
        img = np.array(Image.open(p).convert("RGB"))
        b = battery_angle(img)
        if b:
            found.append((p, b))
    pick = {}
    for name, target in (("turned left", -20), ("straight", 0), ("turned right", 20)):
        p, b = min(found, key=lambda x: abs(x[1][0] - target))
        pick[name] = (p, b)
    return pick


def relabel_samples(img: Image.Image) -> Image.Image:
    """Spanish captions on outputs/vision/samples.jpg (columns: in the box, on the mat, in the gripper; all right)."""
    img = img.copy()
    d = ImageDraw.Draw(img)
    names = ("en la caja", "en la alfombrilla", "en la pinza")
    for c in range(3):
        for r in range(img.height // 270):
            d.rectangle((c * 320, r * 270, c * 320 + 319, r * 270 + 29), fill=(22, 130, 60))
            d.text((c * 320 + 8, r * 270 + 5), f"{names[c]} · acierto", fill="white", font=font("semi", 18))
    return img


# ----------------------------------------------------------------------------- the sections
class Video:
    def __init__(self, intro_dir: Path | None):
        self.intro = sorted(intro_dir.glob("frame_*.png")) if intro_dir and intro_dir.is_dir() else []
        self.trash = Clip(TRASH)
        self.trash_hold = None
        starts = sorted((FRAMES / "ds_af51284a6c").glob("ep*_f0000_on_mat.jpg"))
        self.starts = [Image.open(p).convert("RGB").resize((448, 336), Image.LANCZOS) for p in starts[::2]]
        self.failed = Image.open(FAILED).convert("RGB")
        self.retry1 = Image.open(RETRY / "attempt01_run1_top.jpg").convert("RGB")
        self.retry2 = Image.open(RETRY / "attempt01_run2_top.jpg").convert("RGB")
        self.samples = Image.open(SAMPLES).convert("RGB")
        if LANG == "es":
            self.samples = relabel_samples(self.samples)
        self.panel = Image.open(PANEL).convert("RGB")
        self.var = variation_examples()
        video, t0, t1, grip = episode_info(59)
        self.ep_clip, self.ep_t0, self.ep_t1, self.grip = Clip(video, t0), t0, t1, grip
        lab = vision.episode_labels(grip, 30.0)
        self.ranges = lab.ranges if lab else {}

    # 0:00-0:10
    def need(self, t: float) -> Image.Image:
        if t < 8.0 and self.intro:
            i = min(len(self.intro) - 1, int(t * FPS))
            canvas = Image.open(self.intro[i]).convert("RGB").resize((W, H)).convert("RGBA")
        else:
            canvas = Image.new("RGBA", (W, H), (*INK, 255))
            if t < 8.0:  # no Blender frames: plain dark background
                pass
        facts = [(1.9, 4.05, "UK: a battery fire in the waste system every 3 hours", "2,839 fires in 2025",
                  "Source: Recycle Your Electricals research, 2025"),
                 (4.05, 6.1, "Spain: a waste plant on fire every 3.5 days", "Lithium batteries: a growing cause (2023)",
                  "Source: TECNIFUEGO / IFEMA SICUR"),
                 (6.1, 8.0, "EU law: collect 73% of portable batteries by 2030", "Every one has to be sorted out of the waste",
                  "Source: EU Batteries Regulation 2023/1542")]
        if LANG == "es":
            facts = FACTS_ES
        for start, end, title, sub, src in facts:
            lower_third(canvas, t, start, end, title, sub, src)
        if t >= 8.0:
            a = fade(t, 8.15, 10.2, 0.45)
            if LANG == "es":
                text(canvas, (W // 2, H // 2 - 70), "Hay que sacarlas de la basura.", 76, "bold", alpha=a, anchor="mm")
                accent(canvas, W // 2 - 120, H // 2, 6, a, w=240)
                b = fade(t, 8.6, 10.2, 0.45)
                text(canvas, (W // 2, H // 2 + 80), "A mano es peligroso: una batería dañada puede arder sin aviso.", 42, "semi",
                     fill=AMBER, alpha=b, anchor="mm")
            else:
                text(canvas, (W // 2, H // 2 - 20), "Someone has to get the batteries out.", 76, "bold", alpha=a, anchor="mm")
                accent(canvas, W // 2 - 120, H // 2 + 50, 6, a, w=240)
        return canvas

    # 0:10-0:23
    def task(self, t: float) -> Image.Image:
        local = t - 10.0
        src_t = min(31.0, local * 2.2)          # the clutter test at 2.2x speed, last frame held
        frame = self.trash.frame(src_t)
        top = frame.crop((0, 44, 640, 524))
        wrist = frame.crop((640, 44, 1280, 524))
        canvas = Image.new("RGBA", (W, H), (*INK, 255))
        paste(canvas, top.resize((1280, 960), Image.LANCZOS), (40, 60), radius=18)
        paste(canvas, wrist.resize((520, 390), Image.LANCZOS), (1360, 60), radius=18)
        text(canvas, (1360, 470), T("wrist camera", "cámara de la muñeca"), 26, "semi", fill=MUTED)
        text(canvas, (60, 1062), T("overhead camera · real test, 2.2x speed", "cámara cenital · prueba real, velocidad x2,2"), 24, "semi", fill=MUTED, anchor="ls")
        steps = [(T("1  FIND", "1  ENCONTRAR"), 0.0, 3.4), (T("2  PICK", "2  COGER"), 3.4, 6.6), (T("3  PLACE", "3  DEJAR"), 6.6, 13.0)]
        for i, (label, s, e) in enumerate(steps):
            on = s <= local < e
            y = 560 + i * 92
            col = CRIMSON if on else (60, 64, 74)
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle((1360, y, 1880, y + 74), radius=12, fill=(*col, 235))
            canvas.alpha_composite(layer)
            text(canvas, (1390, y + 37), label, 40, "bold", alpha=1.0 if on else 0.55, anchor="lm", shadow=False)
        a = fade(local, 0.3, 13.0)
        text(canvas, (1360, 868), T("every time", "siempre"), 34, "semi", fill=SNOW, alpha=a)
        b = fade(local, 6.8, 13.0)
        band(canvas, 965, 1080, b, strength=0.0)
        text(canvas, (1360, 930), T("14 other objects on the mat.", "14 objetos más en la alfombrilla."), 32, "bold", alpha=b)
        text(canvas, (1360, 972), T("Only the battery taken, first try.", "Solo la batería, a la primera."), 32, "bold", fill=GREEN, alpha=b)
        return canvas

    # 0:23-0:42
    def data(self, t: float) -> Image.Image:
        local = t - 23.0
        canvas = Image.new("RGBA", (W, H), (*INK, 255))
        if local < 5.0:  # every position: start frames flicker in a 4 x 3 grid
            for k in range(12):
                idx = (int(local * 6) + k * 7) % len(self.starts)
                x, y = 60 + (k % 4) * 458, 150 + (k // 4) * 300
                paste(canvas, self.starts[idx].resize((440, 286)), (x, y), radius=10)
            n = int(round(ease(local / 4.0) * 108))
            text(canvas, (60, 50), f"{n} " + T("demonstrations", "demostraciones"), 64, "bold")
            text(canvas, (W - 60, 70), T("every object through every position", "cada objeto en cada posición"), 38, "semi", fill=MUTED, anchor="rt")
        elif local < 9.0:  # the first model's failure
            l2 = local - 5.0
            paste(canvas, self.failed.resize((960, 720), Image.LANCZOS), (60, 180), radius=16, border=CRIMSON)
            text(canvas, (60, 70), T("Test of model 1: 3 / 7", "Prueba del modelo 1: 3 / 7"), 64, "bold")
            text(canvas, (1080, 230), T("Every failure logged:", "Cada fallo, anotado:"), 44, "bold", alpha=fade(l2, 0.2, 4.0))
            for i, line in enumerate((T("×  battery turned: no attempt", "×  batería girada: ni lo intenta"), T("×  grasp too low: stuck", "×  agarre demasiado bajo: se atasca"), T("×  position moved: missed", "×  posición movida: falla"))):
                text(canvas, (1080, 330 + i * 80), line, 40, "semi", fill=(255, 120, 120), alpha=fade(l2, 0.5 + i * 0.5, 4.0))
        elif local < 14.5:  # the variations, recorded on purpose
            l3 = local - 9.0
            text(canvas, (60, 60), T("+149 demos aimed at the failures", "+149 demostraciones dirigidas a los fallos"), 64, "bold")
            labels = [("turned left", "−20°"), ("straight", "0°"), ("turned right", "+20°")]
            for i, (name, deg) in enumerate(labels):
                p, b = self.var[name]
                img = Image.open(p).convert("RGB")
                cx, cy = b[1]
                crop = img.crop((int(cx - 75), int(cy - 75), int(cx + 75), int(cy + 75))).resize((420, 420), Image.LANCZOS)
                x = 140 + i * 560
                a = fade(l3, 0.2 + i * 0.35, 5.5)
                paste(canvas, crop, (x, 190), alpha=a, radius=16, border=CRIMSON if name != "straight" else (90, 96, 108))
                text(canvas, (x + 210, 640), T(name, {"turned left": "girada a la izquierda", "straight": "recta", "turned right": "girada a la derecha"}[name]), 40, "bold", alpha=a, anchor="mt")
                text(canvas, (x + 210, 694), deg, 34, "semi", fill=MUTED, alpha=a, anchor="mt")
            a = fade(l3, 1.6, 5.5)
            text(canvas, (W // 2, 770), T("and moved 2 cm towards and away from the arm", "y movida 2 cm hacia el brazo y en sentido contrario"), 36, "semi", fill=MUTED, alpha=a, anchor="mt")
            b = fade(l3, 2.4, 5.5)
            if b > 0:
                layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                x0, x1, y0 = 240, 1680, 870
                split = x0 + int((x1 - x0) * 0.8 * ease((l3 - 2.4) / 1.0))
                d.rounded_rectangle((x0, y0, x1, y0 + 56), radius=10, fill=(60, 64, 74, int(255 * b)))
                d.rounded_rectangle((x0, y0, split, y0 + 56), radius=10, fill=(*GREEN, int(255 * b)))
                canvas.alpha_composite(layer)
                text(canvas, (x0 + 20, y0 + 28), T("80% normal placements", "80 % colocación normal"), 30, "bold", fill=INK, alpha=b, anchor="lm", shadow=False)
                text(canvas, (x1 - 20, y0 + 28), T("20% variations", "20 % variaciones"), 30, "bold", alpha=b, anchor="rm", shadow=False)
                text(canvas, (W // 2, 960), T("so nothing it already knew is forgotten", "para que no olvide lo que ya sabía"), 32, "semi", fill=MUTED, alpha=b, anchor="mt")
        else:  # the totals
            l4 = local - 14.5
            stats = [("257", T("demonstrations", "demostraciones")), (T("169,675", "169.675"), T("frames", "fotogramas")), ("94 min", T("of driving the arm", "guiando el brazo")), ("2", T("cameras", "cámaras"))]
            for i, (big, small) in enumerate(stats):
                a = fade(l4, 0.15 + i * 0.25, 4.6)
                x = (120, 520, 1030, 1500)[i]
                text(canvas, (x, 380), big, 110, "bold", fill=SNOW if i else CRIMSON, alpha=a)
                text(canvas, (x, 520), small, 36, "semi", fill=MUTED, alpha=a)
            a = fade(l4, 1.3, 4.6)
            text(canvas, (120, 700), T("ACT policy · 100,000 training steps on an RTX 5090", "Política ACT · 100.000 pasos de entrenamiento en una RTX 5090"), 44, "bold", alpha=a)
        return canvas

    # 0:42-0:56
    def innovation(self, t: float) -> Image.Image:
        local = t - 42.0
        canvas = Image.new("RGBA", (W, H), (*INK, 255))
        if local < 5.5:  # a real retry from `so demo`
            text(canvas, (60, 50), T("It checks its own work", "Comprueba su propio trabajo"), 64, "bold")
            text(canvas, (W - 60, 70), T("retries, hands off", "reintenta, sin que nadie lo toque"), 40, "semi", fill=MUTED, anchor="rt")
            a1 = fade(local, 0.1, 5.5)
            paste(canvas, self.retry1.resize((860, 645), Image.LANCZOS), (60, 200), alpha=a1, radius=16, border=AMBER)
            text(canvas, (60, 880), T("Run 1 · check: battery still on the mat", "Intento 1: sigue en la alfombrilla"), 36, "bold", fill=AMBER, alpha=a1)
            text(canvas, (60, 930), T("→ run again", "→ lo repite"), 36, "semi", fill=MUTED, alpha=a1)
            a2 = fade(local, 1.9, 5.5)
            paste(canvas, self.retry2.resize((860, 645), Image.LANCZOS), (1000, 200), alpha=a2, radius=16, border=GREEN)
            text(canvas, (1000, 880), T("Run 2 · check: battery is in the box", "Intento 2: está en la caja"), 36, "bold", fill=GREEN, alpha=a2)
            text(canvas, (1000, 930), T("real attempt, 21 Nov 2026", "intento real, 21 nov 2026"), 30, "semi", fill=MUTED, alpha=a2)
        elif local < 11.0:  # the gripper signal labels the frames
            l2 = local - 5.5
            text(canvas, (60, 50), T("Our own vision model", "Nuestro propio modelo de visión"), 64, "bold")
            text(canvas, (W - 60, 70), T("labels from the gripper's own signal", "etiquetas sacadas de la señal de la pinza"), 40, "semi", fill=MUTED, anchor="rt")
            n = len(self.grip)
            k = min(n - 1, int(ease(l2 / 5.0) * (n - 1)))
            frame = self.ep_clip.frame(self.ep_t0 + k / 30.0)
            label = next((name for name, (a, b) in self.ranges.items() if a <= k <= b), None)
            colors = {"on_mat": (90, 140, 255), "in_gripper": AMBER, "in_box": GREEN}
            words = {"on_mat": T("on the mat", "en la alfombrilla"), "in_gripper": T("in the gripper", "en la pinza"), "in_box": T("in the box", "en la caja")}
            paste(canvas, frame.resize((800, 600), Image.LANCZOS), (60, 190), radius=16,
                  border=colors.get(label, (90, 96, 108)))
            text(canvas, (60, 820), words.get(label, T("moving", "en movimiento")), 48, "bold", fill=colors.get(label, MUTED))
            # the gripper plot
            x0, y0, pw, ph = 940, 230, 920, 420
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.rectangle((x0, y0, x0 + pw, y0 + ph), fill=(28, 31, 38, 255))
            for name, (a, b) in self.ranges.items():
                d.rectangle((x0 + a / n * pw, y0, x0 + b / n * pw, y0 + ph), fill=(*colors[name], 60))
            pts = [(x0 + i / n * pw, y0 + ph - min(100.0, g) / 100.0 * ph) for i, g in enumerate(self.grip[: k + 1])]
            if len(pts) > 1:
                d.line(pts, fill=SNOW, width=4)
            d.line((x0 + k / n * pw, y0, x0 + k / n * pw, y0 + ph), fill=(*CRIMSON, 255), width=3)
            canvas.alpha_composite(layer)
            text(canvas, (x0, y0 - 50), T("gripper opening during one demonstration", "apertura de la pinza durante una demostración"), 30, "semi", fill=MUTED)
            for i, name in enumerate(("on_mat", "in_gripper", "in_box")):
                text(canvas, (x0 + (0, 330, 620)[i], y0 + ph + 30), "■ " + words[name], 32, "bold", fill=colors[name])
            text(canvas, (x0, 820), T("4,000 frames labelled automatically · 0 by hand", "4.000 fotogramas etiquetados solos · 0 a mano"), 34, "semi", alpha=fade(l2, 1.0, 5.5))
        else:  # the result
            l3 = local - 11.0
            paste(canvas, fit(self.samples, (1000, 840)), (60, 120), radius=16)
            for i, (big, small) in enumerate(((T("99.8%", "99,8 %"), T("right on episodes it never saw", "de aciertos en episodios que nunca vio")), ("10 ms", T("per photo", "por foto")),
                                              (T("offline", "sin conexión"), T("no internet, no API key", "sin internet ni clave de API")))):
                a = fade(l3, 0.1 + i * 0.3, 3.0)
                text(canvas, (1150, 180 + i * 260), big, 100, "bold", fill=CRIMSON if i == 0 else SNOW, alpha=a)
                text(canvas, (1150, 300 + i * 260), small, 34, "semi", fill=MUTED, alpha=a)
        return canvas

    # 0:56-1:00
    def close(self, t: float) -> Image.Image:
        local = t - 56.0
        canvas = Image.new("RGBA", (W, H), (*INK, 255))
        if local < 2.0:
            frame = self.trash.frame(32.5) if self.trash_hold is None else self.trash_hold
            self.trash_hold = frame
            paste(canvas, cover(frame.crop((0, 44, 640, 524)), (1280, 960)), (320, 60), radius=18,
                  alpha=fade(local, -1, 2.0, 0.35))
            text(canvas, (W // 2, 1050), T("battery in the box", "batería en la caja"), 34, "semi", fill=MUTED, anchor="ms", alpha=fade(local, 0.1, 2.0))
        else:
            l2 = local - 2.0
            a = fade(l2, 0.0, 2.2, 0.35)
            text(canvas, (W // 2, 360), "CrimsonSnow", 120, "bold", alpha=a, anchor="mm")
            accent(canvas, W // 2 - 160, 440, 6, a, w=320)
            text(canvas, (W // 2, 560), T("24 / 24 positions · hands off", "24 / 24 posiciones · sin tocarlo"), 64, "bold", fill=GREEN, alpha=a, anchor="mm")
            text(canvas, (W // 2, 660), T("keeping batteries out of the fire", "que ninguna batería acabe en el fuego"), 44, "semi", fill=MUTED, alpha=a, anchor="mm")
            text(canvas, (W // 2, 860), "github.com/SO-101-Hackathon/CrimsonSnow", 36, "semi", fill=SNOW, alpha=a, anchor="mm")
        return canvas

    def frame(self, t: float) -> Image.Image:
        for start, fn in ((56.0, self.close), (42.0, self.innovation), (23.0, self.data), (10.0, self.task), (0.0, self.need)):
            if t >= start:
                img = fn(t)
                break
        # short dip to black between sections
        for cut in (10.0, 23.0, 42.0, 56.0):
            d = abs(t - cut)
            if d < 0.12:
                black = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - d / 0.12))))
                img.alpha_composite(black)
        return img.convert("RGB")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--intro", default=str(ROOT / "outputs" / "video" / "intro"), help="folder of Blender frames frame_0001.png ...")
    p.add_argument("--out", default=str(ROOT / "outputs" / "video" / "CrimsonSnow-1min.mp4"))
    p.add_argument("--stills", nargs="*", type=float, help="only save these times as PNG next to --out (for checking)")
    p.add_argument("--lang", choices=["en", "es"], default="en", help="es = Spanish captions, Spain-first facts")
    args = p.parse_args()
    global LANG
    LANG = args.lang
    video = Video(Path(args.intro))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.stills:
        for t in sorted(args.stills):
            video.frame(t).save(out.with_name(f"still_{t:05.1f}.jpg"), quality=88)
        return 0
    container = av.open(str(out), "w")
    stream = container.add_stream("libx264", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = W, H, "yuv420p"
    stream.options = {"crf": "18", "preset": "medium"}
    total = int(DURATION * FPS)
    for i in range(total):
        frame = av.VideoFrame.from_ndarray(np.asarray(video.frame(i / FPS)), format="rgb24")
        frame.pts, frame.time_base = i, Fraction(1, FPS)
        for packet in stream.encode(frame):
            container.mux(packet)
        if i % 150 == 0:
            print(f"{i / FPS:5.1f} s", flush=True)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
