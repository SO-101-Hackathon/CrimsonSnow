# Runbook — Hackathon LeRobot Bilbao, 20–22 Nov 2026

Playbook for this laptop (Acer Nitro V 15, RTX 4060 Laptop 8 GB, Windows 11). Every number and
every warning below was measured or reproduced on this machine on 19 Nov with LeRobot 0.7.0.
On Ubuntu, macOS or WSL, set up with [docs/SETUP.md](docs/SETUP.md); the `so` commands below are the same.

## 0. Before you leave home — three things only you can do

| # | Do this | Why | State on 19 Nov |
|---|---------|-----|-----------------|
| 1 | In a terminal in this folder: `powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1`, then accept the admin prompt (10 seconds, no reboot) | Turns on Windows Developer Mode. Without it plain `lerobot-train` crashes at its first checkpoint (`WinError 1314`, symlink). | **Done.** Plain `lerobot-train` now writes `checkpoints/last` as a real symlink. |
| 2 | Open `hackathon-shell.cmd`, run `hf auth login` and approve the login in the browser | Uploading the dataset is +3 points, and the model/dataset need an account. | **Done.** Uploading was tested with private copies of a dataset and a model, deleted afterwards. The login expires on 19 Dec 2026. |
| 3 | NitroSense → **Performance** mode, charger plugged in | During the benchmarks the GPU sat at ~55 W. More power = faster training. On battery it is far slower. | To do |

Right-click → "Run with PowerShell" does **not** work for step 1 on this Windows: that menu entry starts
the script under the default policy, which blocks every script, so the window closes at once and nothing
changes.

Then run `so doctor` — it should show no warnings except cameras/arms not plugged in.

Being logged in changes what `so` does: `so record` uploads the dataset when the session ends, `so train`
publishes the final model when a run ends, and the recording rollout modes (`episodic`, `dagger`) upload
their datasets too. All of these are **public**. Add `--no-push` to keep a run on the laptop.

Pack: powered USB hub, USB-C→USB-A adapters, charger, power strip, tape (to mark object and camera
positions), something to raise/fix the cameras.

## 1. Every time you sit down

```
hackathon-shell.cmd        (double-click: terminal with the lerobot environment active)
so doctor                  (GPU, login, ports, cameras, calibration, disk - with fixes)
```

`so --help` lists every command, `so <command> --help` its options, `so show` prints the plain
`lerobot-*` commands for the current `hackathon.toml`, and `--dry-run` shows a command without running it
(`so --dry-run record`). Anything `so` does not know is passed straight to lerobot, e.g.
`so train --policy.chunk_size=50`.

## 2. Friday night — make the whole loop work once (≈ 1 h)

Goal: a tiny throwaway dataset goes all the way to the robot moving by itself. Quality is irrelevant.

```
so ports assign            unplug/replug each arm once -> the tool remembers each board's USB serial
so calibrate follower      all joints mid-range, Enter, then move every joint end to end
so calibrate leader        (calibration is copied into calibration/ automatically)
so cameras                 look at outputs\captured_images\opencv_<n>.png, set indices in hackathon.toml
so teleop                  follower mirrors leader, both camera views show up in Rerun
so record -n 5 --name test --no-push
so qa --dataset test_...   (name is printed at the end of `so record`; `so datasets` lists them)
so train --dataset test_... --steps 2000 --no-push      (≈ 11 min)
so rollout                 the arm should at least move towards the object
```

If that works, everything that can break on this laptop has been exercised.

## 3. Saturday — the real dataset

1. **Fix the scene.** Cameras clamped, lighting even (no window light that changes during the day),
   tape marks for object start positions and for the camera feet. Then `so camcheck` → `s` saves the
   reference framing. Run `so camcheck` again after every break: green outlines must sit on the live image.
2. **Record:** `so record` (50 episodes). 10 per object position × 5 positions beats 50 random ones.
   - `→`/`n` save + next, `←`/`r` redo, `Esc`/`q` stop. These are **global** hotkeys: don't type elsewhere.
   - Start each episode from the same rest pose, move without hesitating, same grasp every time.
   - Keep the leader arm and your hands out of the camera views.
   - Read the "Cadence" lines: it must stay ≈ 30 Hz. If not, see Troubleshooting.
   - More later: `so record --resume -n 10` appends to the same dataset.
3. **Check:** `so qa` flags hesitant / unfinished / odd-start episodes. Re-watch flagged ones with
   `so viz -e <n>`; leave bad ones out with `so train --exclude 3,7` (nothing is deleted).
4. **Plan:** `so plan` converts dataset size into steps and hours for this GPU.
5. **Train early:** a quick model first (`so train --steps 5000`, ≈ 27 min) to see real failure modes,
   then the long run. Training keeps the laptop awake — but **do not close the lid**.
6. **Evaluate while it trains:** `so rollout --step 5000` uses only ≈ 0.3 GB of VRAM and 21 ms per
   inference, so it should fit next to a training job (the two were not tested together: watch the
   "Cadence" lines and stop one job if they drop below 30 Hz). Log every attempt: `so eval`.
7. **Iterate on failures:** record more episodes of exactly the cases that fail, or correct the policy
   live with `so rollout dagger` (Space pause, Tab take over / hand back). Retrain overnight.
   Short on time: fine-tune a checkpoint instead of retraining from zero,
   `so train --policy-path outputs/train/<run>/checkpoints/<step>/pretrained_model --steps 10000`
   (≈ 55 min; this ran here on the sample dataset, its quality against a full retrain is not measured).

## 4. Sunday — demo (30 of the 100 points)

Programme (<https://hackathonbilbao.eus/home-page-es>): submissions close at **11:00** (presentation,
dataset and code); presentations 11:30–12:30, 5 minutes per team. Have the video, the dataset and the
repository online by Saturday night.

- `so eval --summary` → pick the checkpoint with the best logged rate (≥ 5 attempts each). An
  intermediate checkpoint is often better than the last one.
- Dress rehearsal: 5 attempts in a row, hands off, exactly as the jury will see it.
- `so camcheck` right before the jury arrives. Same USB sockets as when recording.
- Demo command: `so rollout --step <best> --duration 0` (runs until Ctrl+C; reset the object between attempts),
  or one run per attempt with `--duration 30`: when a run ends, LeRobot moves the arm back to the pose it
  started in and releases the motors (read in the 0.7.0 source, not tried on an arm). Rehearse the one you will use.
- Upload: `so record` pushes the dataset by itself; `so push dataset` does the same by hand (LeRobot's own
  upload: files, dataset card and the `v3.0` version tag, without which LeRobot refuses to load a Hub dataset).
  Model: `so push policy --step <best>`. Both were tested on 19 Nov with private copies that loaded back from
  the Hub. Afterwards open both pages in a private browser window to check they are public.
- Fill the TODOs in `README.md` from `journal/` (commands, QA reports, eval log), commit, push to GitHub (+2).
- 1-minute video: record with a phone; `ffmpeg` is installed in the environment for trimming:
  `ffmpeg -i in.mp4 -ss 00:00:05 -t 60 -vf scale=-2:720 -c:v libx264 -crf 23 -an out.mp4`

## 5. Numbers measured on this laptop

ACT, batch 8, two 640×480 cameras (public dataset `lerobot/svla_so101_pickplace`, 50 episodes):

| precision | steps/s | VRAM | 5k steps | 20k | 40k | 100k |
|-----------|--------:|-----:|---------:|----:|----:|-----:|
| fp32 (default) | 3.1 | 3.7 GB | 27 min | 1 h 48 | 3 h 36 | 9 h 00 |
| fp16 (`train.mixed_precision = "fp16"`) | 3.7 | 3.5 GB | 23 min | 1 h 30 | 3 h 00 | 7 h 30 |

- fp16 and bf16 gave the same loss curve as fp32 over the first 200 steps; fp32 stays the default
  because it is what everyone else (and the mentors) use. Switch if you are short on time.
- Batch 16 is not worth it: 2.0 steps/s (only +7% samples/s) and 6.4 GB VRAM.
- Dataset size → steps: `so plan`. Typical: 50 episodes × 20 s ≈ 30k frames → 8 epochs ≈ 30k steps ≈ 2 h 40.
- ACT inference: 21 ms per 100-action chunk on the GPU (263 MB VRAM), 275 ms on CPU (`--device=cpu` works as an emergency).
- Recording: episode save takes 0.3 s with streaming encoding (default in `so`) vs ≈ 15 s for a 3-second
  episode without it. Loop held 29.6–29.7 Hz with `encoder_threads = 2`.
- ACT as LeRobot configures it has 51.6 M parameters. One saved checkpoint takes ≈ 0.6 GB on disk (197 MB of
  weights + 394 MB of optimizer state). Publishing the final model took 112 s on the home connection.

SmolVLA (fine-tuning `lerobot/smolvla_base`, 100M of 450M parameters trainable) also runs here — the
base model and its vision-language backbone are already downloaded:

| batch | steps/s | samples/s | VRAM |
|------:|--------:|----------:|-----:|
| 4 | 3.4 | 14 | 2.1 GB |
| 8 | 2.5 | 20 | 2.9 GB |

Memory is no obstacle, time is: the reference recipe (batch 64 × 20k steps) would take ≈ 18 h here.
Treat it as an overnight experiment once ACT works: `so train --policy smolvla --batch-size 16 --steps 15000`,
then `so rollout --rtc`. ACT stays the main plan.

No robot yet? The public sample dataset is cached as `sample_so101`, so the whole software path can be
practised offline: `so qa --dataset sample_so101`, `so plan --dataset sample_so101`,
`so train --dataset sample_so101 --steps 500 --no-push`.

## 6. Windows facts (all reproduced here)

| Symptom / question | What is going on | What to do |
|---|---|---|
| `torch.cuda.is_available()` is False after `pip install lerobot` | PyPI's Windows torch wheel is CPU-only | Already fixed here: torch 2.15.0+cu132 from `download.pytorch.org/whl/cu132` |
| `OSError: [WinError 1314]` when a checkpoint is saved | `checkpoints/last` is a symlink; Windows needs Developer Mode | Fixed here on 19 Nov. On another laptop: `powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1` once; `so train` works meanwhile (junction fallback) |
| Right-click → "Run with PowerShell": the window flashes and nothing happens | That menu entry runs the script under the default policy, which blocks every script | Start scripts from a terminal: `powershell -ExecutionPolicy Bypass -File .\<script>.ps1` (applies to that one run only) |
| A dataset recorded before `hf auth login` | It is stored under `local/…`, later ones under your account name | Nothing: `so` looks in both. `so push dataset --dataset <name>` uploads it to your account |
| Long pause after every episode | Guide's command encodes video after the episode | `--dataset.streaming_encoding=true` (default in `so`) |
| `avcodec_open2(h264_nvenc)` error when recording | `--dataset.rgb_encoder.vcodec=auto` picks NVENC, which fails here | Don't use `vcodec=auto`; default SVT-AV1 is fine |
| `HFValidationError ... 'lerobot\smolvla_base'` | `lerobot-train --policy.path=<hub id>` flips `/` to `\` on Windows | Use a local folder. `so train --policy smolvla` downloads and does that for you |
| Bash commands from the guide fail in PowerShell | `\` line continuation, `${HF_USER}`, `/dev/ttyACM0` are Linux syntax | Use `so ...`, or copy from `so show` (prints your shell's syntax, ports are `COM<n>`) |
| Port changed after re-plugging | COM numbers can move | Nothing: `so` finds each arm by USB serial. `so ports` shows the mapping |
| Arm missing after using WSL | `usbipd attach` hands the USB device to WSL | `usbipd detach --busid <id>`; you don't need WSL for the native flow |
| Camera index 0 is the laptop webcam | Built-in camera enumerates first | USB cameras are usually 1 and 2; check with `so cameras` |
| Second camera fails / black on a hub | Two uncompressed streams exceed one USB 2 hub | Plug one camera straight into the laptop; or add `fourcc = "MJPG"` to that camera in `hackathon.toml` (only if the camera supports MJPG) |
| `.\so.ps1` "running scripts is disabled" | PowerShell execution policy | Use `hackathon-shell.cmd` and type `so ...` (no policy change needed) |

## 7. Troubleshooting

| Problem | Check |
|---|---|
| Arm not found | `so ports`. Both USB **and** power on each board? If Device Manager shows the board with a warning icon, let Windows Update install the driver or get it from the chip vendor (WCH): <https://www.wch-ic.com/downloads/CH343SER_EXE.html> (CH343 boards) or <https://www.wch-ic.com/downloads/CH341SER_EXE.html> (CH340 boards). Not verified here — no arm was connected during setup. |
| Follower moves wrong / mirrored | Wrong calibration or swapped ids. `so calib` shows which files exist; recalibrate that arm. Never give the leader the follower's id. |
| Servos jitter or drop out | Power supply swapped (leader and follower can use different voltages — label them), or a cable was plugged with power on. Power off before touching cables. |
| Cadence below 30 Hz while recording | Close other apps; make sure training is not running at the same time; try `encoder_threads = 1`; plug cameras directly. |
| Policy does nothing useful | `so camcheck` (cameras moved or indices swapped?), same task text, same lighting, object in a position you actually recorded. |
| Training cannot find the dataset | The recorded name carries a timestamp. `so datasets` lists them; `so train` picks the newest of the current task automatically. |
| Out of GPU memory | Something else is using the GPU (`nvidia-smi`). Lower `train.batch_size`. |
| Training was interrupted | `so train --resume` continues from the last checkpoint. |

Help: Bravo Robots mentors, the event WhatsApp group, the LeRobot Discord (links in the guide).
Offline copies of the guide and the LeRobot docs: `docs\offline\`. They exist on the team laptop only
and are not in the repository; the originals are <https://hackathonbilbao.eus/guia-so-101> and
<https://huggingface.co/docs/lerobot>.

## 8. Where the points are

| Criterion | Pts | What moves it |
|---|---:|---|
| Live demo — 5 attempts in a row, 6 pts each | 30 | Reliability over ambition. Fixed cameras + lighting, taped positions, best checkpoint chosen from `so eval`, dress rehearsal. 3/5 is already a good demo. |
| Data and training | 20 | Show the numbers: episodes recorded/discarded (`so qa`), variety per position, loss curves (`trackio show --project lerobot`), what you changed after the first model. `journal/` records all of it. |
| Task difficulty | 15 | Realistic for 48 h; tolerance to position/light changes counts. Add variation only after the fixed case works. |
| Utility and impact | 15 | Frame the task as a real problem (sorting, kitting, tidying…). |
| Innovation | 10 | An original angle on the task or the setup. |
| Presentation and team | 10 | 3 minutes: problem → data → iteration → result. Know your numbers. |
| Bonus | +5 | Public dataset on the Hub (+3), reproducible repository (+2: this repo, pushed to GitHub with the README filled in). |

## 9. Fallbacks

- **No time / GPU busy:** train in the cloud with `so train --cloud a100-large` (Hugging Face Jobs, billed
  by the minute from prepaid credits; `hf jobs hardware` lists machines and prices: A100 80 GB $2.50/h,
  A10G $1.00/h on 19 Nov) or the official Colab notebook (link in `docs\offline\notebooks.txt`).
  - Needs a positive credit balance on huggingface.co/settings/billing (on 19 Nov the account had none),
    so **no job was ever run from this laptop**. Only the config the job receives was checked offline.
  - SmolVLA's full recipe: `so train --policy smolvla --cloud a100-large --batch-size 64 --steps 20000`
    (≈ 4 h on an A100 per the LeRobot docs, ≈ $10).
  - `so` caps a job at 8 h (`--job.timeout=3h` to change); LeRobot's own default is 2 days of billing.
  - The dataset must be on the Hub under your account (`so record` uploads it when logged in). The trained
    model lands in `<you>/<policy>_<task>`; run it with `so rollout --policy <you>/<policy>_<task>`.
  - Watch: `hf jobs ps`, `hf jobs logs <id>`; stop and stop paying: `hf jobs cancel <id>`. Ctrl-C in the
    terminal only detaches, the job keeps running. Loss curves are off unless you add
    `--trackio.space_id=<you>/<space>`.
- **Native Windows flow blocked by something unexpected:** SenseCraft Robotics (Windows desktop app from
  Seeed, guided, ACT only; download link in `docs\offline\hackathon_guia_so101.txt`) is the guide's other
  Windows option. The guide's WSL path is not installed: it can drive the arms through `usbipd`, but USB
  cameras do not work there without a custom kernel. If a mentor insists on it:
  `powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1 -WithWSL` (installs WSL 2, Ubuntu and
  usbipd-win; may need a reboot), then follow the guide's Linux instructions inside Ubuntu.
- **A teammate's laptop takes over:** clone the repo, follow README > Setup, then `so calib restore`
  brings back this pair of arms' calibration.
