# CrimsonSnow: SO-101 / LeRobot hackathon project

Notes for AI assistants. Workspace of team CrimsonSnow for the **Hackathon LeRobot Bilbao** (20–22 Nov 2026): imitation learning on an SO-101
leader/follower arm pair with LeRobot **v0.7.0**. The team laptop runs it **natively on Windows 11**
(no WSL); the repository is public and must stay reproducible on Ubuntu, macOS and WSL too.
Human-facing docs: `README.md` (what we did and how to repeat it), `docs/SETUP.md` (setup per operating
system), `docs/SETUP_LOG.md` (what was set up when) and `RUNBOOK.md` (weekend playbook for the Windows
laptop, measured numbers, Windows gotchas). Offline copies of the hackathon guide and the LeRobot docs
are in `docs/offline/` on the team laptop only (git-ignored) — read those before guessing a flag;
v0.7.0 is newer than most training data.

## Rules for changes

- **Document every setup change**: add a dated line to `docs/SETUP_LOG.md` in the same commit, and
  update `docs/SETUP.md` if the steps for any operating system change.
- **Keep it cross-platform**: no hard-coded paths, drive letters or user names; guard system-specific
  code with `runner.IS_WINDOWS` / `IS_MAC` / `IS_LINUX` / `is_wsl()`; shell scripts keep LF endings
  (`.gitattributes`). Run `python -m unittest discover -s tests` before pushing; CI repeats it on
  Ubuntu, macOS and Windows and runs `./setup.sh` on Ubuntu and macOS.
- The repository is public: no tokens, no personal paths, no private data.

## Environment (team laptop)

- Conda env `lerobot` at `%USERPROFILE%\miniforge3\envs\lerobot` (Python 3.12, ffmpeg 9 from
  conda-forge, torch 2.15.0+cu132, lerobot 0.7.0 with extras core_scripts, training, feetech, smolvla, diffusion).
- GPU: RTX 4060 Laptop, 8 GB. ACT batch 8 ≈ 3.1 steps/s (fp32), 3.7 GB VRAM.
- Run commands from a tool shell without activation via the env's executables, e.g.
  `%USERPROFILE%\miniforge3\envs\lerobot\Scripts\so.exe doctor` (it fixes up PATH itself), or in
  PowerShell: `& "$env:USERPROFILE\miniforge3\shell\condabin\conda-hook.ps1"; conda activate lerobot`.
- The user's own terminal: `hackathon-shell.cmd` (cmd with the env active). PowerShell execution policy
  is the Windows default (scripts disabled) — do not change it; `so.ps1` is optional.
- Since 19 Nov 2026: Windows Developer Mode is on (symlinks work without elevation) and `hf` is logged in
  through the browser (OAuth, expires 2026-12-19; `so doctor` shows the account). Write access was verified
  by pushing, loading back and deleting a private dataset and a private model.

## The `so` helper (`sokit/`)

Thin wrappers that build the official `lerobot-*` command from `hackathon.toml`, print it, append it to
`journal/commands.md`, and run it. `so show` prints all commands; `--dry-run` prints one. Unknown
`--flags` are forwarded to lerobot. Machine state (USB serials of the arms, last dataset/run, measured
training speed) lives in `.so101-state.json` (git-ignored).

| File | Role |
|---|---|
| `sokit/cli.py` | subcommands and argument building |
| `sokit/config.py` | `hackathon.toml` + state, dataset name resolution (recordings get a `_YYYYMMDD_HHMMSS` suffix) |
| `sokit/runner.py` | printing in the caller's shell syntax, journal, keep-awake, env PATH fix-up |
| `sokit/ports.py` | arms identified by USB serial, never by COM number |
| `sokit/winlinks.py`, `sokit/lr.py` | junction fallback for `checkpoints/last` when symlinks are not permitted |
| `sokit/push.py` | dataset upload through `LeRobotDataset.push_to_hub` (card + version tag); used by `so push dataset` |
| `sokit/cloud.py` | HF Jobs submission from Windows: fixes Windows paths in the staged config; used by `so train --cloud` |
| `sokit/demo.py` | `so demo`: rollout with automatic retries through LeRobot's `RolloutController` (run, return home, check grip + a vision model on the overhead camera, run again); `so try`: same session, the operator marks each run s/f (`journal/eval.csv`); pure helpers are unit-tested |
| `sokit/sensecraft.py` | finds SenseCraft's trained models and its follower calibration (read only); used by `so demo --sensecraft` |
| `sokit/vision.py` | `so vision prepare/train/test/check`: our own camera check for `so demo` (`--check local`, or `RETRY_CHECK=local` in `.env`). ResNet-18 fine-tuned on frames labelled automatically from the gripper trace (on the mat / in the gripper / in the box); `prepare` copies the dataset first (SenseCraft's folders are only read); model in `outputs/vision/model/` (git-ignored), report in `journal/vision-report.md` |
| `sokit/panel.py`, `sokit/panel.html` | `so panel`: local web control panel for the presentation; runs `so demo`/`try`/`teleop`/`cameras`/`doctor` as one child process and drives it through stdin; `--mock` runs a fake robot session for testing |
| `docs/presentation/` | the 5-minute pitch deck; `build_deck.py` rebuilds it with python-pptx (installed outside the `lerobot` env), `--voice` writes the laptop copy with the voiced bonus video to `outputs/presentation/` (never commit the voice); `build_demo_clip.py` (lerobot env) cuts slide 7's clip from `outputs/demo/` |
| `setup.sh`, `tests/`, `.github/workflows/ci.yml` | setup on Ubuntu/macOS/WSL, robot-free tests, and the CI that runs both on clean machines |
| `sokit/qa.py`, `plan.py`, `evallog.py`, `camcheck.py`, `calib.py`, `doctor.py` | dataset QA, step planner, eval tally, camera alignment, calibration backup, self-check |

Editable install (`pip install -e . --no-deps`) provides `so.exe`; edits to `sokit/` take effect immediately.

## Verified Windows behaviour of LeRobot 0.7.0 (do not re-derive)

- PyPI's Windows torch wheel is CPU-only; CUDA build comes from `https://download.pytorch.org/whl/cu132`.
- `lerobot-train` creates `checkpoints/last` with `Path.symlink_to` and no fallback → `WinError 1314`
  unless Developer Mode is on (`admin-setup.ps1`, needs the user's UAC approval) — `so train` routes
  through `sokit.lr` when symlinks are unavailable.
- Explorer's "Run with PowerShell" runs `powershell -file <script>` under the default Restricted policy:
  the script never starts and the window just closes. Tell people to run
  `powershell -ExecutionPolicy Bypass -File .\<script>.ps1` (applies to that process only, changes no policy).
- `lerobot-train --policy.path=<hub repo id>` breaks on Windows (`configs/train.py` wraps it in `Path`,
  giving `user\repo`). Pass a local folder; `so` resolves Hub ids with `snapshot_download`.
- Recording: use `--dataset.streaming_encoding=true` (episode save 0.3 s vs ~15 s); do **not** use
  `--dataset.rgb_encoder.vcodec=auto` (h264_nvenc fails to open here).
- Cameras open through DSHOW; index 0 is the built-in webcam; forcing `fourcc: MJPG` on a camera that
  lacks it makes reads time out; the MSMF backend fails to open.
- Scripts that spawn processes need an `if __name__ == "__main__":` guard (Windows uses spawn) —
  dataset video encoding and DataLoader workers re-import the main module.
- SmolVLA needs `--rename_map` to `camera1..3` at both train and rollout time; `so` adds it.
- `hf auth login` (huggingface_hub 1.33) is a browser device-code login: `whoami()["auth"]` is
  `{"type": "oauth", "expiresAt": ...}` with no role field, so write access cannot be read back, only tested.
- A Hub dataset needs the codebase tag (`v3.0`) or LeRobot refuses to load it: upload datasets only with
  `LeRobotDataset.push_to_hub` (`sokit/push.py`), never `hf upload`. Policies are fine with `hf upload`.
- Datasets stay in the namespace folder that was active when they were recorded (`local/` when logged
  out); `config.resolve_dataset` searches the current namespace, then `local`, then the others.
- `--job.target` (HF Jobs) refuses `--trackio.enable=true` without `--trackio.space_id`; `so train --cloud`
  leaves Trackio off. Jobs itself is untested (the account had no credits on 19 Nov 2026).
- For a remote job LeRobot stages a `train_config.json` on the Hub; written on Windows it holds the local
  snapshot folder as `policy.pretrained_path` and a backslashed `output_dir`. `so train --cloud` runs through
  `sokit/cloud.py`, which rewrites both (base model back to its Hub id) and adds `--job.timeout=8h`
  (LeRobot's default cap is 2 days). Checked offline only, by building the staged file without submitting.
- SenseCraft Robotics (Seeed's app, bundles LeRobot 0.6.0) stores its data under the folder named in
  `%LOCALAPPDATA%\SenseCraft Robotics\data-location.json`. It calibrated the follower itself as
  `so100_follower` (offsets differ from `crimson_follower` by up to ~75°), records cameras as `front`
  (overhead) and `gripper` (wrist), uses degrees like LeRobot 0.7.0, and saves trained models in standard
  LeRobot format. A SenseCraft-trained policy must run with SenseCraft's calibration: `so demo --sensecraft`.
  SenseCraft keeps COM ports and cameras open while running: close it before any `so` command.
- API keys for the `so demo` camera check live in the git-ignored `.env` (the team laptop's OpenAI key
  is named `gpt_api_key`); `sokit.demo.load_env_file` reads it at runtime. Never print, copy or commit it.
- `so demo` relies on two LeRobot 0.7.0 internals: `RolloutController` (public) and
  `ThreadSafeRobot._observed_positions` (private, read only, for the gripper/end-of-run detectors).
- ACT with LeRobot's defaults has 51.6 M parameters (counted; the docs say "~80M"); a checkpoint is
  197 MB of weights + 394 MB of training state.
- `so vision` (21 Nov 2026): SenseCraft's "battery final dataset" = 257 episodes; 250 labelled from the
  gripper trace, 4,000 frames; ResNet-18 trained 8 min on the RTX 4060 → 99.8 % on 50 unseen episodes,
  never a wrong "in the box", 10 ms per photo. `RETRY_CHECK=local` is set in this laptop's `.env`.
- The five gripper tests in `tests/test_sokit.py` skip unless `lerobot-train` is on PATH (the
  `skipUnless` decorator sits on the `_ramp` helper): run the suite from an activated env, or put the
  env's `Scripts` folder on PATH first.
- Windows PowerShell 5.1 writes `>` / `*>` redirections as UTF-16; for logs other tools read, use
  `2>&1 | Out-File -Encoding utf8`.

## Conventions

- Arm ids (`crimson_follower`, `crimson_leader`) name the calibration files
  (`~/.cache/huggingface/lerobot/calibration/`): never rename or swap them once calibrated.
- Two ways to run the same LeRobot commands, which must agree on arm ids, camera names, resolution and
  task text (`tests/` checks it): `scripts/*.sh` configured by `robot.env` (bash; macOS and Linux), and
  the `so` helper configured by `hackathon.toml` (every system, including native Windows).
- Reference guide: https://hackathonbilbao.eus/guia-so-101 (Spanish). Prefer its commands and flags over
  older LeRobot docs: in 0.7.0, CLIs are `lerobot-*` and deployment uses `lerobot-rollout`, not
  `lerobot-record --policy`.
- `scripts/*.sh` save datasets as `${HF_USER}/crimson_dataset_YYYYMMDD_HHMMSS`; `so record` saves them as
  `<user>/tnt_YYYYMMDD_HHMMSS`. Rollout datasets must be prefixed `rollout_`.
- Commands that move the arms (teleop, record, replay, rollout, calibrate) need a human at the robot.
  Don't run them unattended.
- A teammate works on Apple Silicon (macOS 15): there, run through `conda run -n lerobot …` or
  `~/miniforge3/envs/lerobot/bin/…` when the env isn't activated, and training uses `mps`.
- Camera names in `hackathon.toml` become dataset keys; changing them invalidates trained policies.
- Camera numbers and ports differ per computer: they go in `hackathon.local.toml` (git-ignored, template
  `hackathon.local.toml.example`), never in `hackathon.toml`. On the Windows laptop 0 is the built-in
  webcam, 1 the overhead camera, 2 the wrist camera; always look at `so cameras` pictures before recording.
- Don't commit `outputs/`, `robot.env` or tokens; `hf auth login` stores the token outside the repo.
- Keep `journal/` — it is the team's evidence for the jury (commands, QA reports, eval log).
