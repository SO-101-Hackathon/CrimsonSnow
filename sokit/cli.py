"""`so` - one short command per step of the SO-101 workflow.

Every subcommand builds the official `lerobot-*` command from hackathon.toml, prints it
(copy-pasteable), journals it, and runs it. Nothing here replaces LeRobot: it only removes
quoting mistakes, port mix-ups and forgotten dataset names.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

from . import config as C
from . import ports as P
from . import runner as R
from . import winlinks


# ----------------------------------------------------------------------------- helpers
def _robot_args(cfg, state, cameras: bool = True) -> list[str]:
    r = cfg["robot"]
    args = [
        f"--robot.type={r['type']}",
        f"--robot.port={P.resolve('follower', r.get('port', 'auto'), state)}",
        f"--robot.id={r['id']}",
    ]
    if cameras and cfg["cameras"]:
        args.append(f"--robot.cameras={C.cameras_arg(cfg)}")
    return args


def _teleop_args(cfg, state) -> list[str]:
    t = cfg["teleop"]
    return [
        f"--teleop.type={t['type']}",
        f"--teleop.port={P.resolve('leader', t.get('port', 'auto'), state)}",
        f"--teleop.id={t['id']}",
    ]


def _bool(v) -> str:
    return "true" if v else "false"


def _lerobot(script: str, need_links: bool = False) -> list[str]:
    """argv prefix for a lerobot script; routed through the junction shim only when required."""
    if need_links and not winlinks.can_symlink():
        return [sys.executable, "-m", "sokit.lr", script]
    return [R.exe(script)]


def _smolvla_rename_map(cfg) -> str:
    """smolvla_base was pretrained with cameras named camera1..3: map ours onto those names."""
    pairs = [
        f"observation.images.{name}: observation.images.camera{i}"
        for i, name in enumerate(cfg["cameras"], start=1)
    ]
    return "{" + ", ".join(pairs[:3]) + "}"


def _local_model(ref: str, dry_run: bool, revision: str | None = None) -> str:
    """Turn a Hub repo id into a local snapshot folder (downloaded once, then cached).

    Why: LeRobot 0.7.0 wraps `--policy.path` in pathlib.Path when training, so on Windows
    `lerobot/smolvla_base` becomes `lerobot\\smolvla_base` and the Hub rejects it
    (HFValidationError). A local folder always works - and keeps working without Wi-Fi.
    """
    if Path(ref).exists() or ref.count("/") != 1 or ref.startswith((".", "~")):
        return ref
    if dry_run:
        return ref
    from huggingface_hub import snapshot_download

    print(f"[so] fetching {ref} from the Hub (cached for next time)...")
    return snapshot_download(repo_id=ref, revision=revision)


def _policy_type(path: str, cfg) -> str:
    """Policy type of a local checkpoint (from its config.json); falls back to train.policy."""
    import json

    cfg_file = Path(path) / "config.json"
    if cfg_file.is_file():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8")).get("type", "")
        except (OSError, json.JSONDecodeError):
            pass
    return cfg["train"].get("policy", "act")


def _display(argv: list[str]) -> list[str]:
    """What we print/journal: always the canonical `lerobot-xxx ...` form."""
    if len(argv) > 3 and argv[1:3] == ["-m", "sokit.lr"]:
        return argv[3:]
    return argv


def _run(argv, *, label, args, keep_awake=False, journal=True) -> int:
    """Print + journal the canonical lerobot command, execute the real argv."""
    shown = _display(argv)
    if shown is not argv:
        print("[so] Developer Mode is off -> running through sokit.lr (symlink fallback). Equivalent command:")
    return R.run(
        argv, label=label, shown=shown, dry_run=args.dry_run, keep_awake=keep_awake, journal=journal
    )


def _run_dir(state, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            cand = C.OUTPUTS_DIR / "train" / explicit
            p = cand if cand.exists() else (C.ROOT / explicit)
        if not p.exists():
            raise SystemExit(f"Training run not found: {p}")
        return p
    last = state.get("last_run")
    if last and Path(last).exists():
        return Path(last)
    runs = sorted((C.OUTPUTS_DIR / "train").glob("*/checkpoints"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise SystemExit("No training run found in outputs/train. Train first (`so train`) or pass --policy user/repo.")
    return runs[-1].parent


def _checkpoint(run: Path, step: str | None) -> Path:
    ckpts = run / "checkpoints"
    if step:
        name = step if not step.isdigit() else f"{int(step):06d}"
        path = ckpts / name / "pretrained_model"
    else:
        numbered = sorted(p for p in ckpts.iterdir() if p.name.isdigit()) if ckpts.is_dir() else []
        if not numbered:
            raise SystemExit(f"No checkpoints in {ckpts} yet (they appear every train.save_freq steps).")
        path = numbered[-1] / "pretrained_model"
    if not path.is_dir():
        have = ", ".join(p.name for p in sorted(ckpts.iterdir())) if ckpts.is_dir() else "none"
        raise SystemExit(f"Checkpoint not found: {path}\nAvailable: {have}")
    return path


# ----------------------------------------------------------------------------- commands
def cmd_ports(args, cfg, state):
    if args.action == "assign":
        C.save_state(P.assign_wizard(state))
    else:
        P.show(state)
    return 0


def cmd_find_port(args, cfg, state):
    return _run(_lerobot("lerobot-find-port"), label="find-port", args=args, journal=False)


def cmd_cameras(args, cfg, state):
    code = _run(_lerobot("lerobot-find-cameras") + ["opencv"], label="find-cameras", args=args, journal=False)
    shots = Path("outputs") / "captured_images" / "opencv_<index>.png"
    print(
        f"\nOpen {shots} to see which index is which camera,\n"
        "then set [cameras.<name>].index_or_path in hackathon.toml.  Verify with:  so camcheck\n"
        "(Linux: a camera can also be named by its path, e.g. /dev/video2. Indices differ per computer.)"
    )
    return code


def cmd_camcheck(args, cfg, state):
    from . import camcheck

    return camcheck.run(cfg, save_now=args.save)


def cmd_setup_motors(args, cfg, state):
    if args.arm == "follower":
        r = cfg["robot"]
        tail = [f"--robot.type={r['type']}", f"--robot.port={P.resolve('follower', r.get('port', 'auto'), state)}"]
    else:
        t = cfg["teleop"]
        tail = [f"--teleop.type={t['type']}", f"--teleop.port={P.resolve('leader', t.get('port', 'auto'), state)}"]
    return _run(_lerobot("lerobot-setup-motors") + tail, label=f"setup-motors {args.arm}", args=args)


def cmd_calibrate(args, cfg, state):
    tail = _robot_args(cfg, state, cameras=False) if args.arm == "follower" else _teleop_args(cfg, state)
    code = _run(_lerobot("lerobot-calibrate") + tail, label=f"calibrate {args.arm}", args=args)
    if code == 0 and not args.dry_run:
        from . import calib

        calib.backup(cfg, quiet=False)
    return code


def cmd_calib(args, cfg, state):
    from . import calib

    if args.action == "backup":
        calib.backup(cfg, quiet=False)
    elif args.action == "restore":
        calib.restore(cfg, force=args.force)
    else:
        calib.status(cfg)
    return 0


def cmd_teleop(args, cfg, state):
    argv = _lerobot("lerobot-teleoperate") + _robot_args(cfg, state, cameras=not args.no_cameras)
    argv += _teleop_args(cfg, state)
    if not args.no_cameras:
        argv.append("--display_data=true")
    return _run(argv, label="teleoperate", args=args, journal=False)


def cmd_record(args, cfg, state):
    rec = cfg["record"]
    ns, logged_in = C.namespace(cfg, state)
    task = args.task or cfg["task"]["description"]
    base = args.name or cfg["task"]["slug"]
    n = args.episodes or rec.get("num_episodes", 50)
    argv = _lerobot("lerobot-record") + _robot_args(cfg, state) + _teleop_args(cfg, state)
    resumed = None
    if args.resume:
        repo_id, local = C.resolve_dataset(cfg, state, args.dataset, base=base)
        if not local.is_dir():
            raise SystemExit(f"Cannot resume: {local} does not exist locally.")
        resumed = (repo_id, local)
        argv += [f"--dataset.repo_id={repo_id}", f"--dataset.root={local}", "--resume=true"]
        print(f"[so] resuming {repo_id}: adding {n} episode(s) to the "
              f"{C.dataset_info(local).get('total_episodes', '?')} already recorded")
    else:
        argv.append(f"--dataset.repo_id={ns}/{base}")
    # A dataset recorded before logging in lives under local/...: lerobot would try to upload
    # it to an account called "local". Upload those with `so push dataset` instead.
    own = resumed is None or resumed[0].startswith(f"{ns}/")
    argv += [
        f"--dataset.num_episodes={n}",
        f"--dataset.single_task={task}",
        f"--dataset.episode_time_s={rec.get('episode_time_s', 30)}",
        f"--dataset.reset_time_s={rec.get('reset_time_s', 10)}",
        f"--display_data={_bool(rec.get('display_data', True))}",
    ]
    if rec.get("streaming_encoding", True):
        # Encode video while recording: saving an episode takes ~0.3 s instead of tens of seconds.
        argv.append("--dataset.streaming_encoding=true")
        if rec.get("encoder_threads"):
            argv.append(f"--dataset.encoder_threads={rec['encoder_threads']}")
    push = bool(rec.get("push_to_hub", True)) and logged_in and own and not args.no_push
    argv.append(f"--dataset.push_to_hub={_bool(push)}")
    if push and rec.get("private"):
        argv.append("--dataset.private=true")
    if not logged_in:
        print("[so] not logged in to Hugging Face -> recording locally only (hf auth login to upload)")
    elif not own:
        print(f"[so] {resumed[0]} was recorded under another account name -> not uploaded automatically.\n"
              f"     When you are done:  so push dataset --dataset {resumed[1].name}")
    argv += list(rec.get("extra", [])) + args.extra
    print("\nKeys while recording:  -> or n = save + next   |   <- or r = redo this episode   |   Esc or q = stop + save")
    print("(arrow keys are captured globally: do not type in other windows while recording)")
    code = _run(argv, label=f"record ({'resume' if args.resume else 'new'}, {n} episodes)", args=args, keep_awake=True)
    if not args.dry_run:
        found = [resumed[1]] if resumed else C.local_datasets(ns, base)
        if found:
            newest = found[-1]
            info = C.dataset_info(newest)
            name = f"{newest.parent.name}/{newest.name}"
            state["last_dataset"] = name
            C.save_state(state)
            print(f"\n[so] dataset: {name}  ({info.get('total_episodes', '?')} episodes, "
                  f"{info.get('total_frames', '?')} frames)\n     next:  so qa   ->   so plan   ->   so train")
    return code


def cmd_replay(args, cfg, state):
    repo_id, local = C.resolve_dataset(cfg, state, args.dataset)
    argv = _lerobot("lerobot-replay") + _robot_args(cfg, state, cameras=False)
    argv += [f"--dataset.repo_id={repo_id}", f"--dataset.episode={args.episode}"]
    if local.is_dir():
        argv.append(f"--dataset.root={local}")
    return _run(argv, label=f"replay episode {args.episode} of {repo_id}", args=args)


def cmd_datasets(args, cfg, state):
    ns, _ = C.namespace(cfg, state)
    root = C.lerobot_home()
    rows = []
    for nsdir in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        if nsdir.name in ("hub", "calibration", "robot-urdfs"):
            continue
        for d in C.local_datasets(nsdir.name):
            info = C.dataset_info(d)
            frames, fps = info.get("total_frames", 0), info.get("fps", 30) or 30
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e6
            rows.append((f"{nsdir.name}/{d.name}", info.get("total_episodes", "?"), frames, frames / fps / 60, size))
    if not rows:
        print(f"No local datasets under {root}")
        return 0
    print(f"\n{'dataset':<58} {'eps':>4} {'frames':>8} {'minutes':>8} {'MB':>8}")
    for name, eps, frames, minutes, size in rows:
        mark = "  <- current" if name == state.get("last_dataset") else ""
        print(f"{name:<58} {eps:>4} {frames:>8} {minutes:>8.1f} {size:>8.0f}{mark}")
    print(f"\nstored in {root}   (namespace in use: {ns})")
    return 0


def cmd_qa(args, cfg, state):
    from . import qa

    repo_id, local = C.resolve_dataset(cfg, state, args.dataset)
    return qa.report(repo_id, local, save=not args.no_save, episode_time_s=cfg["record"].get("episode_time_s"))


def cmd_plan(args, cfg, state):
    from . import plan

    repo_id, local = C.resolve_dataset(cfg, state, args.dataset)
    return plan.report(repo_id, local, cfg, state, epochs=args.epochs, batch_size=args.batch_size)


def cmd_train(args, cfg, state):
    tr = cfg["train"]
    ns, logged_in = C.namespace(cfg, state)
    if args.resume:
        run = _run_dir(state, args.run)
        cfg_path = run / "checkpoints" / "last" / "pretrained_model" / "train_config.json"
        if not cfg_path.is_file():
            cfg_path = _checkpoint(run, None) / "train_config.json"
        argv = _lerobot("lerobot-train", need_links=True) + [f"--config_path={cfg_path}", "--resume=true"]
        if args.steps:
            argv.append(f"--steps={args.steps}")
        argv += args.extra
        state["last_run"] = str(run)
        C.save_state(state)
        return _run(argv, label=f"train resume {run.name}", args=args, keep_awake=True)

    repo_id, local = C.resolve_dataset(cfg, state, args.dataset)
    policy = args.policy or tr.get("policy", "act")
    base_model = args.policy_path or ("lerobot/smolvla_base" if policy == "smolvla" else None)
    if base_model and "smolvla" in base_model:
        policy = "smolvla"
    steps = args.steps or tr.get("steps", 20000)
    slug = cfg["task"]["slug"]
    run_name = args.run or f"{policy}_{slug}_{dt.datetime.now():%m%d_%H%M}"
    out = C.OUTPUTS_DIR / "train" / run_name
    if out.exists():
        raise SystemExit(f"{out} already exists. Use `so train --resume --run {run_name}` or pick another --run name.")
    if args.cloud:
        if repo_id.startswith("local/"):
            raise SystemExit(
                f"{repo_id} was recorded while logged out, so it has no place on the Hub yet.\n"
                f"Upload it first:  so push dataset --dataset {local.name}\n"
                f"then:             so train --cloud {args.cloud} --dataset {ns}/{local.name} ..."
            )
        # The staged config must not carry Windows paths: sokit.cloud rewrites them (base model -> Hub id).
        hub_base = base_model if base_model and not Path(base_model).exists() and base_model.count("/") == 1 else None
        prefix = [sys.executable, "-m", "sokit.cloud", f"--base-model={hub_base or ''}", "lerobot-train"]
    else:
        prefix = _lerobot("lerobot-train", need_links=True)
    argv = prefix + [f"--dataset.repo_id={repo_id}"]
    if local.is_dir():
        argv.append(f"--dataset.root={local}")
    if base_model:
        # fine-tune an existing model (Hub ids are resolved to a local snapshot first)
        argv.append(f"--policy.path={_local_model(base_model, args.dry_run)}")
        if policy == "smolvla":
            argv.append(f"--rename_map={_smolvla_rename_map(cfg)}")
    else:
        argv.append(f"--policy.type={policy}")
    default_bs = tr.get("smolvla_batch_size", 8) if policy == "smolvla" else tr.get("batch_size", 8)
    batch_size = args.batch_size or default_bs
    argv += [
        f"--output_dir={out.relative_to(C.ROOT).as_posix()}",  # relative: commands run from the repo root
        f"--job_name={run_name}",
        f"--steps={steps}",
        f"--batch_size={batch_size}",
        f"--num_workers={tr.get('num_workers', 4)}",
        f"--save_freq={args.save_freq or tr.get('save_freq', 5000)}",
    ]
    if args.device:
        # Without this flag LeRobot picks the best device itself: cuda, then mps (Apple), then cpu.
        argv.append(f"--policy.device={args.device}")
    push = bool(tr.get("push_to_hub", True)) and logged_in and not args.no_push
    if push:
        argv.append(f"--policy.repo_id={ns}/{policy}_{slug}")
    else:
        argv.append("--policy.push_to_hub=false")
    if tr.get("mixed_precision"):
        argv.append(f"--accelerator.mixed_precision={tr['mixed_precision']}")
    extra = list(tr.get("extra", [])) + args.extra
    if tr.get("trackio", True):
        # A cloud job has no local Trackio database to keep, and LeRobot refuses such a run
        # unless a Space is named: log curves there only when the user names one.
        if not args.cloud or any(e.startswith("--trackio.space_id") for e in extra):
            argv.append("--trackio.enable=true")
        else:
            print("[so] cloud run: loss curves are off (add --trackio.space_id=<you>/<space> to log them to a Space)")
    if tr.get("augment"):
        argv.append("--dataset.image_transforms.enable=true")
    if args.exclude:
        eps = sorted({int(x) for x in args.exclude.replace(" ", "").split(",") if x})
        argv.append(f"--dataset.exclude_episodes={eps}")
    if args.cloud:
        argv.append(f"--job.target={args.cloud}")
        if not any(e.startswith("--job.timeout") for e in extra):
            # LeRobot's own cap is 2 days; a hung job would keep billing until then.
            argv.append("--job.timeout=8h")
            print("[so] cloud run: billing stops after 8 h at the latest (change with --job.timeout=<e.g. 3h>)")
    argv += extra
    if not args.dry_run:
        state["last_run"] = str(out)
        C.save_state(state)
    t0 = time.time()
    code = _run(argv, label=f"train {run_name} ({steps} steps on {repo_id})", args=args, keep_awake=True)
    if code == 0 and not args.dry_run:
        if steps >= 2000 and not args.cloud:
            from . import plan

            # Remember how fast this laptop really trains, so `so plan` gets more accurate.
            plan.record_measurement(state, policy, batch_size, tr.get("mixed_precision", "") or "",
                                    (time.time() - t0) / steps)
        print(f"\n[so] run: {out}\n     next:  so rollout            (newest checkpoint)\n"
              f"            so rollout --step 5000  (a specific one)")
    return code


def _policy_path(args, state) -> tuple[str, str]:
    """(value for --policy.path, short label for the eval log)."""
    if args.policy:
        revision = getattr(args, "step", None)
        if revision and revision.isdigit():
            revision = f"{int(revision):06d}"  # checkpoints pushed to the Hub are tagged by step
        label = args.policy + (f"@{revision}" if revision else "")
        return _local_model(args.policy, getattr(args, "dry_run", False), revision), label
    run = _run_dir(state, args.run)
    ckpt = _checkpoint(run, args.step)
    return str(ckpt), f"{run.name}@{ckpt.parent.name}"


def cmd_rollout(args, cfg, state):
    ro = cfg["rollout"]
    ns, logged_in = C.namespace(cfg, state)
    task = args.task or cfg["task"]["description"]
    path, label = _policy_path(args, state)
    mode = args.mode
    argv = _lerobot("lerobot-rollout") + [f"--strategy.type={mode}", f"--policy.path={path}"]
    argv += _robot_args(cfg, state)
    slug = cfg["task"]["slug"]
    if mode == "base":
        duration = args.duration if args.duration is not None else ro.get("duration", 60)
        argv += [f"--task={task}", f"--duration={duration}"]
    else:
        # Recording strategies: dataset names must start with rollout_
        argv += _teleop_args(cfg, state)
        suffix = "" if mode == "episodic" else f"_{mode}"
        argv += [f"--dataset.repo_id={ns}/rollout_{slug}{suffix}", f"--dataset.single_task={task}"]
        n = args.episodes or 10
        if mode == "episodic":
            rec = cfg["record"]
            argv += [
                f"--dataset.num_episodes={n}",
                f"--dataset.episode_time_s={rec.get('episode_time_s', 30)}",
                f"--dataset.reset_time_s={rec.get('reset_time_s', 10)}",
            ]
        elif mode == "dagger":
            argv.append(f"--strategy.num_episodes={n}")
        argv.append(f"--dataset.push_to_hub={_bool(logged_in and not args.no_push)}")
    if args.display or ro.get("display_data"):
        argv.append("--display_data=true")
    if _policy_type(path, cfg) == "smolvla":
        argv.append(f"--rename_map={_smolvla_rename_map(cfg)}")  # same mapping as at training time
        if not args.rtc:
            print("[so] SmolVLA policy: add --rtc if the arm moves in jerks (real-time chunking)")
    if args.rtc:
        argv.append("--inference.type=rtc")
    argv += list(ro.get("extra", [])) + args.extra
    if mode == "dagger":
        print("\nDAgger keys:  Space = pause/resume policy   |   Tab = start/stop your correction   |   Esc = stop")
    elif mode == "episodic":
        print("\nEpisodic keys:  -> = end attempt early   |   <- = discard + redo   |   Esc = stop")
    code = _run(argv, label=f"rollout {mode} {label}", args=args, keep_awake=True)
    if not args.dry_run:
        state["last_policy_label"] = label
        C.save_state(state)
        print(f"\n[so] log how it went:  so eval \"{label}\"")
    return code


def cmd_eval(args, cfg, state):
    from . import evallog

    if args.summary:
        evallog.summary()
        return 0
    label = args.label or state.get("last_policy_label")
    if not label:
        raise SystemExit("Which checkpoint? e.g.  so eval act_pickplace_1121_0930@005000   (or run `so rollout` first)")
    evallog.interactive(label, args.attempts)
    return 0


def cmd_viz(args, cfg, state):
    repo_id, local = C.resolve_dataset(cfg, state, args.dataset)
    print(f"Online visualizer (dataset must be on the Hub):\n"
          f"  https://huggingface.co/spaces/lerobot/visualize_dataset?path=/{repo_id}/episode_{args.episode}\n")
    argv = _lerobot("lerobot-dataset-viz") + ["--repo-id", repo_id, "--episode-index", str(args.episode)]
    if local.is_dir():
        argv += ["--root", str(local), "--mode", "local"]
    return _run(argv, label="dataset-viz", args=args, journal=False)


def cmd_push(args, cfg, state):
    ns, logged_in = C.namespace(cfg, state)
    if not logged_in:
        raise SystemExit("Not logged in. Run:  hf auth login")
    if args.what == "dataset":
        repo_id, local = C.resolve_dataset(cfg, state, args.dataset)
        if not (local / "meta" / "info.json").is_file():
            raise SystemExit(f"No local dataset at {local}   (`so datasets` lists what is on this laptop)")
        # Default destination: the logged-in account, same dataset name (also for datasets
        # recorded before logging in, which live under local/).
        named = bool(args.dataset and "/" in args.dataset and not args.dataset.startswith("local/"))
        target = args.repo or (repo_id if named else f"{ns}/{local.name}")
        # Through LeRobot's own push_to_hub (sokit.push), never a plain `hf upload`: LeRobot
        # refuses to load a Hub dataset that lacks the codebase-version tag.
        argv = [sys.executable, "-m", "sokit.push", target, str(local)]
        if args.private or cfg["record"].get("private"):
            argv.append("--private")
        label = f"push dataset {local.parent.name}/{local.name} -> {target}"
    else:
        path, short = _policy_path(args, state)
        repo = args.repo or f"{ns}/{short.split('@')[0]}"
        argv = [R.exe("hf"), "upload", repo, path] + (["--private"] if args.private else []) + args.extra
        label = f"push policy {short} -> {repo}"
    return _run(argv, label=label, args=args)


def cmd_show(args, cfg, state):
    """Print every command the current config produces (nothing is executed)."""
    args.dry_run = True
    state = dict(state)
    fake = False
    for role, cfg_key in (("follower", "robot"), ("leader", "teleop")):
        try:
            P.resolve(role, cfg[cfg_key].get("port", "auto"), state)
        except SystemExit:
            cfg[cfg_key]["port"] = f"<{role.upper()}_PORT>"
            fake = True
    if fake:
        print("(arms not connected/identified: showing placeholder ports)")
    ns, _ = C.namespace(cfg, state)
    slug = cfg["task"]["slug"]
    sample = f"{ns}/{slug}_YYYYMMDD_HHMMSS"
    blank = argparse.Namespace(
        dry_run=True, extra=[], arm="follower", no_cameras=False, task=None, name=None, episodes=None,
        resume=False, dataset=sample, no_push=False, episode=0, policy=None, steps=None, run=None,
        policy_path=None, device=None, batch_size=None, save_freq=None, exclude=None, cloud=None,
        mode="base", duration=None, display=False, rtc=False, step=None,
    )
    for title, fn, over in (
        ("calibrate follower", cmd_calibrate, {}),
        ("calibrate leader", cmd_calibrate, {"arm": "leader"}),
        ("teleoperate", cmd_teleop, {}),
        ("record", cmd_record, {"dataset": None}),
        ("replay", cmd_replay, {}),
        ("train", cmd_train, {}),
        ("rollout (demo mode)", cmd_rollout,
         {"policy": f"outputs/train/act_{slug}_MMDD_HHMM/checkpoints/last/pretrained_model"}),
    ):
        print(f"# ---- {title} ----")
        ns_args = argparse.Namespace(**{**vars(blank), **over})
        fn(ns_args, cfg, state)
    return 0


def cmd_doctor(args, cfg, state):
    from . import doctor

    return doctor.run(cfg, state)


# ----------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="so",
        description="SO-101 hackathon helper: config-driven wrappers around the official lerobot-* commands.",
        epilog="Anything after `--` is passed to the underlying lerobot command unchanged.",
    )
    p.add_argument("--dry-run", action="store_true", help="print the command, do not run it")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_, description=help_)
        sp.set_defaults(fn=fn)
        return sp

    add("doctor", cmd_doctor, "check the whole setup (GPU, ffmpeg, login, ports, cameras, calibration, disk)")
    sp = add("ports", cmd_ports, "list serial ports / identify which arm is which")
    sp.add_argument("action", nargs="?", choices=["list", "assign"], default="list")
    add("find-port", cmd_find_port, "official lerobot-find-port wizard")
    add("cameras", cmd_cameras, "detect cameras and save a test frame per index")
    sp = add("camcheck", cmd_camcheck, "live view with ghost overlay of the reference framing")
    sp.add_argument("--save", action="store_true", help="save reference frames immediately and exit")
    sp = add("setup-motors", cmd_setup_motors, "write motor ids/baudrate (only for unconfigured arms)")
    sp.add_argument("arm", choices=["follower", "leader"])
    sp = add("calibrate", cmd_calibrate, "calibrate one arm (then backs the calibration up into the repo)")
    sp.add_argument("arm", choices=["follower", "leader"])
    sp = add("calib", cmd_calib, "calibration files: status / backup into repo / restore from repo")
    sp.add_argument("action", nargs="?", choices=["status", "backup", "restore"], default="status")
    sp.add_argument("--force", action="store_true", help="restore: overwrite existing calibration")
    sp = add("teleop", cmd_teleop, "leader drives follower, with camera view")
    sp.add_argument("--no-cameras", action="store_true")

    sp = add("record", cmd_record, "record demonstrations into a dataset")
    sp.add_argument("-n", "--episodes", type=int, help="episodes to record now (default: record.num_episodes)")
    sp.add_argument("--resume", action="store_true", help="add episodes to the newest dataset of this task")
    sp.add_argument("--dataset", help="with --resume: full dataset name (default: newest)")
    sp.add_argument("--name", help="dataset base name (default: task.slug)")
    sp.add_argument("--task", help="override task.description for this session")
    sp.add_argument("--no-push", action="store_true", help="do not upload at the end")

    sp = add("replay", cmd_replay, "replay a recorded episode on the follower")
    sp.add_argument("-e", "--episode", type=int, default=0)
    sp.add_argument("--dataset")
    add("datasets", cmd_datasets, "list local datasets")
    sp = add("qa", cmd_qa, "dataset quality report: flags suspicious episodes")
    sp.add_argument("--dataset")
    sp.add_argument("--no-save", action="store_true", help="do not write the report to journal/")
    sp = add("plan", cmd_plan, "how many steps to train and how long it will take on this GPU")
    sp.add_argument("--dataset")
    sp.add_argument("--epochs", type=float)
    sp.add_argument("--batch-size", type=int)
    sp = add("viz", cmd_viz, "view an episode (Rerun) and print the online visualizer link")
    sp.add_argument("-e", "--episode", type=int, default=0)
    sp.add_argument("--dataset")

    sp = add("train", cmd_train, "train a policy on the newest dataset")
    sp.add_argument("--steps", type=int)
    sp.add_argument("--policy", help="act | smolvla | diffusion (default: train.policy)")
    sp.add_argument("--policy-path", help="fine-tune an existing model instead, e.g. lerobot/smolvla_base")
    sp.add_argument("--dataset", help="dataset name or user/name (default: newest recording of this task)")
    sp.add_argument("--run", help="run name (default: <policy>_<slug>_<MMDD_HHMM>)")
    sp.add_argument("--resume", action="store_true", help="continue the last (or --run) training run")
    sp.add_argument("--batch-size", type=int)
    sp.add_argument("--save-freq", type=int)
    sp.add_argument("--exclude", help="episode indices to leave out, e.g. 3,7,12 (see `so qa`)")
    sp.add_argument("--device", default=None, help="cuda | mps | cpu (default: LeRobot picks the best available)")
    sp.add_argument("--cloud", metavar="FLAVOR", help="run on Hugging Face Jobs instead (paid), e.g. a100-large; `hf jobs hardware` lists them")
    sp.add_argument("--no-push", action="store_true")

    sp = add("rollout", cmd_rollout, "run a trained policy on the robot")
    sp.add_argument("mode", nargs="?", choices=["base", "episodic", "dagger", "highlight", "sentry"], default="base")
    sp.add_argument("--run", help="training run folder name (default: last run)")
    sp.add_argument("--step", help="checkpoint step, e.g. 5000 (default: newest)")
    sp.add_argument("--policy", help="Hub repo id or path instead of a local run")
    sp.add_argument("--duration", type=float, help="seconds (base mode); 0 = until Ctrl+C")
    sp.add_argument("-n", "--episodes", type=int, help="episodes for episodic / dagger")
    sp.add_argument("--task")
    sp.add_argument("--display", action="store_true", help="live Rerun view")
    sp.add_argument("--rtc", action="store_true", help="real-time chunking (use with SmolVLA / pi0)")
    sp.add_argument("--no-push", action="store_true")

    sp = add("eval", cmd_eval, "log success/fail per attempt; pick the best checkpoint for the demo")
    sp.add_argument("label", nargs="?", help="checkpoint label (default: the last one rolled out)")
    sp.add_argument("-n", "--attempts", type=int, default=5, help="attempts to log (0 = until q)")
    sp.add_argument("--summary", action="store_true")

    sp = add("push", cmd_push, "upload a dataset or a policy checkpoint to the Hub")
    sp.add_argument("what", choices=["dataset", "policy"])
    sp.add_argument("--dataset")
    sp.add_argument("--run")
    sp.add_argument("--step")
    sp.add_argument("--policy")
    sp.add_argument("--repo", help="target repo id (default: <you>/<dataset name> or <you>/<run name>)")
    sp.add_argument("--private", action="store_true", help="create the repo as private (default: public)")

    add("show", cmd_show, "print all the lerobot commands this config produces")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1 :]
    # Unknown --flags are forwarded to lerobot as well: PowerShell swallows a bare `--`
    # when calling a script, so `so train --policy.chunk_size=50` must work without it.
    args, unknown = build_parser().parse_known_args(argv)
    stray = [u for u in unknown if not u.startswith("--")]
    if stray:
        raise SystemExit(f"so: unexpected argument(s): {' '.join(stray)}   (see: so {args.cmd} --help)")
    args.extra = unknown + extra
    R.ensure_env_on_path()
    cfg = C.load_config()
    state = C.load_state()
    try:
        return int(args.fn(args, cfg, state) or 0)
    except KeyboardInterrupt:
        print("\n[so] interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
