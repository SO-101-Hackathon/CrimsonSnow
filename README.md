# CrimsonSnow

Team CrimsonSnow, Hackathon LeRobot Bilbao (II edición, 20–22 Nov 2026). This repo holds our SO-101 setup on LeRobot **v0.7.0**, based on the [official hackathon guide](https://hackathonbilbao.eus/guia-so-101).

## 1. Install

```bash
./setup.sh                 # Miniforge + conda env "lerobot" (py3.12) + ffmpeg + lerobot==0.7.0
conda activate lerobot
hf auth login              # token needs WRITE access: https://huggingface.co/settings/tokens
```

Optional LeLab web UI: `uv tool install --python ~/miniforge3/envs/lerobot/bin/python3.12 git+https://github.com/huggingface/leLab.git && lelab`
(on Apple Silicon, pass the arm64 Python explicitly or uv may pick an x86_64 one and fail to find torch wheels).

**macOS:** arms show up as `/dev/tty.usbmodem…`. Give your terminal/VS Code **Input Monitoring** permission (System Settings → Privacy & Security), or the recording keys won't work.

## 2. Configure the hardware

```bash
cp robot.env.example robot.env    # setup.sh already does this
lerobot-find-port                 # unplug the arm when asked; repeat for each arm
lerobot-find-cameras opencv       # pick the top and wrist indices
```

Put the ports and camera indices in `robot.env`. That file stays local and is not committed.

Safety: each arm has its **own** power supply, and the two often run at different voltages (e.g. leader 5 V, follower 12 V). Label them and never swap them. Cut power before touching cables.

## 3. Workflow

All scripts read `robot.env` and your HF username.

| Step | Command |
|---|---|
| Calibrate (once per arm) | `scripts/calibrate.sh follower` / `scripts/calibrate.sh leader` |
| Teleoperate | `scripts/teleop.sh` |
| Record new dataset | `scripts/record.sh 50` |
| Add more episodes | `scripts/resume_record.sh crimson_dataset_YYYYMMDD_HHMMSS 10` |
| Replay an episode | `scripts/replay.sh crimson_dataset_YYYYMMDD_HHMMSS 0` |
| Train ACT | `scripts/train.sh crimson_dataset_YYYYMMDD_HHMMSS 20000` |
| Run policy | `scripts/rollout.sh 60` or `scripts/rollout.sh episodic 10` |

Recording keys: `→`/`n` save and go to the next episode, `←`/`r` redo the episode, `Esc`/`q` finish and upload.

Dataset names get a timestamp suffix. To list them: `ls ~/.cache/huggingface/lerobot/$HF_USER`. View one at https://huggingface.co/spaces/lerobot/visualize_dataset.

Resume training:
```bash
lerobot-train --config_path=outputs/train/act_crimson/checkpoints/last/pretrained_model/train_config.json --resume=true
```

## Tips from the guide
- The hackathon has **no GPU**. The options are Mac MPS (slow, fine for short tests), Colab, or HF Jobs (`--job.target=a10g-small`, paid).
- Aim for about 50 episodes for pick-and-place, about 10 per object position. Keep the cameras and lighting fixed, keep people out of frame, and use the same grasp and home pose every time.
- Plan: Friday, validate the whole flow on a small dataset. Saturday, record the real dataset and start training early. Sunday, test and record more episodes of the failure cases.
- Scoring: the live demo is worth 30 pts (5 attempts × 6). Bonus: +3 for a published HF dataset, +2 for a reproducible repo.

Links: [LeRobot docs](https://huggingface.co/docs/lerobot) · [SO-101](https://huggingface.co/docs/lerobot/so101) · [Cheat sheet](https://huggingface.co/docs/lerobot/cheat-sheet) · [IL on real robots](https://huggingface.co/docs/lerobot/il_robots)
