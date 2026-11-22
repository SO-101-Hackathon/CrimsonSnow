# Setup log

Every setup step done for this project, in order, so that someone else can repeat it and the jury can
see what was prepared. **Rule: whoever changes the setup adds a dated line here in the same commit.**
Commands run through `so` are logged separately and automatically in `journal/commands.md`.

## 19 Nov 2026 — team laptop (Windows 11, RTX 4060 Laptop 8 GB)

| Step | What was done | How to repeat it |
|---|---|---|
| Python environment | Conda environment `lerobot`: Python 3.12, ffmpeg from conda-forge | [SETUP.md](SETUP.md), Windows section |
| GPU build of torch | torch 2.15.0 with CUDA (cu132), because PyPI's Windows build has no GPU support | `pip install torch==2.15.0 torchvision --index-url https://download.pytorch.org/whl/cu132` |
| LeRobot | `lerobot==0.7.0` with the extras `core_scripts`, `training`, `feetech`, `smolvla`, `diffusion` | `pip install "lerobot[core_scripts,training,feetech,smolvla,diffusion]==0.7.0"` |
| `so` helper | Editable install of this repository | `pip install -e . --no-deps` |
| Windows Developer Mode | Turned on, so `lerobot-train` can save `checkpoints/last` as a symlink | `powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1` |
| Hugging Face login | Browser login to the team account | `hf auth login` |
| Upload check | A private dataset and a private model were uploaded, loaded back and deleted | `so push dataset --private`, `so push policy --private` |
| SmolVLA base model | Downloaded once so SmolVLA training also works without Wi-Fi | first `so train --policy smolvla` does it |
| Speed measurements | ACT 3.1 training steps per second at batch size 8; details in [RUNBOOK.md](../RUNBOOK.md) | `so train --steps 2000` on any dataset |

## 20 Nov 2026

| Step | What was done | How to repeat it |
|---|---|---|
| Task chosen | `hackathon.toml`: task text `Put the battery in the bin`, short name `battery`, 60 episodes per recording session | edit `[task]` and `[record]` |
| Recording list | 120 object arrangements in a balanced order, plus 10 battery-alone episodes | [strategy/recording-list.csv](strategy/recording-list.csv) |
| Cloud training | `so train --cloud <machine>` now sends a config the cloud machine can read, and stops a job after 8 hours. Checked only by building that config; no paid job has run | `so train --cloud a10g-small` (needs Hugging Face credits) |
| Other operating systems | `setup.sh` for Ubuntu, macOS and WSL; device chosen by LeRobot; sleep prevention and hints per system; tests and CI | [SETUP.md](SETUP.md) |
| Exact versions | Saved every package version of the laptop's environment | [requirements/lock-windows-cu132.txt](../requirements/lock-windows-cu132.txt) |

## 20 Nov 2026 — teammate's laptop (Apple Silicon, macOS 15) and the merge

| Step | What was done | How to repeat it |
|---|---|---|
| macOS scaffold | `setup.sh`, `robot.env.example` and the bash wrappers in `scripts/` were added for the Mac | `./setup.sh`, then edit `robot.env` |
| Two toolchains merged | The Mac scaffold and the Windows `so` helper now live side by side. `setup.sh` is one script for Ubuntu, macOS and WSL and also installs `so` | [SETUP.md](SETUP.md) |
| Shared settings aligned | `hackathon.toml` now uses the arm ids `crimson_follower` / `crimson_leader` (it had `h_follower` / `h_leader`; nothing was calibrated under those). `robot.env.example` now has the task text `Put the battery in the bin` (it had the red-cube example) | a test in `tests/` keeps the two files in agreement |

| First clean-machine check | CI ran `./setup.sh` on fresh Ubuntu and macOS machines and the manual steps on Windows: LeRobot 0.7.0 installed and every test passed on all three. The first attempt on Ubuntu ran out of disk, hence the 15 GB note in SETUP.md | [CI runs](https://github.com/SO-101-Hackathon/CrimsonSnow/actions) |

**If you already copied `robot.env` before this change:** set `TASK="Put the TNT in the bin"` in it (see the 20:45 entry below)
by hand, because `robot.env` is not tracked. Every recording of one dataset must carry the same task text.

## 20 Nov 2026, evening — arms and cameras at the venue

| Step | What was done | How to repeat it |
|---|---|---|
| Calibration | Both arms were calibrated on the teammate's Mac and committed to `calibration/` | `so calibrate follower`, `so calibrate leader` |
| Calibration on the Windows laptop | Copied from the repository into LeRobot's folder; nothing was recalibrated | `git pull`, then `so calib restore` |
| Which arm is which | Follower = USB serial `5B91029724`, leader = USB serial `5B91031270`. Read from `journal/commands.md`: on the Mac the follower was calibrated on `/dev/cu.usbmodem5B910297241` and the leader on `…5B910312701`, and macOS puts the serial number in the port name. On the Windows laptop these are COM5 and COM6 | `so ports assign` does the same by unplugging each arm once |
| Cameras on the Windows laptop | `so cameras`, then looked at the three pictures: 0 = the laptop's own webcam, 1 = overhead camera, 2 = wrist camera. The shared file said wrist = 0, which is right on the Mac and wrong here | `so cameras`, then set the numbers in `hackathon.local.toml` |
| Per-computer settings | New `hackathon.local.toml` (not committed) holds each computer's camera numbers, so `hackathon.toml` no longer has to change per laptop | copy `hackathon.local.toml.example` |
| Check | `so doctor` on the Windows laptop: 0 problems, 0 warnings, both arms and both cameras found | `so doctor` |

## 20 Nov 2026, 19:00 to 20:45 — cameras on the Windows laptop, and the real objects

| Step | What was done | How to repeat it |
|---|---|---|
| Wrist camera dropouts | During teleoperation the wrist camera (`USB2.0_CAM1`) left and rejoined the USB bus, which stops LeRobot with "latest frame is too old". Windows' device log showed it arriving and leaving within the same second, on several sockets, on a hub, and after a restart. It held for a while once the hub was fed from a power bank, then dropped again. Treated as a faulty camera, cable or power feed; a replacement was requested | Check with `so cameras`; the device log is in Event Viewer under Kernel-PnP, Configuration |
| Compressed camera mode | Both cameras support MJPG at 640×480. With it the overhead camera went from 13 to 25 pictures per second and the wrist camera from 27 to 30, because two uncompressed cameras nearly fill one USB 2.0 hub | `fourcc = "MJPG"` per camera in `hackathon.local.toml`. Check first that the camera supports it: `ffmpeg -f dshow -list_options true -i video="<camera name>"` |
| Camera numbers move | After every re-plug or restart the numbers changed (laptop webcam was 0, then 2, then 1). Recording with a stale number would have stored the laptop's own webcam | Always run `so cameras` and look at the pictures after touching a cable |
| Objects chosen | The arm picks up a pink TNT block. A yellow duck, a blue car and a green cube stay on the mat. Task text is now `Put the TNT in the bin`, short name `tnt`, in both `hackathon.toml` and `robot.env.example` | edit `[task]`; `tests/` checks that the two files agree |
| Recording list | 200 episodes: each of the 120 arrangements once, 10 with the TNT alone, then a second pass over the first 70 | [strategy/recording-list.csv](strategy/recording-list.csv); the page source is [strategy/checklist.html](strategy/checklist.html) |

**If you already have a `robot.env`:** set `TASK="Put the TNT in the bin"` in it by hand before recording.

## 21 Nov 2026 — Windows laptop

| Step | What was done | How to repeat it |
|---|---|---|
| Broken package removed | `torchaudio 2.11.0+cu130` had been installed at 00:58 (not in the lock file). It does not match torch `2.15.0+cu132`, and it made every LeRobot import fail (`Could not import module 'AutoProcessor'`). LeRobot does not need it, so it was uninstalled; LeRobot imports again and `pip check` is clean | `pip uninstall -y torchaudio`, then `python -c "import lerobot.datasets"` |
| Anthropic SDK | `anthropic 2.12.0` installed into the `lerobot` environment, for the camera check of `so demo`. Optional: without it (or without `ANTHROPIC_API_KEY`) `so demo` checks the gripper position only | `pip install anthropic` |
| Demo with automatic retries | New `so demo` (`sokit/demo.py`): runs the policy in LeRobot's `RolloutController`, ends a run when the arm is back at rest, returns to the start pose, checks the result (gripper position + Claude on the overhead camera) and runs again if the battery is still on the mat. The two detectors were checked on all 108 recorded battery episodes: the grip check said "held" in 108/108, and the end-of-run check never fired before 93 % of an episode. Checked offline with the real flags: SenseCraft's model loads and runs on the GPU with our cameras renamed. Not yet run on the arm | `so --dry-run demo --sensecraft` |
| Fix plan | Testing found three failures: a turned stick (no attempt at all), grabs below the middle or at the very top of the stick (stuck), and any change of position. Plan chosen: 132 new episodes in one session. 12 setups (3 per place) recorded seven times in a row with only the stick changing (straight, turned left 20°, turned right 20°, straight, moved up 2 cm away from the arm, moved down 2 cm toward it, straight), with 48 single straight recordings (12 per place, one swap each) placed between the setups. Altogether 84 straight + 12 of each change; merged with the 108 old ones that is 240 episodes, exactly 80 % straight, and never below 79.4 % at any point where the session could stop. One model, `battery v2`, trained for about 89,000 steps. Recording sheet: [strategy/recordings.html](strategy/recordings.html) Big changes (45°, 90°) are left out on purpose. A fixed 20-setup exam (E1 to E12 normal, E13 to E16 turned 20°, E17 to E20 moved up/down 2 cm) is run with the current and the new model; the new one is demoed only if it is at least as good on E1 to E12 | [strategy/fix-plan.html](strategy/fix-plan.html) |
| Calibration follows the data | `so try` / `so demo` now use SenseCraft's calibration automatically for any policy whose cameras are `front`/`gripper` (SenseCraft recordings), also when the model was trained outside SenseCraft | `so try --policy <folder>` |
| Manual trials | New `so try`: the `so demo` session without checks or retries. You mark each run `s`/`f` with a note; logged in `journal/eval.csv` for `so eval --summary`. Enter during a run stops the arm (also in `so demo`). The first `so demo --sensecraft` run on the arm (15:56, model "battery sample - ACT") ended with exit code 0 and one logged success | `so try --sensecraft` |
| OpenAI check | `openai 3.57.0` installed. With only an OpenAI key (in the git-ignored `.env`, as `OPENAI_API_KEY` or `gpt_api_key`) `so demo` asks `gpt-5.5`. Tested on 8 overhead frames of our recordings with known answers (4 battery on the mat, 4 in the box): gpt-5.5, gpt-5.4-mini, gpt-4.1-mini and gpt-6.1-sol were all 8/8; with the wrist frame added gpt-5.5 and gpt-5.4-mini stayed 8/8 (about 3.0 s and 1.3 s per answer) | `pip install openai`, key in `.env` (see `.env.example`) |
| SenseCraft models and calibration | SenseCraft calibrated the follower itself (`so100_follower`); its offsets differ from `crimson_follower` by up to ~75° (wrist roll). Its recordings name the cameras `front` (overhead) and `gripper` (wrist). It used COM5 for the follower and COM6 for the leader, matching our USB serial mapping. `so demo --sensecraft` reads SenseCraft's calibration file in place (`sokit/sensecraft.py`) | `so demo --sensecraft` |
| π0.5 cloud job checked offline | The staged config for a π0.5 run on Hugging Face Jobs was built without submitting. Written on Windows it held `lerobot\pi05_base`; `sokit/cloud.py` turns it back into `lerobot/pi05_base`. π0.5 also needs access to the gated `google/paligemma-3b-pt-224` tokenizer | `python -m sokit.cloud --base-model=lerobot/pi05_base lerobot-train --policy.type=pi05 ...` |
| Second recording session and the final model | In SenseCraft: "battery sample 2" recorded from 17:55 to 19:33 (149 episodes, 100,079 frames), merged with "battery sample" into "battery final dataset" (257 episodes, 169,675 frames, about 94 min). ACT, 100,000 steps on an RTX 5090 in SenseCraft's cloud, started after the merge | SenseCraft Robotics: record, merge datasets, train |
| Our own camera check | New `so vision` (`sokit/vision.py`). `prepare` copied the overhead-camera videos of "battery final dataset" out of SenseCraft's folder (654 MB, read only, while SenseCraft kept running) and labelled 250 of the 257 episodes from the gripper trace (7 had no clear grab and release): 16 frames each, 4,000 frames in 46 s. `train`: ResNet-18 with ImageNet weights (already in the torch cache, nothing downloaded), 10 epochs, 8.0 min on the RTX 4060. `test`: 99.8 % right on 800 frames of 50 episodes it never saw (100 % with the arm at rest), 10/10 on real check photos without hands and 7/8 with a hand in the picture, never a wrong "in the box", 10 ms per photo. The model stays in `outputs/vision/model/` (git-ignored); the report is `journal/vision-report.md` | `so vision prepare`, `so vision train`, `so vision test` |
| Control panel | New `so panel` (`sokit/panel.py`, `sokit/panel.html`): a local web page that runs `so demo` / `try` / `teleop` / `cameras` / `doctor` and shows the scoreboard, the photo the check looked at and the journal results. Python standard library only. Checked with 24 robot-free tests, over HTTP in mock mode and through `so --dry-run demo`; not yet used on the arm (SenseCraft held the arm and the cameras) | `so panel` (`so panel --mock` without the robot) |
| Pitch deck | `docs/presentation/CrimsonSnow-pitch.pptx`: 8 slides with speaker notes, 4:40 of talk. `build_deck.py` rebuilds it with python-pptx, installed in a separate virtual environment (the `lerobot` environment was not touched); every slide was exported through PowerPoint and checked by eye. SenseCraft's ACT settings were read from its model config: the same as LeRobot's defaults, so the 51.6 M parameters on the slides apply | `pip install python-pptx` in any Python, then `python docs/presentation/build_deck.py` |
| Video of the whole test | `so demo --record-video` / `so try --record-video`, or the panel's "Record the full test on video" switch: films the session from the robot's own overhead and wrist cameras side by side, with the attempt, the run and each verdict written on top, into `outputs/demo/<session>/test.mp4` (H.264, 15 fps). Frames come from LeRobot's `read_latest()`, which does not take frames away from the control loop. Tested with fake cameras; not yet filmed on the arm | `so demo --sensecraft --record-video` |
| Clutter test, 24/24 and the judges' video | Best test of the final model, filmed with `--record-video`: the battery among 14 other objects, picked first try (`outputs/demo/test video trash/test.mp4`). The team reports 24/24 on all arrangements of the 4 objects over the 4 tapes (the shared test page had 23 ticked at the time). Slides updated (9 slides, 4:40). New 1-minute video for the judges, no sound: `docs/presentation/build_video.py` edits our own footage with a Blender intro (`docs/presentation/intro.blend`, rendered with Eevee in Blender 5.2) into `outputs/video/CrimsonSnow-1min.mp4` | `python docs/presentation/build_video.py` |
| Video with the team's voice-over | `docs/presentation/build_story_video.py` cuts the four Spanish voice-over recordings (80 s raw, 66 s of speech) to 60 s and times every picture to the spoken word (Whisper word times, measured locally); output `outputs/video/CrimsonSnow-1min-ES-voz.mp4`. The recordings stay out of git (`recording/` in `.gitignore`) | `python docs/presentation/build_story_video.py` |
| Choosing the check in `.env` | `RETRY_CHECK` picks the check of `so demo` when no `--check` is given: `local` (our model), `openai`, `claude`, `grip`, or `auto` (the behaviour before this setting). This laptop's `.env` now says `RETRY_CHECK=local`; its API key was left as it was | copy `.env.example` to `.env` |

## 22 Nov 2026 — final delivery

| Step | What was done | How to repeat it |
|---|---|---|
| Public on Hugging Face | Datasets `CrimsonSnowLLC/battery-full-dataset` (281 episodes) and `battery-full-plus-locations` (+12 along the arc, held twice), models `act_battery_full_100k` (100k steps from scratch, A100) and `act_battery_finetune_locations_2026-11-22_03-35-47` (+20k steps on the arc): cards that say how each was made and link to this repository, then switched to public. `battery-sample` (the first session) stays private. | `HfApi().upload_file(..., path_in_repo="README.md")`, then `HfApi().update_repo_settings(repo_id, repo_type, private=False)` |
| Final deck | 9 slides + bonus, 4:30: data in 4 sessions (293 episodes), a new slide 7 with four recorded runs of the final model (9 of 11 logged attempts on the first run, `journal/demo.csv`), the four models on slide 9, the public links. The teammates' edits are kept: the deck is rebuilt from `build_deck.py`, which holds them. | `python docs/presentation/build_demo_clip.py` (lerobot env), then `python docs/presentation/build_deck.py`; `--voice` for the laptop copy with the voiced bonus video (`outputs/presentation/`, not public) |

## Still to do at the venue

- `so teleop` on the Windows laptop: confirm the follower mirrors the leader with the copied calibration.
- `so camcheck`: save the reference camera frames into `calibration/camera_refs/`.
