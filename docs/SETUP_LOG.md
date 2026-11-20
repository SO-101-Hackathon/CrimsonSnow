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

## Still to do at the venue

- `so ports assign`: identify leader and follower by USB serial number.
- `so calibrate follower`, `so calibrate leader`: results are copied into `calibration/`.
- `so cameras`: set the two camera indices in `hackathon.toml`.
- `so camcheck`: save the reference camera frames into `calibration/camera_refs/`.
