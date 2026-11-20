"""Turn a dataset size into a --steps value and a wall-clock estimate for this laptop.

LeRobot's hardware guide: imitation learning typically converges in 5-10 epochs over the
data, so the right number of steps depends on how many frames you recorded - the default
of 100,000 is usually far more than a hackathon dataset needs.

    steps_per_epoch = ceil(total_frames / batch_size)
    steps           = epochs * steps_per_epoch
"""

from __future__ import annotations

import math
from pathlib import Path

from .config import dataset_info, save_state

# Seconds per training step measured on this laptop (RTX 4060 Laptop 8 GB, 2 cameras 640x480,
# torch 2.15 + cu132, 2026-11-19, lerobot/svla_so101_pickplace). Used until your own runs
# replace them (every finished `so train` updates the measurement in .so101-state.json).
DEFAULT_STEP_S = {
    ("act", 8, ""): 0.325,
    ("act", 8, "fp16"): 0.270,
    ("act", 8, "bf16"): 0.273,
    ("act", 16, "fp16"): 0.500,
    ("smolvla", 4, ""): 0.295,
    ("smolvla", 8, ""): 0.408,
}


def _key(policy: str, batch_size: int, precision: str) -> str:
    return f"{policy}|{batch_size}|{precision or 'fp32'}"


def record_measurement(state: dict, policy: str, batch_size: int, precision: str, step_s: float) -> None:
    state.setdefault("bench", {})[_key(policy, batch_size, precision)] = round(step_s, 4)
    save_state(state)


def step_seconds(state: dict, policy: str, batch_size: int, precision: str) -> tuple[float | None, str]:
    measured = (state.get("bench") or {}).get(_key(policy, batch_size, precision))
    if measured:
        return float(measured), "measured on your own runs"
    default = DEFAULT_STEP_S.get((policy, batch_size, precision or ""))
    if default:
        return default, "benchmark from setup day"
    base = DEFAULT_STEP_S.get((policy, 8, precision or "")) or DEFAULT_STEP_S.get((policy, 8, ""))
    if base:
        return base * batch_size / 8, "extrapolated from batch 8 (roughly linear)"
    return None, "no measurement for this policy yet"


def _hm(seconds: float) -> str:
    m = int(round(seconds / 60))
    return f"{m // 60}h{m % 60:02d}m" if m >= 60 else f"{m} min"


def _round_steps(steps: float) -> int:
    return int(math.ceil(steps / 1000.0) * 1000)


def report(repo_id: str, local: Path, cfg: dict, state: dict, epochs: float | None, batch_size: int | None) -> int:
    info = dataset_info(local)
    frames, episodes, fps = info.get("total_frames"), info.get("total_episodes"), info.get("fps") or 30
    if not frames:
        raise SystemExit(f"Cannot read meta/info.json of {repo_id} at {local}")
    tr = cfg["train"]
    policy = tr.get("policy", "act")
    bs = batch_size or (tr.get("smolvla_batch_size", 8) if policy == "smolvla" else tr.get("batch_size", 8))
    precision = tr.get("mixed_precision", "") or ""
    per_epoch = math.ceil(frames / bs)
    step_s, source = step_seconds(state, policy, bs, precision)

    print(f"\n{repo_id}: {episodes} episodes, {frames} frames ({frames / fps / 60:.1f} min of data)")
    print(f"policy={policy}  batch_size={bs}  precision={precision or 'fp32'}  ->  {per_epoch} steps per epoch")
    if step_s:
        print(f"speed: {1 / step_s:.2f} steps/s ({source})\n")
    else:
        print(f"speed: unknown ({source}); run a short `so train --steps 500` to measure\n")
    print(f"{'epochs':>7} {'steps':>8} {'wall-clock':>11}")
    for e in ([epochs] if epochs else [3, 5, 8, 10, 15]):
        steps = _round_steps(e * per_epoch)
        wall = _hm(steps * step_s) if step_s else "?"
        note = "  <- quick sanity model" if e == 3 else ("  <- recommended" if e == 8 else "")
        print(f"{e:>7g} {steps:>8} {wall:>11}{note}")
    rec = _round_steps((epochs or 8) * per_epoch)
    save = max(1000, _round_steps(rec / 5))
    print(
        f"\nSuggested:  so train --steps {rec} --save-freq {save}\n"
        f"First, get a model on the robot fast:  so train --steps {_round_steps(3 * per_epoch)}\n"
        "Checkpoints are saved every save-freq steps; an intermediate one is sometimes better than\n"
        "the last - compare them with `so rollout --step N` + `so eval`.\n\n"
        "Rule of thumb (Seeed guide):  ~20 eps -> 10-15k steps | ~50 eps -> 30-40k | ~100 eps -> 80-100k"
    )
    if step_s and not precision:
        print("Tip: train.mixed_precision = \"fp16\" in hackathon.toml is ~20% faster on this GPU (see RUNBOOK).")
    return 0
