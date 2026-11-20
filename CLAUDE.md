# Project notes for AI assistants

Workspace for the **Hackathon LeRobot Bilbao** (20–22 Nov 2026): imitation learning on an SO-101
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
- ACT with LeRobot's defaults has 51.6 M parameters (counted; the docs say "~80M"); a checkpoint is
  197 MB of weights + 394 MB of training state.

## Conventions

- Arm ids (`h_follower`, `h_leader`) name the calibration files: never change them once calibrated.
- Camera names in `hackathon.toml` become dataset keys; changing them invalidates trained policies.
- Don't commit tokens; `hf auth login` stores the token outside the repo.
- Keep `journal/` — it is the team's evidence for the jury (commands, QA reports, eval log).
