# CrimsonSnow: SO-101 / LeRobot hackathon project

- Stack: LeRobot **0.7.0** (pinned), conda env `lerobot` (Python 3.12, `~/miniforge3`), ffmpeg from conda-forge. Apple Silicon, macOS 15, so train with `--policy.device=mps`.
- Reference guide: https://hackathonbilbao.eus/guia-so-101 (Spanish). Prefer its commands and flags over older LeRobot docs: in 0.7.0, CLIs are `lerobot-*` and deployment uses `lerobot-rollout`, not `lerobot-record --policy`.
- Hardware: SO-101 follower and leader (Feetech STS3215, `feetech` extra), two OpenCV cameras (`top`, `wrist`).
- Machine config lives in `robot.env` (gitignored; template `robot.env.example`). All `scripts/*.sh` source `scripts/_common.sh`, which loads it, resolves `HF_USER` from `hf auth whoami`, and builds the `--robot.cameras` string.
- Robot ids `crimson_follower` / `crimson_leader` key the calibration files (`~/.cache/huggingface/lerobot/calibration/`). Never rename or swap them after calibrating.
- Datasets are saved as `${HF_USER}/crimson_dataset_YYYYMMDD_HHMMSS`. Rollout datasets must be prefixed `rollout_`.
- Run commands through `conda run -n lerobot …` or `~/miniforge3/envs/lerobot/bin/…` when the env isn't activated.
- Commands that move the arms (teleop, record, replay, rollout, calibrate) need a human at the robot. Don't run them unattended.
- Don't commit `outputs/`, `robot.env`, or tokens.
