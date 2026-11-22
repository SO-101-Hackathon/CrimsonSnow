"""The judges' video in Spanish, cut to the team's own voice-over and exactly 60 seconds long.

    python docs/presentation/build_story_video.py

The voice-over is the four recordings in recording/ (1st.m4a, 2nd.m4a, 3.m4a, 4th.m4a), reading the story
script in guion-video-es.md. The script cuts the silences at both ends, shortens long pauses to 0.3 s,
speeds the speech up slightly (pitch unchanged) so it fits 60 s, and evens out the loudness. Every picture
change is placed on the word it belongs to (word times measured once with Whisper, listed in EVENTS), and
the spoken text runs as subtitles. Output: outputs/video/CrimsonSnow-1min-ES-voz.mp4.

Uses the same material as build_video.py: the Blender intro frames (outputs/video/intro), the clutter test
(outputs/demo/test video trash/test.mp4), check photos from `so demo` and frames of the recordings.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_video as bv  # noqa: E402

ROOT = bv.ROOT
W, H, FPS = bv.W, bv.H, bv.FPS
REC = ROOT / "recording"
PARTS = ["1st.m4a", "2nd.m4a", "3.m4a", "4th.m4a"]
OUT_DIR = ROOT / "outputs" / "video"
FFMPEG = shutil.which("ffmpeg") or str(Path(sys.executable).parent / "Library" / "bin" / "ffmpeg.exe")
SR = 48000
VO_START, VO_END, DURATION = 0.25, 59.5, 60.0
GAP_CAP, PART_GAP = 0.30, 0.35
LONG_BEATS = {(3, 15.72): 0.6}   # a breath before "El equipo de CrimsonSnow"

# Word times in each recording (seconds from its start), measured with Whisper (openai/whisper-base).
EVENTS = {
    "p1": 0, "p1.casa_end": 3.37, "p1.viaja": 4.21, "p1.camion": 4.80, "p1.planta": 6.38, "p1.aplastarse": 6.94,
    "p1.prende": 9.00, "p1.espana": 10.46, "p1.end": 14.87,
    "p2.sacarlas": 0.53, "p2.asi": 2.79, "p2.llenamos": 5.76, "p2.patitos": 7.92, "p2.llaves": 8.74,
    "p2.movil": 9.40, "p2.tijeras": 10.36, "p2.entre": 11.65, "p2.bateria": 16.34, "p2.end": 17.12,
    "p3.principio": 0.24, "p3.girada": 2.62, "p3.cogia": 5.68, "p3.ensenamos": 9.49, "p3.uno": 11.90,
    "p3.hoy": 14.92, "p3.end": 18.98,
    "p4.cuando": 0.98, "p4.mira": 4.76, "p4.vuelve": 8.64, "p4.solo": 10.66, "p4.internet": 11.04,
    "p4.nadie": 12.18, "p4.equipo": 15.72, "p4.para": 17.60, "p4.end": 20.03,
}
SUBTITLES = [
    (0, 1.14, 3.37, "Una pila acaba en la basura de casa."),
    (0, 4.21, 9.69, "Viaja en un camión, llega a una planta y, al aplastarse, prende fuego."),
    (0, 10.46, 14.87, "En España arde una planta de residuos cada tres días y medio."),
    (1, 0.53, 5.04, "Sacarlas a mano es peligroso, así que se lo enseñamos a un robot."),
    (1, 5.76, 11.22, "Le llenamos la mesa de cosas: patitos, llaves, un móvil, unas tijeras."),
    (1, 11.65, 17.12, "Y entre todo eso, fue a por lo único que importaba: la batería."),
    (2, 0.24, 2.00, "Al principio no le salía."),
    (2, 2.62, 8.98, "Si la batería estaba girada, ni lo intentaba; si la cogía mal, se le atascaba."),
    (2, 9.49, 13.77, "Le enseñamos justo esos casos, uno a uno, hasta que dejó de fallar."),
    (2, 14.92, 18.98, "Hoy acierta en todas las posiciones que le ponemos."),
    (3, 0.98, 10.35, "Cuando algo sale mal, no se rinde: mira la caja, ve que la batería sigue ahí y lo vuelve a intentar."),
    (3, 10.68, 14.30, "Solo. Sin internet. Sin que nadie meta la mano."),
    (3, 15.72, 20.03, "El equipo de CrimsonSnow: para que ninguna batería acabe en el fuego."),
]

# Where things are in the clutter test's overhead picture (640 x 480).
DUCKS = [(230, 172), (282, 220), (352, 277), (197, 300), (367, 375)]
KEYS, PHONE, SCISSORS, BATTERY = (367, 325), (387, 185), (227, 250), (236, 334)
BOX = (12, 160, 182, 405)   # the cardboard box in the check photos (640 x 480)


# ----------------------------------------------------------------------------- the voice-over
def load(path: Path) -> np.ndarray:
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def speech(x: np.ndarray, thr_db=-38.0, hop=0.01, min_gap=0.25) -> list[list[float]]:
    n = int(hop * SR)
    frames = len(x) // n
    db = 20 * np.log10(np.sqrt(np.mean(x[: frames * n].reshape(frames, n) ** 2, axis=1) + 1e-12))
    segs, start = [], None
    for i, on in enumerate(db > thr_db):
        if on and start is None:
            start = i * hop
        if not on and start is not None:
            segs.append([start, i * hop]); start = None
    if start is not None:
        segs.append([start, frames * hop])
    merged: list[list[float]] = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return [s for s in merged if s[1] - s[0] > 0.12]


class VoiceOver:
    """Cuts the four parts together; maps a time in a part to a time in the final video."""

    def __init__(self):
        self.audio = [load(REC / f) for f in PARTS]
        self.keep: list[list[tuple[float, float, float]]] = []   # per part: (start, end, position in the cut)
        pieces, pos = [], 0.0
        for k, x in enumerate(self.audio):
            spans = [[max(0.0, a - 0.06), min(len(x) / SR, b + 0.08)] for a, b in speech(x)]
            part = []
            for i, (a, b) in enumerate(spans):
                if i:
                    gap = a - spans[i - 1][1]
                    cap = next((v for (pk, t), v in LONG_BEATS.items() if pk == k and abs(t - a) < 0.4), GAP_CAP)
                    pos += min(max(gap, 0.0), cap)
                    pieces.append(np.zeros(int(min(max(gap, 0.0), cap) * SR), np.float32))
                seg = x[int(a * SR): int(b * SR)].copy()
                ramp = min(len(seg) // 2, int(0.008 * SR))
                seg[:ramp] *= np.linspace(0, 1, ramp); seg[-ramp:] *= np.linspace(1, 0, ramp)
                part.append((a, b, pos))
                pieces.append(seg)
                pos += b - a
            self.keep.append(part)
            if k < len(self.audio) - 1:
                pieces.append(np.zeros(int(PART_GAP * SR), np.float32))
                pos += PART_GAP
        self.cut = np.concatenate(pieces)
        self.length = len(self.cut) / SR
        self.speed = self.length / (VO_END - VO_START)

    def at(self, part: int, t: float) -> float:
        """Time in the final video of second `t` of recording `part`."""
        spans = self.keep[part]
        for a, b, p in spans:
            if t <= b:
                return VO_START + (p + max(0.0, t - a)) / self.speed
        a, b, p = spans[-1]
        return VO_START + (p + b - a) / self.speed

    def write(self, out: Path) -> Path:
        raw = out.with_name("vo_cut.wav")
        _write_wav(raw, self.cut)
        flt = (f"atempo={self.speed:.5f},loudnorm=I=-16:TP=-1.5:LRA=11,adelay={int(VO_START * 1000)}|{int(VO_START * 1000)},"
               f"apad,atrim=0:{DURATION}")
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(raw), "-af", flt, "-ar", str(SR), "-ac", "1", str(out)], check=True)
        return out


def _write_wav(path: Path, x: np.ndarray) -> None:
    import wave

    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)


# ----------------------------------------------------------------------------- drawing helpers
def dim(img: Image.Image, amount: float) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, int(255 * amount)))
    out = img.convert("RGBA"); out.alpha_composite(layer); return out


def ring(canvas: Image.Image, xy, r: int, color, alpha=1.0, width=6):
    if alpha <= 0:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r), outline=(*color, int(255 * alpha)), width=width)
    canvas.alpha_composite(layer)


def tag(canvas: Image.Image, xy, text: str, color, alpha=1.0, size=40, anchor="lm"):
    """A label on a solid pill, for pointing at things."""
    if alpha <= 0:
        return
    f = bv.font("bold", size)
    d = ImageDraw.Draw(canvas)
    box = d.textbbox(xy, text, font=f, anchor=anchor)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((box[0] - 18, box[1] - 12, box[2] + 18, box[3] + 12), radius=14,
                                            fill=(*color, int(235 * alpha)))
    canvas.alpha_composite(layer)
    bv.text(canvas, xy, text, size, "bold", fill=(16, 18, 24) if sum(color) > 450 else bv.SNOW, alpha=alpha,
            anchor=anchor, shadow=False)


def overhead_full(frame: Image.Image) -> Image.Image:
    """The clutter test's overhead camera, filling the 16:9 screen (rows 60-420 of 480)."""
    return frame.crop((0, 44 + 60, 640, 44 + 420)).resize((W, H), Image.LANCZOS).convert("RGBA")


def in_full(p) -> tuple[int, int]:
    return int(p[0] * 3), int((p[1] - 60) * 3)


def photo_43(img: Image.Image) -> tuple[Image.Image, float, int]:
    """A 640 x 480 photo letterboxed into the screen: (canvas, scale, x offset)."""
    s = H / img.height
    w = int(img.width * s)
    canvas = Image.new("RGBA", (W, H), (*bv.INK, 255))
    canvas.paste(img.resize((w, H), Image.LANCZOS), ((W - w) // 2, 0))
    return canvas, s, (W - w) // 2


def subtitle(canvas: Image.Image, text: str, alpha: float):
    if alpha <= 0 or not text:
        return
    f = bv.font("semi", 40)
    d = ImageDraw.Draw(canvas)
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) > 1500 and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    lines.append(cur)
    y = H - 70 - 52 * (len(lines) - 1)
    bv.band(canvas, y - 44, H, alpha, strength=0.55)
    for i, line in enumerate(lines):
        bv.text(canvas, (W // 2, y + i * 52), line, 40, "semi", alpha=alpha, anchor="ms")


# simple line icons for the journey
def icon_house(d, cx, cy, col, s=1.0):
    d.polygon([(cx - 90 * s, cy - 10 * s), (cx, cy - 95 * s), (cx + 90 * s, cy - 10 * s)], outline=col, width=8)
    d.rectangle((cx - 70 * s, cy - 10 * s, cx + 70 * s, cy + 85 * s), outline=col, width=8)
    d.rectangle((cx - 18 * s, cy + 30 * s, cx + 18 * s, cy + 85 * s), outline=col, width=8)


def icon_truck(d, cx, cy, col, s=1.0):
    d.rectangle((cx - 110 * s, cy - 55 * s, cx + 30 * s, cy + 45 * s), outline=col, width=8)
    d.polygon([(cx + 30 * s, cy - 25 * s), (cx + 80 * s, cy - 25 * s), (cx + 110 * s, cy + 10 * s),
               (cx + 110 * s, cy + 45 * s), (cx + 30 * s, cy + 45 * s)], outline=col, width=8)
    for wx in (-70, 70):
        d.ellipse((cx + wx * s - 22 * s, cy + 35 * s, cx + wx * s + 22 * s, cy + 79 * s), outline=col, width=8)


def icon_plant(d, cx, cy, col, s=1.0):
    d.rectangle((cx - 110 * s, cy - 10 * s, cx + 110 * s, cy + 85 * s), outline=col, width=8)
    d.line([(cx - 110 * s, cy - 10 * s), (cx - 60 * s, cy - 50 * s), (cx - 60 * s, cy - 10 * s), (cx - 10 * s, cy - 50 * s),
            (cx - 10 * s, cy - 10 * s), (cx + 40 * s, cy - 50 * s), (cx + 40 * s, cy - 10 * s)], fill=col, width=8)
    d.rectangle((cx + 60 * s, cy - 100 * s, cx + 90 * s, cy - 10 * s), outline=col, width=8)


def battery_icon(canvas, cx, cy, alpha=1.0, s=1.0):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((cx - 34 * s, cy - 15 * s, cx + 34 * s, cy + 15 * s), radius=6, fill=(201, 160, 106, int(255 * alpha)),
                        outline=(80, 56, 28, int(255 * alpha)), width=3)
    d.line([(cx + 14 * s, cy), (cx + 26 * s, cy)], fill=(40, 28, 12, int(255 * alpha)), width=4)
    d.line([(cx + 20 * s, cy - 6 * s), (cx + 20 * s, cy + 6 * s)], fill=(40, 28, 12, int(255 * alpha)), width=4)
    d.line([(cx - 26 * s, cy), (cx - 14 * s, cy)], fill=(40, 28, 12, int(255 * alpha)), width=4)
    canvas.alpha_composite(layer)


def warning_icon(canvas, cx, cy, alpha=1.0):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon([(cx, cy - 120), (cx + 140, cy + 115), (cx - 140, cy + 115)], fill=(*bv.AMBER, int(255 * alpha)))
    d.rounded_rectangle((cx - 13, cy - 45, cx + 13, cy + 50), radius=8, fill=(16, 18, 24, int(255 * alpha)))
    d.ellipse((cx - 15, cy + 68, cx + 15, cy + 98), fill=(16, 18, 24, int(255 * alpha)))
    canvas.alpha_composite(layer)


def check_mark(canvas, cx, cy, r, alpha=1.0):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*bv.GREEN, int(235 * alpha)))
    d.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.38)],
           fill=(255, 255, 255, int(255 * alpha)), width=max(3, int(r * 0.22)))
    canvas.alpha_composite(layer)


# ----------------------------------------------------------------------------- the story
class Story:
    def __init__(self, vo: VoiceOver):
        self.vo = vo
        self.e = {}
        for key, t in EVENTS.items():
            part = int(key[1]) - 1
            self.e[key] = vo.at(part, t)
        self.part_start = [vo.at(k, 0.0) - 0.15 for k in range(4)]
        self.subs = [(vo.at(k, a), vo.at(k, b), text) for k, a, b, text in SUBTITLES]
        self.intro = sorted((OUT_DIR / "intro").glob("frame_*.png"))
        self.trash = bv.Clip(bv.TRASH)
        self.trash_end = None
        self.failed = Image.open(bv.FAILED).convert("RGB")
        self.stuck = Image.open(ROOT / "outputs" / "demo" / "20261121_161706" / "attempt02_run1_top.jpg").convert("RGB")
        self.retry1 = Image.open(bv.RETRY / "attempt01_run1_top.jpg").convert("RGB")
        self.retry2 = Image.open(bv.RETRY / "attempt01_run2_top.jpg").convert("RGB")
        starts = sorted((bv.FRAMES / "ds_af51284a6c").glob("ep*_f0000_on_mat.jpg"))
        self.starts = [Image.open(p).convert("RGB").resize((448, 336), Image.LANCZOS) for p in starts[::3]]
        self.var = bv.variation_examples()
        b = bv.battery_angle(np.array(self.retry1))
        self.retry1_battery = b[1] if b else (348, 362)   # measured by eye when the detector misses it

    def intro_frame(self, i: int) -> Image.Image:
        i = max(0, min(len(self.intro) - 1, i))
        return Image.open(self.intro[i]).convert("RGB").resize((W, H)).convert("RGBA")

    # part 1: the battery's journey into the fire --------------------------------------------
    def part1(self, t: float) -> Image.Image:
        e = self.e
        if t < e["p1.viaja"] - 0.25:                       # falls into the kitchen bin
            u = (t - self.part_start[0]) / max(0.1, e["p1.casa_end"] - self.part_start[0])
            return self.intro_frame(int(min(1.0, u) * 52))
        if t < e["p1.aplastarse"]:                          # home -> truck -> plant
            canvas = Image.new("RGBA", (W, H), (*bv.INK, 255))
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            pts = [(360, 470), (960, 470), (1560, 470)]
            stops = [e["p1.viaja"], e["p1.camion"], e["p1.planta"]]
            for x in range(420, 1500, 34):
                d.line([(x, 470), (x + 16, 470)], fill=(90, 96, 108, 255), width=6)
            canvas.alpha_composite(layer)
            names = ("casa", "camión de la basura", "planta de residuos")
            for i, (p, name, s0) in enumerate(zip(pts, names, stops)):
                a = bv.fade(t, s0 - 0.2, 99, 0.25)
                col = (*(bv.CRIMSON if (i == 2 and t >= e["p1.planta"]) else bv.SNOW), int(255 * max(0.25, a)))
                lay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                (icon_house, icon_truck, icon_plant)[i](ImageDraw.Draw(lay), p[0], p[1] - 150, col, 1.0)
                canvas.alpha_composite(lay)
                bv.text(canvas, (p[0], p[1] + 70), name, 40, "semi", fill=bv.MUTED, alpha=max(0.25, a), anchor="mt")
            # the battery travels along
            if t < stops[1]:
                x = pts[0][0] + (pts[1][0] - pts[0][0]) * bv.ease((t - stops[0]) / max(0.1, stops[1] - stops[0]))
            else:
                x = pts[1][0] + (pts[2][0] - pts[1][0]) * bv.ease((t - stops[1]) / max(0.1, stops[2] - stops[1]))
            battery_icon(canvas, x, 470, 1.0, 1.2)
            return canvas
        # crushed, it catches fire (the Blender bin from frame 55 on), then the fact
        if t < e["p1.prende"]:
            u = (t - e["p1.aplastarse"]) / max(0.1, e["p1.prende"] - e["p1.aplastarse"])
            i = int(55 + u * 50)
        else:
            u = (t - e["p1.prende"]) / max(0.1, self.part_start[1] - e["p1.prende"])
            i = int(105 + min(1.0, u) * 134)
        canvas = self.intro_frame(i)
        a = bv.fade(t, e["p1.espana"] - 0.1, self.part_start[1] + 0.1, 0.3)
        if a > 0:
            bv.band(canvas, 90, 330, a)
            bv.accent(canvas, 90, 120, 180, a)
            bv.text(canvas, (125, 115), "España: arde una planta de residuos", 62, "bold", alpha=a)
            bv.text(canvas, (125, 190), "cada 3,5 días", 62, "bold", fill=bv.AMBER, alpha=a)
            bv.text(canvas, (125, 268), "109 incendios en 2023 · Fuente: TECNIFUEGO / IFEMA SICUR", 30, "semi", fill=bv.MUTED, alpha=a)
        return canvas

    # part 2: dangerous by hand, so a robot does it --------------------------------------------
    def part2(self, t: float) -> Image.Image:
        e = self.e
        if t < e["p2.asi"] + 0.6:
            canvas = Image.new("RGBA", (W, H), (*bv.INK, 255))
            a = bv.fade(t, self.part_start[1], e["p2.asi"] + 0.6, 0.25)
            warning_icon(canvas, W // 2, 330, a)
            bv.text(canvas, (W // 2, 560), "Sacarlas a mano es peligroso", 72, "bold", alpha=a, anchor="mt")
            bv.text(canvas, (W // 2, 660), "una batería dañada puede arder sin aviso", 42, "semi", fill=bv.AMBER, alpha=a, anchor="mt")
            return canvas
        if t < e["p2.entre"]:                               # the cluttered table, things named as they are said
            frame = self.trash.frame(0.6)
            canvas = overhead_full(frame)
            zoom_in = bv.fade(t, e["p2.asi"] + 0.6, 99, 0.4)
            canvas = dim(canvas, 0.25 * zoom_in)
            items = [("p2.patitos", "patitos", DUCKS), ("p2.llaves", "llaves", [KEYS]), ("p2.movil", "un móvil", [PHONE]),
                     ("p2.tijeras", "unas tijeras", [SCISSORS])]
            for key, word, spots in items:
                a = bv.fade(t, e[key] - 0.05, 99, 0.2)
                for p in spots:
                    ring(canvas, in_full(p), 62, bv.AMBER, a, 7)
                x, y = in_full(spots[0])
                tag(canvas, (x + 80, y - 70), word, bv.AMBER, a, 40)
            return canvas
        if t < e["p2.bateria"]:                             # it goes straight for the battery: pick and place, sped up
            u = (t - e["p2.entre"]) / max(0.1, e["p2.bateria"] - e["p2.entre"])
            src = 1.5 + 21.5 * u
            frame = self.trash.frame(src)
            canvas = overhead_full(frame)
            bv.paste(canvas, frame.crop((640, 44, 1280, 524)).resize((520, 390), Image.LANCZOS), (W - 560, 40), radius=16,
                     border=bv.SNOW)
            bv.text(canvas, (W - 300, 450), "cámara de la pinza", 28, "semi", anchor="mt")
            ring(canvas, in_full(BATTERY), 70, bv.GREEN, bv.fade(t, e["p2.entre"], e["p2.entre"] + 1.2, 0.2), 8)
            tag(canvas, (60, 70), f"x{max(1, round(21.5 / max(0.1, e['p2.bateria'] - e['p2.entre'])))} velocidad", (60, 64, 74), 1.0, 30)
            return canvas
        frame = self.trash.frame(32.5) if self.trash_end is None else self.trash_end
        self.trash_end = frame
        canvas = overhead_full(frame)
        box_battery = (55, 315)                             # where it lies in the box at the end of the test
        a = bv.fade(t, e["p2.bateria"] - 0.05, 99, 0.2)
        ring(canvas, in_full(box_battery), 80, bv.GREEN, a, 9)
        tag(canvas, (in_full(box_battery)[0] + 110, in_full(box_battery)[1] - 90), "la batería, en su caja", bv.GREEN, a, 44)
        return canvas

    # part 3: it failed, we taught it, now it always works -------------------------------------
    def part3(self, t: float) -> Image.Image:
        e = self.e
        canvas = Image.new("RGBA", (W, H), (*bv.INK, 255))
        if t < e["p3.ensenamos"]:
            a0 = bv.fade(t, self.part_start[2], 99, 0.25)
            bv.text(canvas, (W // 2, 70), "Al principio no le salía", 70, "bold", alpha=a0, anchor="mt")
            cards = [("p3.girada", self.var["turned left"], "batería girada", "ni lo intentaba"),
                     ("p3.cogia", None, "la cogía mal", "se le atascaba")]
            for i, (key, var, title, sub) in enumerate(cards):
                x = 150 + i * 860
                a = bv.fade(t, e[key] - 0.1, 99, 0.25) if t >= self.part_start[2] else 0
                if var is not None:
                    p, b = var
                    img = Image.open(p).convert("RGB")
                    cx, cy = b[1]
                    pic = img.crop((int(cx - 110), int(cy - 82), int(cx + 110), int(cy + 82))).resize((760, 567), Image.LANCZOS)
                else:
                    pic = self.stuck.crop((140, 250, 420, 460)).resize((760, 567), Image.LANCZOS)
                if a <= 0:
                    pic = None
                if pic is not None:
                    bv.paste(canvas, pic, (x, 200), alpha=a, radius=18, border=bv.CRIMSON)
                    bv.text(canvas, (x + 380, 800), "×  " + title, 50, "bold", fill=(255, 120, 120), alpha=a, anchor="mt")
                    bv.text(canvas, (x + 380, 870), sub, 40, "semi", fill=bv.MUTED, alpha=a, anchor="mt")
            return canvas
        if t < e["p3.hoy"]:                                 # taught case by case
            l = t - e["p3.ensenamos"]
            for k in range(12):
                idx = (int(l * 7) + k * 5) % len(self.starts)
                x, y = 60 + (k % 4) * 458, 210 + (k // 4) * 270
                bv.paste(canvas, self.starts[idx].resize((440, 254)), (x, y), radius=10)
            bv.text(canvas, (60, 70), "Le enseñamos justo esos casos", 66, "bold")
            bv.text(canvas, (W - 60, 92), "uno a uno", 44, "semi", fill=bv.AMBER, anchor="rt",
                    alpha=bv.fade(t, e["p3.uno"] - 0.1, 99, 0.25))
            return canvas
        l = t - e["p3.hoy"]                                 # now it always works
        for k in range(12):
            x, y = 60 + (k % 4) * 458, 300 + (k // 4) * 210
            tile = self.starts[(k * 7) % len(self.starts)].resize((440, 198))
            bv.paste(canvas, tile, (x, y), radius=10)
            a = bv.fade(l, 0.25 + k * 0.12, 99, 0.15)
            check_mark(canvas, x + 400, y + 40, 30, a)
        bv.text(canvas, (60, 70), "Hoy acierta en todas las posiciones", 66, "bold")
        bv.text(canvas, (60, 165), "24 / 24", 110, "bold", fill=bv.GREEN, alpha=bv.fade(l, 0.1, 99, 0.25))
        bv.text(canvas, (520, 205), "posiciones · 34 pruebas seguidas, 0 fallos", 44, "semi", fill=bv.SNOW,
                alpha=bv.fade(l, 0.4, 99, 0.25))
        return canvas

    # part 4: it checks its own work, then the close -------------------------------------------
    def part4(self, t: float) -> Image.Image:
        e = self.e
        if t < e["p4.vuelve"]:                              # run 1 failed: it looks at the box
            canvas, s, ox = photo_43(self.retry1)
            canvas = dim(canvas, 0.15)
            tag(canvas, (ox + 30, 60), "Intento 1", bv.AMBER, 1.0, 40)
            if t >= e["p4.mira"] - 0.1:
                l = t - e["p4.mira"]
                x0, y0, x1, y1 = (ox + BOX[0] * s, BOX[1] * s, ox + BOX[2] * s, BOX[3] * s)
                layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                d.rectangle((x0, y0, x1, y1), outline=(*bv.SNOW, 255), width=6)
                scan = y0 + (y1 - y0) * ((l * 1.2) % 1.0)
                d.line([(x0, scan), (x1, scan)], fill=(*bv.SNOW, 180), width=5)
                canvas.alpha_composite(layer)
                tag(canvas, (x1 + 30, y0 + 40), "¿en la caja? no", bv.SNOW, bv.fade(l, 0.6, 99, 0.2), 38)
                if self.retry1_battery is not None:
                    bx, by = self.retry1_battery
                    a = bv.fade(l, 1.4, 99, 0.2)
                    ring(canvas, (int(ox + bx * s), int(by * s)), 75, bv.AMBER, a, 8)
                    tag(canvas, (int(ox + bx * s) + 100, int(by * s) - 110), "sigue ahí", bv.AMBER, a, 40)
            return canvas
        if t < e["p4.solo"]:                                # so it tries again: run 2 in the box
            canvas, s, ox = photo_43(self.retry2)
            tag(canvas, (ox + 30, 60), "Intento 2", bv.GREEN, 1.0, 40)
            ring(canvas, (int(ox + 75 * s), int(330 * s)), 85, bv.GREEN, bv.fade(t, e["p4.vuelve"] + 0.4, 99, 0.2), 9)
            tag(canvas, (int(ox + 75 * s) + 110, int(330 * s) - 120), "en la caja", bv.GREEN,
                bv.fade(t, e["p4.vuelve"] + 0.4, 99, 0.2), 44)
            return canvas
        if t < e["p4.equipo"] - 0.2:                        # alone, offline, hands off
            frame = self.trash_end or self.trash.frame(32.5)
            canvas = dim(overhead_full(frame), 0.62)
            for i, (key, word) in enumerate((("p4.solo", "Solo."), ("p4.internet", "Sin internet."),
                                             ("p4.nadie", "Sin que nadie meta la mano."))):
                bv.text(canvas, (W // 2, 270 + i * 170), word, 96, "bold", alpha=bv.fade(t, self.e[key] - 0.08, 99, 0.2),
                        anchor="mm", fill=bv.SNOW if i < 2 else bv.GREEN)
            return canvas
        canvas = Image.new("RGBA", (W, H), (*bv.INK, 255))   # the close
        a = bv.fade(t, e["p4.equipo"] - 0.2, 99, 0.35)
        bv.text(canvas, (W // 2, 300), "el equipo de", 46, "semi", fill=bv.MUTED, alpha=a, anchor="mm")
        bv.text(canvas, (W // 2, 400), "CrimsonSnow", 130, "bold", alpha=a, anchor="mm")
        bv.accent(canvas, W // 2 - 170, 485, 6, a, w=340)
        b = bv.fade(t, e["p4.para"] - 0.1, 99, 0.35)
        bv.text(canvas, (W // 2, 590), "para que ninguna batería acabe en el fuego", 54, "bold", fill=bv.AMBER, alpha=b, anchor="mm")
        bv.text(canvas, (W // 2, 700), "24 / 24 posiciones · sin tocarlo · sin internet", 38, "semi", fill=bv.GREEN, alpha=b, anchor="mm")
        bv.text(canvas, (W // 2, 860), "github.com/SO-101-Hackathon/CrimsonSnow", 34, "semi", fill=bv.MUTED, alpha=b, anchor="mm")
        return canvas

    def frame(self, t: float) -> Image.Image:
        if t >= self.part_start[3]:
            img = self.part4(t)
        elif t >= self.part_start[2]:
            img = self.part3(t)
        elif t >= self.part_start[1]:
            img = self.part2(t)
        else:
            img = self.part1(t)
        img = img.convert("RGBA")
        for a, b, text in self.subs:
            if a - 0.1 <= t <= b + 0.35:
                subtitle(img, text, min(1.0, bv.fade(t, a - 0.1, b + 0.35, 0.15)))
                break
        for cut in self.part_start[1:]:
            d = abs(t - cut)
            if d < 0.1:
                img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - d / 0.1)))))
        return img.convert("RGB")


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=str(OUT_DIR / "CrimsonSnow-1min-ES-voz.mp4"))
    p.add_argument("--stills", nargs="*", type=float, help="only save these times as JPG next to --out")
    args = p.parse_args()
    bv.LANG = "es"
    vo = VoiceOver()
    story = Story(vo)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"voice-over: {vo.length:.1f} s of speech after cutting pauses, sped up x{vo.speed:.3f} to end at {VO_END} s")
    print("parts start at " + ", ".join(f"{s:.1f} s" for s in story.part_start))
    if args.stills:
        for t in sorted(args.stills):
            story.frame(t).save(out.with_name(f"story_{t:05.1f}.jpg"), quality=86)
        return 0
    audio = vo.write(OUT_DIR / "vo_final.wav")
    silent = out.with_name(out.stem + "_video.mp4")
    container = av.open(str(silent), "w")
    stream = container.add_stream("libx264", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = W, H, "yuv420p"
    stream.options = {"crf": "18", "preset": "medium"}
    for i in range(int(DURATION * FPS)):
        frame = av.VideoFrame.from_ndarray(np.asarray(story.frame(i / FPS)), format="rgb24")
        frame.pts, frame.time_base = i, Fraction(1, FPS)
        for packet in stream.encode(frame):
            container.mux(packet)
        if i % 300 == 0:
            print(f"{i / FPS:5.1f} s", flush=True)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(silent), "-i", str(audio), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-t", str(DURATION), "-movflags", "+faststart", str(out)], check=True)
    silent.unlink(missing_ok=True)
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
