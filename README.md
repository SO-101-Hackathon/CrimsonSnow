# SO-101 battery reject station — Hackathon LeRobot Bilbao 2026

An SO-101 arm picks the battery out of a tray of rubbish and drops it in a bin. It learned the task
from teleoperated demonstrations with ACT, using LeRobot **v0.7.0**.

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

- the configuration: [hackathon.toml](hackathon.toml)
- the setup on each operating system: [docs/SETUP.md](docs/SETUP.md), and what we set up when:
  [docs/SETUP_LOG.md](docs/SETUP_LOG.md)
- the station layout and recording plan: [docs/strategy/](docs/strategy/), with the order of
  arrangements in [recording-list.csv](docs/strategy/recording-list.csv)
- the commands we ran, in order: `journal/commands.md` (written by the `so` helper as we work)
- our evaluation log and dataset quality reports: `journal/eval.csv`, `journal/qa_*.md`
- the arm calibration and reference camera framings: `calibration/`

## Setup

Requirements: an SO-101 leader/follower pair, two USB cameras, a computer with Python 3.12.
An NVIDIA GPU is needed for fast training; without one use Colab or `so train --cloud`.

**Ubuntu, macOS, WSL**

```bash
# Miniforge first if `conda` is missing: https://github.com/conda-forge/miniforge
git clone https://github.com/SO-101-Hackathon/CrimsonSnow.git
cd CrimsonSnow
./setup.sh
conda activate lerobot
so doctor
```

**Windows 11, native (what we used)**

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
indices, permissions) and what was checked on which system. In short: installing and the `so` helper
are checked automatically on Ubuntu, macOS and Windows on every push; recording and training were run
by us on Windows only.

## Reproduce

All steps read [hackathon.toml](hackathon.toml) (ports, arm ids, cameras, task text, training
settings). `so show` prints the plain `lerobot-*` commands if you prefer to run those yourself;
`so <command> --help` lists options.

```bash
so doctor                 # environment check
so ports assign           # identify leader / follower by USB serial number (once)
so calibrate follower     # or: so calib restore   (to reuse OUR calibration with OUR arms)
so calibrate leader
so cameras                # find camera indices -> edit [cameras] in hackathon.toml
so camcheck               # compare the live framing with calibration/camera_refs/*.png
so teleop                 # sanity check: follower mirrors leader, both camera views visible

so record                 # record.num_episodes demonstrations  (so record --resume -n 10 adds more)
so qa                     # per-episode quality report; flags hesitant / odd episodes
so plan                   # steps and wall-clock for this dataset size on this GPU
so train --steps 30000    # ACT; checkpoints in outputs/train/<run>/checkpoints/
so rollout                # run the newest checkpoint on the robot (so rollout --step 15000 for another)
so eval                   # log success/fail per attempt, compare checkpoints

so push dataset           # publish the dataset by hand (so record already does it when logged in)
so push policy --step 15000   # publish the checkpoint used in the demo
```

To skip recording and train on our data: `so train --dataset <user>/<dataset>` (downloads it from the Hub).
To skip training and run our policy: `so rollout --policy <user>/<policy>`.

## What we did and why

> **TODO (team)** — the jury asks exactly these:
> - Episodes recorded / discarded, and why (see `journal/qa_*.md`).
> - Camera placement and what each camera sees.
> - What failed after the first training, and what we changed (more episodes of which cases?).
> - Checkpoint comparison (`so eval --summary`).

## Repository layout

```
hackathon.toml        single source of truth: ports, ids, cameras, task, record/train/rollout settings
setup.sh              one-time setup on Ubuntu, macOS and WSL
sokit/                the `so` helper (thin wrappers around the official lerobot-* commands)
tests/                checks that run without a robot, on every operating system
docs/SETUP.md         setup per operating system; docs/SETUP_LOG.md: what was set up when
docs/strategy/        station layout, recording plan and the list of arrangements to record
journal/              commands.md (everything we ran), eval.csv (success log), qa_*.md (dataset reports)
calibration/          arm calibration files + reference camera frames
requirements/         exact package versions of the environment our numbers were measured in
admin-setup.ps1       one-time Windows setup that needs admin (Developer Mode; optional WSL + usbipd-win)
hackathon-shell.cmd   opens a terminal with the environment active (Windows)
RUNBOOK.md            our playbook for the 48 hours, written for the team's Windows laptop
```

## Acknowledgements

Built with [LeRobot](https://github.com/huggingface/lerobot) (Hugging Face) on the
[SO-101](https://github.com/TheRobotStudio/SO-ARM100) arm by TheRobotStudio, at the Hackathon LeRobot
Bilbao (II edition, 20–22 November 2026) organised with Bravo Robots.
