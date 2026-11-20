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

**If you already copied `robot.env` before this change:** set `TASK="Put the battery in the bin"` in it
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

## Still to do at the venue

- `so teleop` on the Windows laptop: confirm the follower mirrors the leader with the copied calibration.
- `so camcheck`: save the reference camera frames into `calibration/camera_refs/`.
