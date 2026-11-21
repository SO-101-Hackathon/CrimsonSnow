"""Our own camera check for `so demo`: a small vision model that says where the battery is.

Instead of sending the overhead photo to Claude or OpenAI, `so demo --check local` (or
RETRY_CHECK=local in .env) asks a model trained on this laptop from our own recordings: no
internet, no API key, an answer in milliseconds.

    so vision prepare   copy a recorded dataset and cut labelled frames out of its videos
    so vision train     fine-tune ResNet-18 (ImageNet weights) on those frames, on the GPU
    so vision test      score it on episodes it never saw and on real check photos
    so vision check PHOTO [PHOTO ...]   where is the battery in these photos?

Labels without anyone drawing boxes: every recording starts with the battery on the mat and
ends with it in the box, and the gripper position stored with every frame says when the
battery was grabbed and when it was let go:

    on_mat      from the start until the gripper begins to close on the battery
    in_gripper  while the gripper holds it (stopped part-way while told to close)
    in_box      from 1 s after the gripper opened again until the end of the episode

Every fifth episode is kept out of training and only used to measure accuracy.

The model only answers "in the box" when it is at least 80 % sure (a wrong "in the box" would
end a demo attempt that actually failed); "on the mat" / "in the gripper" need 60 % (a wrong
one only costs an extra run). Below that it says it is unsure and `so demo` falls back to the
gripper reading, exactly as without a camera check.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import shutil
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .demo import (CLOSE_DROP, GRIP_EMPTY, GRIP_OPEN, HOLD_MAX, HOLD_MIN, HOLD_SECONDS, HOLD_WOBBLE,
                   CheckFailed, camera_role)

ROOT = Path(__file__).resolve().parent.parent
VISION_DIR = ROOT / "outputs" / "vision"          # git-ignored, like every other training output
CACHE_DIR = VISION_DIR / "cache"                  # copies of the datasets we learn from
FRAMES_DIR = VISION_DIR / "frames"                # labelled frames + index.csv
INDEX_CSV = FRAMES_DIR / "index.csv"
DEFAULT_MODEL = VISION_DIR / "model" / "battery_check.pt"
REAL_LABELS = VISION_DIR / "real_checks.csv"      # real check photos labelled by eye (see `test`)
REPORT = ROOT / "journal" / "vision-report.md"    # the evidence for the jury

CLASSES = ("in_box", "on_mat", "in_gripper")      # same words as demo.LOCATIONS
IMAGE_SIZE = (448, 336)                           # width, height: the 640 x 480 overhead picture at 70 %
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)  # ImageNet statistics
BOX_MIN = 0.80     # "in the box" only when this sure: a wrong one ends a failed attempt as a success
OTHER_MIN = 0.60   # "on the mat" / "in the gripper": a wrong one only costs one more run
VAL_EVERY = 5      # episodes 4, 9, 14, ... are never trained on
PICKS = {"on_mat": 6, "in_gripper": 4, "in_box": 6}  # frames per episode and label
REST_DEG = 12.0    # arm counts as folded at rest within this many degrees of its start pose
WORDS = {"in_box": "in the box", "on_mat": "on the mat", "in_gripper": "in the gripper"}


# ----------------------------------------------------------------------------- labels (pure)
@dataclass
class Grab:
    closing: int   # frame where the gripper starts to close (its widest opening)
    held: int      # first frame of the steady hold: something is in the jaws
    released: int  # first frame where it has opened again


def grabs(grip: list[float], fps: float = 30.0) -> list[Grab]:
    """Every grab that held something and then let it go, from per-frame gripper positions
    (0 closed .. 100 open). Same thresholds as the live check in sokit/demo.py."""
    need = max(2, round(HOLD_SECONDS * fps))
    found: list[Grab] = []
    state, peak, peak_i, low, level = "closed", 0.0, 0, 0.0, 0.0
    closing = held = 0
    window: list[tuple[int, float]] = []
    for i, raw in enumerate(grip):
        g = float(raw)
        if state == "closed":
            if g >= GRIP_OPEN:
                state, peak, peak_i = "open", g, i
        elif state == "open":
            if g >= peak:
                peak, peak_i = g, i
            elif g <= peak - CLOSE_DROP:
                state, closing, low, window = "closing", peak_i, g, []
        elif state == "closing":
            low = min(low, g)
            if g >= GRIP_OPEN and g >= low + CLOSE_DROP:  # opened again before holding: a new grab
                state, peak, peak_i = "open", g, i
                continue
            if not HOLD_MIN <= g <= HOLD_MAX:
                window = []
                if g <= GRIP_EMPTY:                       # closed on nothing: wait for the next opening
                    state = "closed"
                continue
            window.append((i, g))
            while max(v for _, v in window) - min(v for _, v in window) > HOLD_WOBBLE:
                window.pop(0)
            if len(window) >= need:
                held, level, state = window[0][0], max(v for _, v in window), "holding"
        elif state == "holding":
            if g >= max(GRIP_OPEN, level + CLOSE_DROP):   # let go
                found.append(Grab(closing, held, i))
                state, peak, peak_i = "open", g, i
    return found


@dataclass
class EpisodeLabels:
    ranges: dict[str, tuple[int, int]]  # label -> (first frame, last frame), both included
    released: int                        # frame where the battery was let go into the box


def episode_labels(grip: list[float], fps: float = 30.0) -> EpisodeLabels | None:
    """Frame ranges per label for one recorded (successful) episode, or None when unclear."""
    found = grabs(grip, fps)
    if not found:
        return None
    first, last, n = found[0], found[-1], len(grip)
    sec = lambda s: round(s * fps)  # noqa: E731
    ranges = {
        "on_mat": (0, first.closing - sec(0.2)),                        # nothing has touched it yet
        "in_gripper": (last.held + sec(0.3), last.released - sec(0.3)),  # carried to the box
        "in_box": (last.released + sec(1.0), n - 1),                    # dropped and settled
    }
    ranges = {k: v for k, v in ranges.items() if v[1] >= v[0]}
    if "on_mat" not in ranges or "in_box" not in ranges:
        return None
    return EpisodeLabels(ranges, last.released)


def spread(first: int, last: int, k: int) -> list[int]:
    """k frame numbers spread evenly over first..last, both ends included."""
    if k <= 0 or last < first:
        return []
    if last - first + 1 <= k:
        return list(range(first, last + 1))
    if k == 1:
        return [last]
    return sorted({round(first + j * (last - first) / (k - 1)) for j in range(k)})


def split_of(episode: int) -> str:
    return "val" if episode % VAL_EVERY == VAL_EVERY - 1 else "train"


def decide_location(probs: dict[str, float]) -> tuple[str | None, str]:
    """(location, or None when unsure; the probabilities in words) from the model's output."""
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    text = ", ".join(f"{WORDS.get(k, k)} {v:.0%}" for k, v in ranked)
    best, p = ranked[0]
    if best == "in_box" and p >= BOX_MIN:
        return "in_box", text
    if best != "in_box" and p >= OTHER_MIN:
        return best, text
    return None, text


# ----------------------------------------------------------------------------- datasets
def sensecraft_datasets(root: Path | None = None) -> list[dict]:
    """Datasets SenseCraft has on this computer (read only), newest first."""
    from . import sensecraft

    root = root or sensecraft.data_root()
    if root is None:
        return []
    found = []
    for state_file in root.glob("projects/*/datasets/*/state.json"):
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            info = json.loads((state_file.parent / "meta" / "info.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if state.get("status") != "ready" or not info.get("total_episodes"):
            continue
        found.append({"id": state_file.parent.name, "name": str(state.get("dataset_name") or state_file.parent.name),
                      "path": state_file.parent, "episodes": int(info["total_episodes"]),
                      "updated": str(state.get("updated_at") or "")})
    return sorted(found, key=lambda d: d["updated"], reverse=True)


def pick_sensecraft_dataset(name: str | None, root: Path | None = None) -> dict:
    """The dataset named `name` (exact, else contains), or by default the one with most episodes
    (the merged dataset SenseCraft trains on)."""
    found = sensecraft_datasets(root)
    if not found:
        raise SystemExit("[vision] No SenseCraft dataset found on this computer (pass --dataset FOLDER or --repo-id).")
    if not name:
        return max(found, key=lambda d: d["episodes"])
    exact = [d for d in found if d["name"].lower() == name.lower()]
    matches = exact or [d for d in found if name.lower() in d["name"].lower()]
    if not matches:
        listing = "\n".join(f"   {d['name']}  ({d['episodes']} episodes)" for d in found)
        raise SystemExit(f"[vision] No SenseCraft dataset named like '{name}'. On this computer:\n{listing}")
    return matches[0]


def scene_camera_key(info: dict, wanted: str | None = None) -> str:
    """The overhead camera's feature key, e.g. observation.images.front (SenseCraft) or .top (ours)."""
    keys = [k for k, v in info.get("features", {}).items() if v.get("dtype") == "video"]
    if wanted:
        key = wanted if wanted.startswith("observation.images.") else f"observation.images.{wanted}"
        if key not in keys:
            raise SystemExit(f"[vision] camera '{wanted}' is not in this dataset ({keys})")
        return key
    for key in keys:
        if camera_role(key.rsplit(".", 1)[-1]) == "scene":
            return key
    raise SystemExit(f"[vision] no overhead camera among {keys}: pass --camera NAME")


def copy_dataset(src: Path, dest: Path, camera_key: str) -> Path:
    """Copy what the labels need (metadata, joint positions, one camera's videos) out of `src`.
    Decoding takes minutes; working on a copy keeps the source files (e.g. SenseCraft's) closed."""
    copied = 0
    for part in (src / "meta", src / "data", src / "videos" / camera_key):
        for f in sorted(part.rglob("*")):
            if not f.is_file():
                continue
            out = dest / f.relative_to(src)
            if out.is_file() and out.stat().st_size == f.stat().st_size:
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            copied += f.stat().st_size
    print(f"[vision] copied {copied / 1e6:.0f} MB into {_rel(dest)}", flush=True)
    return dest


def hub_dataset(repo_id: str, camera: str | None) -> Path:
    """Download (once) the parts of a Hub dataset the labels need."""
    from huggingface_hub import hf_hub_download, snapshot_download

    info = json.loads(Path(hf_hub_download(repo_id, "meta/info.json", repo_type="dataset")).read_text(encoding="utf-8"))
    key = scene_camera_key(info, camera)
    return Path(snapshot_download(repo_id, repo_type="dataset",
                                  allow_patterns=["meta/*", "meta/**", "data/**", f"videos/{key}/**"]))


# ----------------------------------------------------------------------------- frames
def plan_frames(dataset_dir: Path, tag: str, camera: str | None = None) -> tuple[list[dict], dict[Path, dict[int, dict]], dict]:
    """Which frames to cut out and their labels: (index rows, {video file: {frame number: row}}, stats)."""
    import numpy as np
    import pandas as pd

    info = json.loads((dataset_dir / "meta" / "info.json").read_text(encoding="utf-8"))
    fps = float(info["fps"])
    key = scene_camera_key(info, camera)
    names = list(info["features"]["observation.state"]["names"])
    gi, li, ei, pi = (names.index(n) for n in ("gripper.pos", "shoulder_lift.pos", "elbow_flex.pos", "shoulder_pan.pos"))
    episodes = pd.concat([pd.read_parquet(p) for p in sorted((dataset_dir / "meta" / "episodes").rglob("*.parquet"))])
    data = pd.concat([pd.read_parquet(p, columns=["episode_index", "frame_index", "observation.state"])
                      for p in sorted((dataset_dir / "data").rglob("*.parquet"))])
    states = {int(e): np.stack(g.sort_values("frame_index")["observation.state"].to_numpy())
              for e, g in data.groupby("episode_index")}

    labelled: list[tuple[pd.Series, EpisodeLabels]] = []
    skipped: list[str] = []
    for _, ep in episodes.sort_values("episode_index").iterrows():
        e = int(ep["episode_index"])
        st = states.get(e)
        labels = episode_labels(st[:, gi].tolist(), fps) if st is not None else None
        if labels is None:
            skipped.append(f"episode {e}: no grab-and-release in the gripper trace")
            continue
        labelled.append((ep, labels))

    # The battery must have been let go over the box: same arm direction in every episode.
    pans = {int(ep["episode_index"]): float(states[int(ep["episode_index"])][lab.released, pi]) for ep, lab in labelled}
    median_pan = float(np.median(list(pans.values()))) if pans else 0.0
    rows: list[dict] = []
    wanted: dict[Path, dict[int, dict]] = {}
    vk = f"videos/{key}"
    for ep, lab in labelled:
        e = int(ep["episode_index"])
        if abs(pans[e] - median_pan) > 25:
            skipped.append(f"episode {e}: let go {pans[e] - median_pan:+.0f} deg away from the box direction")
            continue
        st = states[e]
        home = st[0]
        video = dataset_dir / info["video_path"].format(video_key=key, chunk_index=int(ep[f"{vk}/chunk_index"]),
                                                        file_index=int(ep[f"{vk}/file_index"]))
        t0 = float(ep[f"{vk}/from_timestamp"])
        for label, (a, b) in lab.ranges.items():
            for k in spread(a, b, PICKS[label]):
                away = max(abs(st[k, li] - home[li]), abs(st[k, ei] - home[ei]))
                row = {"path": f"{tag}/ep{e:04d}_f{k:04d}_{label}.jpg", "label": label, "dataset": tag,
                       "episode": e, "frame": k, "rest": int(away <= REST_DEG), "split": split_of(e)}
                rows.append(row)
                wanted.setdefault(video, {})[round((t0 + k / fps) * fps)] = row
    stats = {"fps": fps, "camera": key, "episodes": len(episodes), "labelled": len({r["episode"] for r in rows}),
             "skipped": skipped, "box_direction_deg": round(median_pan, 1)}
    return rows, wanted, stats


def cut_frames(wanted: dict[Path, dict[int, dict]], fps: float) -> int:
    """Decode each video once, front to back, and save the wanted frames as JPEG."""
    import av

    saved = 0
    for video, by_number in wanted.items():
        todo = {n: r for n, r in by_number.items() if not (FRAMES_DIR / r["path"]).is_file()}
        if not todo:
            continue
        last = max(todo)
        print(f"[vision] {video.name}: {len(todo)} frames to cut", flush=True)
        with av.open(str(video)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            for frame in container.decode(stream):
                if frame.time is None:
                    continue
                n = round(frame.time * fps)
                row = todo.pop(n, None)
                if row is not None:
                    out = FRAMES_DIR / row["path"]
                    out.parent.mkdir(parents=True, exist_ok=True)
                    frame.to_image().save(out, quality=92)
                    saved += 1
                if not todo or n > last:
                    break
        if todo:
            print(f"[vision]   {len(todo)} frames were not found in {video.name}", flush=True)
    return saved


def read_index() -> list[dict]:
    if not INDEX_CSV.is_file():
        raise SystemExit("[vision] No labelled frames yet: run  so vision prepare")
    with open(INDEX_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if (FRAMES_DIR / r["path"]).is_file()]


def write_index(rows: list[dict], replace_tag: str) -> None:
    old = []
    if INDEX_CSV.is_file():
        with open(INDEX_CSV, newline="", encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r["dataset"] != replace_tag]
    INDEX_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "label", "dataset", "episode", "frame", "rest", "split"])
        w.writeheader()
        w.writerows(old + rows)


def cmd_prepare(args) -> int:
    if args.dataset:
        src, tag = Path(args.dataset).expanduser().resolve(), Path(args.dataset).name
        info = json.loads((src / "meta" / "info.json").read_text(encoding="utf-8"))
        key = scene_camera_key(info, args.camera)
        work = src if args.no_copy else copy_dataset(src, CACHE_DIR / tag, key)
    elif args.repo_id:
        work, tag = hub_dataset(args.repo_id, args.camera), args.repo_id.replace("/", "__")
    else:
        ds = pick_sensecraft_dataset(args.sensecraft)
        tag = ds["id"]
        print(f"[vision] SenseCraft dataset '{ds['name']}' ({ds['episodes']} episodes), read only", flush=True)
        info = json.loads((ds["path"] / "meta" / "info.json").read_text(encoding="utf-8"))
        work = copy_dataset(ds["path"], CACHE_DIR / tag, scene_camera_key(info, args.camera))
    rows, wanted, stats = plan_frames(work, tag, args.camera)
    print(f"[vision] {stats['labelled']}/{stats['episodes']} episodes labelled from the gripper trace; "
          f"camera {stats['camera']}; box direction {stats['box_direction_deg']} deg", flush=True)
    for line in stats["skipped"]:
        print(f"[vision]   skipped {line}", flush=True)
    t0 = time.monotonic()
    saved = cut_frames(wanted, stats["fps"])
    write_index(rows, tag)
    counts = Counter((r["split"], r["label"]) for r in rows)
    print(f"[vision] {saved} new frames in {time.monotonic() - t0:.0f} s; {len(rows)} labelled frames for {tag}:", flush=True)
    for split in ("train", "val"):
        print(f"[vision]   {split}: " + ", ".join(f"{c} {counts[(split, c)]}" for c in CLASSES), flush=True)
    print(f"[vision] next:  so vision train", flush=True)
    return 0


# ----------------------------------------------------------------------------- the model (torch)
def _device(prefer: str | None = None) -> str:
    import torch

    if prefer:
        return prefer
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def build_model(pretrained: bool = True):
    import torch.nn as nn
    from torchvision.models import ResNet18_Weights, resnet18

    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
    model.fc = nn.Linear(model.fc.in_features, len(CLASSES))
    return model


def eval_transform():
    import torch
    from torchvision.transforms import v2

    w, h = IMAGE_SIZE
    return v2.Compose([v2.PILToTensor(), v2.Resize((h, w), antialias=True),
                       v2.ToDtype(torch.float32, scale=True), v2.Normalize(MEAN, STD)])


def train_transform():
    """Small changes the venue can bring: light, a nudged camera, blur, something in the way.
    No mirroring: the box is always on the left."""
    import torch
    from torchvision.transforms import v2

    w, h = IMAGE_SIZE
    return v2.Compose([
        v2.PILToTensor(),
        v2.RandomResizedCrop((h, w), scale=(0.9, 1.0), ratio=(1.28, 1.38), antialias=True),
        v2.RandomRotation(4),
        v2.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.03),
        v2.RandomApply([v2.GaussianBlur(5, sigma=(0.1, 1.5))], p=0.2),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(MEAN, STD),
        v2.RandomErasing(p=0.25, scale=(0.01, 0.04), value=0),
    ])


class FrameSet:
    """Labelled frames for torch's DataLoader (module level so Windows' spawned workers can load it)."""

    def __init__(self, rows: list[dict], train: bool):
        self.rows, self.train = rows, train
        self.tf = None

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, i: int):
        from PIL import Image

        if self.tf is None:
            self.tf = train_transform() if self.train else eval_transform()
        row = self.rows[i]
        with Image.open(FRAMES_DIR / row["path"]) as img:
            x = self.tf(img.convert("RGB"))
        return x, CLASSES.index(row["label"])


def _predict(model, loader, device: str) -> list[list[float]]:
    import torch

    probs: list[list[float]] = []
    model.eval()
    with torch.no_grad():
        for x, _ in loader:
            x = x.to(device, non_blocking=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
                out = model(x)
            probs += torch.softmax(out.float(), dim=1).cpu().tolist()
    return probs


def scores(rows: list[dict], probs: list[list[float]]) -> dict:
    """Accuracy, confusion and what the demo would do with these answers."""
    conf = {t: {p: 0 for p in CLASSES} for t in CLASSES}
    out = {"frames": len(rows), "correct": 0, "rest_frames": 0, "rest_correct": 0,
           "false_box": 0, "missed_box": 0, "unsure": 0}
    for row, p in zip(rows, probs):
        pred = CLASSES[max(range(len(CLASSES)), key=lambda i: p[i])]
        conf[row["label"]][pred] += 1
        ok = pred == row["label"]
        out["correct"] += ok
        if str(row.get("rest")) == "1":
            out["rest_frames"] += 1
            out["rest_correct"] += ok
        location, _ = decide_location(dict(zip(CLASSES, p)))
        if location is None:
            out["unsure"] += 1
        elif location == "in_box" and row["label"] != "in_box":
            out["false_box"] += 1
        elif location != "in_box" and row["label"] == "in_box":
            out["missed_box"] += 1
    out["accuracy"] = out["correct"] / max(1, out["frames"])
    out["rest_accuracy"] = out["rest_correct"] / max(1, out["rest_frames"])
    out["confusion"] = conf
    return out


def cmd_train(args) -> int:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader

    rows = read_index()
    train_rows = [r for r in rows if r["split"] == "train"]
    val_rows = [r for r in rows if r["split"] == "val"]
    if not train_rows or not val_rows:
        raise SystemExit("[vision] need labelled frames in both splits: run  so vision prepare")
    device = _device(args.device)
    torch.manual_seed(args.seed)
    model = build_model().to(device)
    counts = Counter(r["label"] for r in train_rows)
    weights = torch.tensor([len(train_rows) / (len(CLASSES) * max(1, counts[c])) for c in CLASSES], dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=weights.to(device), label_smoothing=0.05)
    workers = args.workers
    pin = device == "cuda"
    train_dl = DataLoader(FrameSet(train_rows, True), batch_size=args.batch_size, shuffle=True, drop_last=True,
                          num_workers=workers, pin_memory=pin, persistent_workers=workers > 0)
    val_dl = DataLoader(FrameSet(val_rows, False), batch_size=64, num_workers=workers, pin_memory=pin,
                        persistent_workers=workers > 0)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * len(train_dl),
                                                pct_start=0.15)
    print(f"[vision] training ResNet-18 on {device}: {len(train_rows)} frames "
          f"({', '.join(f'{c} {counts[c]}' for c in CLASSES)}), checking on {len(val_rows)} frames "
          f"of {len({(r['dataset'], r['episode']) for r in val_rows})} episodes it never sees", flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    best, t_start = -1.0, time.monotonic()
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, total, seen = time.monotonic(), 0.0, 0
        for x, y in train_dl:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
                loss = loss_fn(model(x), y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            total, seen = total + loss.item() * len(y), seen + len(y)
        s = scores(val_rows, _predict(model, val_dl, device))
        print(f"[vision] epoch {epoch}/{args.epochs}: loss {total / max(1, seen):.3f} | unseen episodes: "
              f"{s['accuracy']:.1%} right ({s['correct']}/{s['frames']}), arm at rest {s['rest_accuracy']:.1%}, "
              f"wrong 'in the box' {s['false_box']}, unsure {s['unsure']} | {time.monotonic() - t0:.0f} s", flush=True)
        key = s["accuracy"] - 0.01 * s["false_box"]
        if key > best:
            best = key
            meta = {"arch": "resnet18", "classes": list(CLASSES), "image_size": list(IMAGE_SIZE),
                    "mean": list(MEAN), "std": list(STD), "box_min": BOX_MIN, "other_min": OTHER_MIN,
                    "trained": dt.datetime.now().isoformat(timespec="seconds"), "epoch": epoch,
                    "epochs": args.epochs, "device": device,
                    "datasets": sorted({r["dataset"] for r in rows}),
                    "train_frames": len(train_rows), "val_frames": len(val_rows),
                    "val": {k: v for k, v in s.items() if k != "confusion"}, "val_confusion": s["confusion"]}
            torch.save({"state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()}, "meta": meta}, out)
            out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[vision] done in {(time.monotonic() - t_start) / 60:.1f} min; best model saved to {_rel(out)}", flush=True)
    print("[vision] next:  so vision test", flush=True)
    return 0


class LocalChecker:
    """Loads the trained model once and answers per photo."""

    _cache: dict[str, "LocalChecker"] = {}

    def __init__(self, path: Path, device: str | None = None):
        import torch

        blob = torch.load(path, map_location="cpu", weights_only=True)
        self.meta = blob["meta"]
        self.classes = tuple(self.meta["classes"])
        self.device = _device(device or os.environ.get("LOCAL_CHECK_DEVICE") or None)
        self.model = build_model(pretrained=False)
        self.model.load_state_dict(blob["state_dict"])
        self.model.eval().to(self.device)
        self.tf = eval_transform()

    @classmethod
    def load(cls, path: str | Path | None = None) -> "LocalChecker":
        p = resolve_model(path)
        if not p.is_file():
            raise CheckFailed(f"no trained model at {_rel(p)} (run: so vision prepare, then so vision train)")
        key = str(p)
        if key not in cls._cache:
            cls._cache[key] = cls(p)
        return cls._cache[key]

    def probabilities(self, image) -> dict[str, float]:
        """image: JPEG/PNG bytes, a file path, a PIL image or an RGB array (H x W x 3, uint8)."""
        import torch
        from PIL import Image

        if isinstance(image, (bytes, bytearray)):
            img = Image.open(io.BytesIO(image))
        elif isinstance(image, (str, Path)):
            img = Image.open(image)
        elif isinstance(image, Image.Image):
            img = image
        else:
            img = Image.fromarray(image)
        x = self.tf(img.convert("RGB")).unsqueeze(0).to(self.device)
        with torch.no_grad():
            p = torch.softmax(self.model(x).float(), dim=1)[0].cpu().tolist()
        return dict(zip(self.classes, p))


def resolve_model(path: str | Path | None = None) -> Path:
    p = Path(path or os.environ.get("LOCAL_CHECK_MODEL") or DEFAULT_MODEL).expanduser()
    return p if p.is_absolute() else ROOT / p


def available(path: str | Path | None = None) -> bool:
    """True when a trained model file exists and torch can be imported."""
    import importlib.util

    return resolve_model(path).is_file() and importlib.util.find_spec("torch") is not None


def verdict(scene_jpeg: bytes, model_path: str | Path | None = None) -> dict:
    """Same answer format as demo.ask_claude / ask_openai. Raises CheckFailed when unsure, so the
    demo falls back to the gripper reading."""
    probs = LocalChecker.load(model_path).probabilities(scene_jpeg)
    location, text = decide_location(probs)
    if location is None:
        raise CheckFailed(f"our model is unsure ({text})")
    return {"explanation": text, "battery_location": location, "other_objects_in_box": []}


# ----------------------------------------------------------------------------- test / check
def read_real_labels(path: Path = REAL_LABELS) -> list[dict]:
    """Real check photos labelled by eye: photo (relative to the repo), label, hands (1 = a person's
    hand is in the picture, which never happens in the recordings)."""
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if (ROOT / r["photo"]).is_file()]


def cmd_test(args) -> int:
    import torch
    from torch.utils.data import DataLoader

    checker = LocalChecker.load(args.model)
    meta = checker.meta
    lines = [f"# Local camera check: test report", "",
             f"Model `{_rel(resolve_model(args.model))}` (ResNet-18, trained {meta['trained']}, epoch {meta['epoch']}"
             f" of {meta['epochs']}, on {meta['train_frames']} frames from {', '.join(meta['datasets'])}).",
             f"It answers *in the box* only when at least {BOX_MIN:.0%} sure and *on the mat* / *in the gripper* "
             f"when at least {OTHER_MIN:.0%} sure; otherwise the demo falls back to the gripper reading.", ""]

    rows = [r for r in read_index() if r["split"] == "val"]
    if rows:
        loader = DataLoader(FrameSet(rows, False), batch_size=64, num_workers=0)
        s = scores(rows, _predict(checker.model, loader, checker.device))
        eps = len({(r["dataset"], r["episode"]) for r in rows})
        lines += ["## Episodes it never saw", "",
                  f"{s['frames']} frames from {eps} recorded episodes (every fifth episode, never trained on).", "",
                  "| | frames | right |", "|---|---:|---:|",
                  f"| all frames | {s['frames']} | {s['accuracy']:.1%} |",
                  f"| arm folded at rest (what the demo sees) | {s['rest_frames']} | {s['rest_accuracy']:.1%} |", "",
                  f"What the demo would do: wrong *in the box* (a failed attempt counted as success): **{s['false_box']}**; "
                  f"missed *in the box* (one extra run): {s['missed_box']}; unsure (falls back to the gripper): {s['unsure']}.", "",
                  "Confusion (rows = truth, columns = answer):", "",
                  "| truth \\ answer | " + " | ".join(CLASSES) + " |", "|---|" + "---:|" * len(CLASSES)]
        lines += [f"| {t} | " + " | ".join(str(s["confusion"][t][p]) for p in CLASSES) + " |" for t in CLASSES]
        lines.append("")

    real = read_real_labels(Path(args.labels) if args.labels else REAL_LABELS)
    if real:
        lines += ["## Real check photos from `so demo` runs", "",
                  "Taken by `so demo` after real runs on 21 Nov 2026 (labelled by eye). In some a person's hand is in "
                  "the picture: the recordings never show hands, so those are harder than a real demo.", "",
                  "| photo | truth | hands | answer | probabilities |", "|---|---|---|---|---|"]
        tally = Counter()
        for r in real:
            probs = checker.probabilities(ROOT / r["photo"])
            location, text = decide_location(probs)
            answer = location or "unsure"
            hands = r.get("hands") == "1"
            if r["label"] in CLASSES:
                right = answer == r["label"]
            else:  # 'elsewhere' (held by a person, fell off) or 'hidden': anything but "in the box" is fine
                right = answer != "in_box"
            group = "hands" if hands else "clean"
            tally[(group, "n")] += 1
            tally[(group, "right")] += right
            tally[(group, "unsure")] += answer == "unsure"
            tally["false_box"] += answer == "in_box" and r["label"] != "in_box"
            lines.append(f"| {Path(r['photo']).parent.name}/{Path(r['photo']).stem} | {r['label']} | {'yes' if hands else ''} | "
                         f"{answer}{'' if right else ' ✗'} | {text} |")
        lines += ["", "*elsewhere* / *hidden*: the battery is not in the box, so any answer but *in the box* is fine.", "",
                  f"Without hands: {tally[('clean', 'right')]}/{tally[('clean', 'n')]} right. With a hand in the picture: "
                  f"{tally[('hands', 'right')]}/{tally[('hands', 'n')]} right ({tally[('hands', 'unsure')]} unsure, which "
                  f"falls back to the gripper). Wrong *in the box* answers: **{tally['false_box']}**.", ""]

    if rows:
        picture = sample_grid(checker, rows, VISION_DIR / "samples.jpg")
        lines += [f"Sample answers on unseen episodes: `{_rel(picture)}`.", ""]

    # speed, on this computer
    from PIL import Image

    img = Image.new("RGB", (640, 480), (90, 90, 90))
    checker.probabilities(img)
    t0 = time.perf_counter()
    for _ in range(20):
        checker.probabilities(img)
    ms = (time.perf_counter() - t0) / 20 * 1000
    gpu = torch.cuda.get_device_name(0) if checker.device == "cuda" else checker.device
    lines += ["## Speed", "", f"{ms:.0f} ms per photo on {gpu} (the online checks took about 1-3 s).", ""]
    text = "\n".join(lines)
    print(text)
    if not args.no_save:
        REPORT.parent.mkdir(exist_ok=True)
        REPORT.write_text(text + "\n", encoding="utf-8")
        print(f"\n[vision] report saved to {_rel(REPORT)}")
    return 0


def sample_grid(checker: LocalChecker, rows: list[dict], out: Path, per_class: int = 3, seed: int = 3) -> Path:
    """A picture of the model's answers on unseen frames (arm at rest first): green = right, red = wrong."""
    import random

    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.load_default(size=17)  # Pillow >= 10.1
    except TypeError:
        font = ImageFont.load_default()
    rng = random.Random(seed)
    picked: list[dict] = []
    for label in CLASSES:
        pool = [r for r in rows if r["label"] == label]
        rest = [r for r in pool if str(r.get("rest")) == "1"]
        picked += rng.sample(rest if len(rest) >= per_class else pool, min(per_class, len(pool)))
    w, h, bar = 320, 240, 30
    cols = len(CLASSES)
    sheet = Image.new("RGB", (cols * w, per_class * (h + bar)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, r in enumerate(picked):
        probs = checker.probabilities(FRAMES_DIR / r["path"])
        location, _ = decide_location(probs)
        answer = location or "unsure"
        x, y = (i // per_class) * w, (i % per_class) * (h + bar)
        with Image.open(FRAMES_DIR / r["path"]) as img:
            sheet.paste(img.convert("RGB").resize((w, h)), (x, y + bar))
        color = (22, 130, 60) if answer == r["label"] else (200, 40, 40)
        draw.rectangle((x, y, x + w - 1, y + bar - 1), fill=color)
        draw.text((x + 8, y + 5), f"{WORDS.get(answer, answer)} {max(probs.values()):.0%}  (truth: {WORDS[r['label']]})",
                  fill="white", font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90)
    return out


def cmd_check(args) -> int:
    checker = LocalChecker.load(args.model)
    for photo in args.photos:
        location, text = decide_location(checker.probabilities(Path(photo)))
        print(f"{photo}: {location or 'unsure'}  ({text})")
    return 0


def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m sokit.vision", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True, metavar="action")
    sp = sub.add_parser("prepare", help="copy a dataset and cut labelled frames out of it")
    sp.add_argument("--sensecraft", metavar="NAME", help="SenseCraft dataset name (default: the one with most episodes)")
    sp.add_argument("--dataset", metavar="FOLDER", help="a LeRobot dataset folder instead")
    sp.add_argument("--repo-id", help="a Hugging Face dataset instead, e.g. CrimsonSnowLLC/battery-sample")
    sp.add_argument("--camera", help="overhead camera name (default: found by name, e.g. front or top)")
    sp.add_argument("--no-copy", action="store_true", help="--dataset: read it in place instead of copying it first")
    sp = sub.add_parser("train", help="fine-tune the model on the prepared frames")
    sp.add_argument("--epochs", type=int, default=10)
    sp.add_argument("--batch-size", type=int, default=32)
    sp.add_argument("--lr", type=float, default=3e-4)
    sp.add_argument("--workers", type=int, default=4, help="data loading processes (0 = none)")
    sp.add_argument("--device", help="cuda | mps | cpu (default: the best available)")
    sp.add_argument("--seed", type=int, default=0)
    sp.add_argument("--out", default=str(DEFAULT_MODEL))
    sp = sub.add_parser("test", help="accuracy on unseen episodes and on labelled real check photos")
    sp.add_argument("--model", help=f"model file (default: {_rel(DEFAULT_MODEL)}, or LOCAL_CHECK_MODEL)")
    sp.add_argument("--labels", help=f"CSV of real photos: photo,label,hands (default: {_rel(REAL_LABELS)})")
    sp.add_argument("--no-save", action="store_true", help=f"do not write {_rel(REPORT)}")
    sp = sub.add_parser("check", help="where is the battery in these photos?")
    sp.add_argument("photos", nargs="+")
    sp.add_argument("--model")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_arg_parser().parse_args(argv)
    return {"prepare": cmd_prepare, "train": cmd_train, "test": cmd_test, "check": cmd_check}[args.action](args)


if __name__ == "__main__":  # also keeps Windows' spawned DataLoader workers from re-running this
    sys.exit(main())
