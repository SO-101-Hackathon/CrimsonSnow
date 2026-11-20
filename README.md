# CrimsonSnow — SO-101 battery reject station

Team CrimsonSnow, Hackathon LeRobot Bilbao (II edición, 20–22 Nov 2026). An SO-101 arm picks the
battery out of a tray of rubbish and drops it in a bin. It learns the task from teleoperated
demonstrations with ACT on LeRobot **v0.7.0**, following the
[official hackathon guide](https://hackathonbilbao.eus/guia-so-101).

| | |
|---|---|
| Task | `Put the battery in the bin`: four objects shuffled over five places on an arc; only the battery is picked up |
| Robot | SO-101 leader + follower (6 axes each), 2 USB cameras (`top`, `wrist`), 640×480 @ 30 fps |
| Policy | ACT, trained with LeRobot **v0.7.0** |
| Dataset | TODO `https://huggingface.co/datasets/<user>/<dataset>` |
| Model | TODO `https://huggingface.co/<user>/<policy>` |
| Live demo result | TODO `x / 5` consecutive successes |
| 1-minute video | TODO link |

Everything needed to repeat our result is in this repository:

- the setup on each operating system: [docs/SETUP.md](docs/SETUP.md), and what we set up when:
  [docs/SETUP_LOG.md](docs/SETUP_LOG.md)
- the configuration: [hackathon.toml](hackathon.toml) and [robot.env.example](robot.env.example)
- the station layout and recording plan: [docs/strategy/](docs/strategy/), with the order of
  arrangements in [recording-list.csv](docs/strategy/recording-list.csv)
- the commands we ran, in order: `journal/commands.md` (written by the `so` helper as we work)
- our evaluation log and dataset quality reports: `journal/eval.csv`, `journal/qa_*.md`
- the arm calibration and reference camera framings: `calibration/`

## 1. Install

Requirements: an SO-101 leader/follower pair, two USB cameras, a computer with Python 3.12.
The hackathon provides **no GPU**: train on your own NVIDIA card, on Mac MPS (slow, fine for short
tests), in Colab, or on Hugging Face Jobs (`--job.target=a10g-small`, paid).

**Ubuntu, macOS, WSL**

```bash
git clone https://github.com/SO-101-Hackathon/CrimsonSnow.git
cd CrimsonSnow
./setup.sh                 # Miniforge if missing + conda env "lerobot" (py3.12) + ffmpeg + lerobot==0.7.0 + `so`
conda activate lerobot
hf auth login              # token needs WRITE access: https://huggingface.co/settings/tokens
so doctor                  # checks GPU, ffmpeg, login, ports, cameras, and says how to fix what is missing
```

**Windows 11, native**

```powershell
# In a Miniforge Prompt, inside this folder
conda create -y -n lerobot -c conda-forge python=3.12 ffmpeg
conda activate lerobot
pip install torch==2.15.0 torchvision --index-url https://download.pytorch.org/whl/cu132
pip install "lerobot[core_scripts,training,feetech]==0.7.0"
pip install -e . --no-deps
powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1    # once: Windows Developer Mode
so doctor
```

[docs/SETUP.md](docs/SETUP.md) explains each step, what differs between systems (port names, camera
indices, permissions) and what was checked on which system. In short: installing, the scripts' syntax
and the `so` helper are checked automatically on Ubuntu, macOS and Windows on every push.

**macOS:** arms show up as `/dev/tty.usbmodem…`. Give your terminal or VS Code **Input Monitoring**
permission (System Settings → Privacy & Security), or the recording keys won't work.

Optional LeLab web UI: `uv tool install --python ~/miniforge3/envs/lerobot/bin/python3.12 git+https://github.com/huggingface/leLab.git && lelab`
(on Apple Silicon, pass the arm64 Python explicitly or uv may pick an x86_64 one and fail to find torch wheels).

## 2. Configure the hardware

Safety: each arm has its **own** power supply, and the two often run at different voltages (e.g. leader
5 V, follower 12 V). Label them and never swap them. Cut power before touching cables.

There are two equivalent ways to run the same official `lerobot-*` commands. Pick one per computer.

| | Bash scripts | `so` helper |
|---|---|---|
| Runs on | macOS, Linux, WSL | macOS, Linux, WSL, native Windows |
| Machine settings | `robot.env` (copied from `robot.env.example`, not committed) | `hackathon.toml` + ports found by USB serial number |
| Find the ports | `lerobot-find-port`, then edit `robot.env` | `so ports assign` |
| Find the cameras | `lerobot-find-cameras opencv`, then edit `robot.env` | `so cameras`, then edit `hackathon.local.toml` |

Both use the same arm ids (`crimson_follower`, `crimson_leader`), camera names (`top`, `wrist`),
resolution and task text, so calibration files, datasets and policies made with one work with the other.
`tests/` fails if the two configurations drift apart.

## 3. Workflow

| Step | Bash scripts | `so` helper |
|---|---|---|
| Calibrate (once per arm) | `scripts/calibrate.sh follower` / `leader` | `so calibrate follower` / `leader` |
| Teleoperate | `scripts/teleop.sh` | `so teleop` |
| Record a new dataset | `scripts/record.sh 60` | `so record` |
| Add more episodes | `scripts/resume_record.sh <dataset> 10` | `so record --resume -n 10` |
| Replay an episode | `scripts/replay.sh <dataset> 0` | `so replay` |
| Check dataset quality | | `so qa` |
| Train ACT | `scripts/train.sh <dataset> 20000` | `so train --steps 20000` |
| Run the policy | `scripts/rollout.sh 60` or `scripts/rollout.sh episodic 10` | `so rollout` |
| Log successes and failures | | `so eval` |

`<dataset>` is the dataset name with its timestamp, e.g. `crimson_dataset_YYYYMMDD_HHMMSS`.

Recording keys: `→`/`n` save and go to the next episode, `←`/`r` redo the episode, `Esc`/`q` finish and upload.

Dataset names get a timestamp suffix. To list them: `ls ~/.cache/huggingface/lerobot/$HF_USER` or
`so datasets`. View one at https://huggingface.co/spaces/lerobot/visualize_dataset.

`so show` prints the plain `lerobot-*` commands for the current `hackathon.toml`, `so <command> --help`
lists options, and `--dry-run` shows a command without running it.

Resume training:

```bash
lerobot-train --config_path=outputs/train/act_crimson/checkpoints/last/pretrained_model/train_config.json --resume=true
so train --resume                  # the same for a run started with `so train`
```

To skip recording and train on our data: `so train --dataset <user>/<dataset>` (downloads it from the Hub).
To skip training and run our policy: `so rollout --policy <user>/<policy>`.

## What we did and why

> **TODO (team)** — the jury asks exactly these:
> - Episodes recorded / discarded, and why (see `journal/qa_*.md`).
> - Camera placement and what each camera sees.
> - What failed after the first training, and what we changed (more episodes of which cases?).
> - Checkpoint comparison (`so eval --summary`).

## Tips from the guide

- Aim for about 10 episodes per object position. Keep the cameras and lighting fixed, keep people out
  of frame, and use the same grasp and home pose every time.
- Plan: Friday, validate the whole flow on a small dataset. Saturday, record the real dataset and start
  training early. Sunday, test and record more episodes of the failure cases.
- Scoring: the live demo is worth 30 pts (5 attempts × 6). Bonus: +3 for a published HF dataset, +2 for
  a reproducible repo.

## Repository layout

```
setup.sh              one-time setup on Ubuntu, macOS and WSL
robot.env.example     machine settings for scripts/*.sh (copy to robot.env)
scripts/              bash wrappers around the official lerobot-* commands
hackathon.toml        settings for the `so` helper: ids, cameras, task, record/train/rollout
sokit/                the `so` helper (also wraps lerobot-*; adds checks, QA, evaluation log)
tests/                checks that run without a robot, on every operating system
docs/SETUP.md         setup per operating system; docs/SETUP_LOG.md: what was set up when
docs/strategy/        station layout, recording plan and the list of arrangements to record
journal/              commands.md (everything run through `so`), eval.csv, qa_*.md
calibration/          arm calibration files + reference camera frames
requirements/         exact package versions of the Windows environment our numbers were measured in
admin-setup.ps1       one-time Windows setup that needs admin (Developer Mode; optional WSL + usbipd-win)
hackathon-shell.cmd   opens a terminal with the environment active (Windows)
RUNBOOK.md            playbook for the 48 hours, written for the team's Windows laptop
```

## Acknowledgements

Built with [LeRobot](https://github.com/huggingface/lerobot) (Hugging Face) on the
[SO-101](https://github.com/TheRobotStudio/SO-ARM100) arm by TheRobotStudio, at the Hackathon LeRobot
Bilbao (II edition, 20–22 November 2026) organised with Bravo Robots.

Links: [LeRobot docs](https://huggingface.co/docs/lerobot) · [SO-101](https://huggingface.co/docs/lerobot/so101) · [Cheat sheet](https://huggingface.co/docs/lerobot/cheat-sheet) · [IL on real robots](https://huggingface.co/docs/lerobot/il_robots)
