"""Dataset quality report: per-episode numbers and flags for suspicious demonstrations.

"El modelo solo aprende lo que le ensenas": a few bad episodes (hesitation, a missed
grasp, an odd start pose) hurt more than a few missing ones. This reads the recorded
joint data (no video decoding, so it takes seconds) and points at episodes worth
re-watching. Nothing is deleted: leave flagged episodes out with `so train --exclude`.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np

from .config import JOURNAL_DIR, dataset_info

IDLE_SPEED = 2.0  # action units (degrees) per second below which the leader is "not moving"


def _read_tables(root: Path, sub: str, columns: list[str]):
    import pyarrow as pa
    import pyarrow.parquet as pq

    files = sorted((root / sub).rglob("*.parquet"))
    if not files:
        raise SystemExit(f"No parquet files under {root / sub} (is this a LeRobot v3 dataset?)")
    return pa.concat_tables([pq.read_table(f, columns=columns) for f in files])


def _matrix(col) -> np.ndarray:
    arr = col.combine_chunks()
    flat = arr.flatten().to_numpy(zero_copy_only=False)
    return flat.reshape(len(arr), -1).astype(np.float32)


def analyze(local: Path) -> tuple[list[dict], dict]:
    info = dataset_info(local)
    fps = float(info.get("fps") or 30)
    t = _read_tables(local, "data", ["action", "observation.state", "episode_index", "frame_index"])
    ep = t.column("episode_index").to_numpy()
    fr = t.column("frame_index").to_numpy()
    order = np.lexsort((fr, ep))
    ep, action, state = ep[order], _matrix(t.column("action"))[order], _matrix(t.column("observation.state"))[order]

    rows = []
    for e in np.unique(ep):
        m = ep == e
        a, s = action[m], state[m]
        n = len(a)
        speed = np.abs(np.diff(a, axis=0)).max(axis=1) * fps if n > 1 else np.zeros(0)
        moving = speed > IDLE_SPEED
        idle_start = int(np.argmax(moving)) if moving.any() else n
        idle_end = int(np.argmax(moving[::-1])) if moving.any() else n
        jerk = float(np.abs(np.diff(a, n=2, axis=0)).mean()) if n > 2 else 0.0
        rows.append(
            {
                "ep": int(e),
                "frames": n,
                "sec": n / fps,
                "idle_start_s": idle_start / fps,
                "idle_end_s": idle_end / fps,
                "idle_frac": float(1 - moving.mean()) if len(moving) else 1.0,
                "grip_range": float(a[:, -1].max() - a[:, -1].min()),
                "start": s[0],
                "lag": float(np.percentile(np.abs(a - s).max(axis=1), 95)),
                "jerk": jerk,
                "flags": [],
            }
        )
    meta = {"fps": fps, "total_frames": int(len(ep)), "episodes": len(rows), "dof": action.shape[1]}
    return rows, meta


def flag(rows: list[dict], episode_time_s: float | None) -> None:
    if not rows:
        return
    med = lambda key: float(np.median([r[key] for r in rows]))  # noqa: E731
    med_frames, med_grip, med_lag, med_jerk = med("frames"), med("grip_range"), med("lag"), med("jerk")
    starts = np.stack([r["start"] for r in rows])
    centre = np.median(starts, axis=0)
    dev = np.abs(starts - centre)
    scale = np.maximum(np.median(dev, axis=0) * 1.4826, 1.0)  # robust per-joint spread, floor 1 degree
    for r, d in zip(rows, dev):
        f = r["flags"]
        r["start_dev"] = float(d.max())
        if r["frames"] < 0.5 * med_frames:
            f.append("SHORT")
        if r["frames"] > 1.8 * med_frames:
            f.append("LONG")
        if episode_time_s and r["sec"] >= episode_time_s - 0.3:
            f.append("TIMEOUT")
        if r["idle_start_s"] > 1.5:
            f.append("IDLE-START")
        if r["idle_frac"] > 0.5:
            f.append("MOSTLY-IDLE")
        if med_grip > 10 and r["grip_range"] < 0.3 * med_grip:
            f.append("NO-GRIP")
        if (d / scale).max() > 4 and d.max() > 8:
            f.append("START-POSE")
        if r["lag"] > max(3 * med_lag, 12):
            f.append("LAG")
        if med_jerk > 0 and r["jerk"] > 2.5 * med_jerk:
            f.append("JERKY")


LEGEND = """\
SHORT / LONG   much shorter / longer than the typical episode
TIMEOUT        ran into record.episode_time_s (task probably not finished, or -> not pressed)
IDLE-START     >1.5 s before the first motion (the policy learns to wait)
MOSTLY-IDLE    the leader was still for more than half of the episode
NO-GRIP        the gripper barely moved compared with the other episodes
START-POSE     starts from an unusual pose (start every episode from the same rest pose)
LAG            follower far from the leader's command (blocked, overloaded or colliding)
JERKY          much shakier motion than the other episodes"""


def report(repo_id: str, local: Path, save: bool = True, episode_time_s: float | None = None) -> int:
    if not local.is_dir():
        raise SystemExit(f"{repo_id} is not available locally at {local}")
    rows, meta = analyze(local)
    flag(rows, episode_time_s)
    lines = [
        f"Dataset QA: {repo_id}",
        f"{meta['episodes']} episodes, {meta['total_frames']} frames, "
        f"{meta['total_frames'] / meta['fps'] / 60:.1f} min of data at {meta['fps']:.0f} fps",
        "",
        f"{'ep':>3} {'frames':>6} {'sec':>6} {'idle@start':>10} {'idle%':>6} {'grip':>6} {'startdev':>8} {'lag':>6}  flags",
    ]
    for r in rows:
        lines.append(
            f"{r['ep']:>3} {r['frames']:>6} {r['sec']:>6.1f} {r['idle_start_s']:>9.1f}s {r['idle_frac']:>6.0%} "
            f"{r['grip_range']:>6.1f} {r['start_dev']:>8.1f} {r['lag']:>6.1f}  {' '.join(r['flags'])}"
        )
    flagged = [r for r in rows if r["flags"]]
    secs = np.array([r["sec"] for r in rows])
    lines += [
        "",
        f"episode length: median {np.median(secs):.1f} s, min {secs.min():.1f} s, max {secs.max():.1f} s",
        f"flagged: {len(flagged)} of {len(rows)} episodes",
    ]
    if flagged:
        serious = [r["ep"] for r in flagged if set(r["flags"]) - {"JERKY", "LONG"}]
        lines += ["", LEGEND, ""]
        lines.append("Re-watch the flagged ones (`so viz -e <ep>`). To train without them:")
        lines.append(f"  so train --exclude {','.join(str(r['ep']) for r in flagged)}")
        if serious and len(serious) != len(flagged):
            lines.append(f"  (only the more serious ones: --exclude {','.join(map(str, serious))})")
    else:
        lines.append("Nothing suspicious in the joint data. Still skim a few episodes: so viz -e 0")
    text = "\n".join(lines)
    print("\n" + text + "\n")
    if save:
        JOURNAL_DIR.mkdir(exist_ok=True)
        out = JOURNAL_DIR / f"qa_{repo_id.replace('/', '__')}.md"
        out.write_text(f"<!-- generated {dt.datetime.now():%Y-%m-%d %H:%M} by `so qa` -->\n```\n{text}\n```\n", encoding="utf-8")
        print(f"[so] report saved to {out}")
    return 0
