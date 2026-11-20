# Setup on every operating system

How to get from a fresh computer to `so doctor` reporting no problems, on Ubuntu, macOS, WSL and
native Windows. The steps follow the organisers' guide and LeRobot's install guide for **LeRobot 0.7.0**.

## What has been checked where

| System | Installing and the `so` helper | Recording, training and running a policy |
|---|---|---|
| Windows 11, native (RTX 4060 Laptop) | Run by hand on the team laptop | Software path measured without a robot on 19 Nov 2026; see [RUNBOOK.md](../RUNBOOK.md) |
| Ubuntu | Checked automatically on every push ([CI](../.github/workflows/ci.yml)) | Not run by us |
| macOS (Apple Silicon) | Checked automatically on every push; a teammate's laptop runs it | See [SETUP_LOG.md](SETUP_LOG.md) |
| WSL (Ubuntu) | Same script as Ubuntu; not run by us inside WSL | Not run by us. Cameras need a custom kernel (below) |

"Checked automatically" means a clean machine runs `./setup.sh`, the tests in `tests/` and `so show`.
No robot is attached there, so it proves the install and the commands, not the robot's behaviour.

## Ubuntu, macOS and WSL

```bash
git clone https://github.com/SO-101-Hackathon/CrimsonSnow.git
cd CrimsonSnow
./setup.sh              # add --smolvla for the SmolVLA policy; --check only reports
conda activate lerobot  # open a new terminal first if Miniforge was just installed
so doctor
```

`setup.sh` does the following, and never uses `sudo`:

1. Installs Miniforge into `~/miniforge3` if `conda` is missing.
2. Creates the conda environment `lerobot` with Python 3.12 and ffmpeg from conda-forge.
3. Installs `lerobot[core_scripts,training,feetech]==0.7.0` and this repository's `so` helper.
4. Copies `robot.env.example` to `robot.env`, the machine settings for `scripts/*.sh`.
5. Runs `so doctor` and prints the commands that need administrator rights.

### Ubuntu

- **Serial ports.** The arms appear as `/dev/ttyACM0` and `/dev/ttyACM1`. Your user must be in the
  `dialout` group: `sudo usermod -aG dialout $USER`, then log out and in. `so doctor` checks this.
- **A board never appears.** On Ubuntu the `brltty` package can grab the serial chip:
  `sudo apt remove brltty`.
- **NVIDIA driver.** `nvidia-smi` must work. LeRobot's guide asks for driver 580.65 or newer.
- **Disk space.** The Linux build of torch downloads several GB of NVIDIA libraries. Our first CI run
  on a small Ubuntu machine ran out of disk during `pip install`, so keep 15 GB or more free.

### macOS

- **Serial ports.** The arms appear as `/dev/tty.usbmodem*` (also listed as `/dev/cu.usbmodem*`).
  No driver is needed.
- **Permissions.** In System Settings → Privacy & Security, give your terminal or VS Code Camera
  access and **Input Monitoring**. Without Input Monitoring the recording keys do not work.
- **Training.** It runs on the Apple GPU, slowly. `so train` lets LeRobot pick the device, which is
  `mps` on macOS 15 and the CPU on macOS 14. Train on an NVIDIA computer, in Colab, or with
  `so train --cloud a10g-small`.

### WSL

- **Share the USB devices from Windows**, in PowerShell as administrator:

  ```powershell
  winget install --interactive --exact dorssel.usbipd-win
  usbipd list
  usbipd bind --busid <BUSID>
  usbipd attach --wsl --busid <BUSID>     # repeat after every re-plug
  ```

- **Cameras.** The organisers' guide states that USB cameras do not work in WSL without a custom
  kernel. Record on native Windows, Ubuntu or macOS, and use WSL for training.
- **GPU.** WSL uses the Windows NVIDIA driver. `nvidia-smi` must work inside WSL.
- `setup.sh` also installs `evdev`, which LeRobot needs in WSL for keyboard control while recording.

## Windows 11, native

This is what the team laptop runs. Cameras and the arms' COM ports work directly.

```powershell
# In a Miniforge Prompt
conda create -y -n lerobot -c conda-forge python=3.12 ffmpeg
conda activate lerobot
# PyPI's Windows build of torch has no GPU support: install the CUDA build first
pip install torch==2.15.0 torchvision --index-url https://download.pytorch.org/whl/cu132
pip install "lerobot[core_scripts,training,feetech]==0.7.0"
pip install -e . --no-deps
so doctor
```

- **Developer Mode.** `lerobot-train` saves `checkpoints/last` as a symlink, which Windows only allows
  with Developer Mode on. Run `powershell -ExecutionPolicy Bypass -File .\admin-setup.ps1` once and
  accept the admin prompt. Right-click and "Run with PowerShell" does not work under the default script
  policy. Without Developer Mode, train through `so train`, which falls back to a directory junction.
- **Terminal.** `hackathon-shell.cmd` opens a terminal with the environment active.
- **Exact versions.** [requirements/lock-windows-cu132.txt](../requirements/lock-windows-cu132.txt) lists
  every package version of the environment our numbers were measured in.

## What differs between systems

There are two ways to run the same `lerobot-*` commands: the bash scripts in `scripts/`, configured by
`robot.env`, and the `so` helper, configured by `hackathon.toml`. The scripts need bash, so native
Windows uses `so`. Two kinds of values depend on the computer, whichever you use:

| Setting | Windows | Ubuntu and WSL | macOS |
|---|---|---|---|
| Arm ports | `COM5` | `/dev/ttyACM0` | `/dev/tty.usbmodem…` |
| Camera index | `0` is usually the built-in webcam | index or `/dev/video2` | index |

Everything else must be identical on every computer and in both configurations: the arm ids
(`crimson_follower`, `crimson_leader`), the camera names, the resolution and the task text. A test in
`tests/` fails if `robot.env.example` and `hackathon.toml` disagree on any of them.

- **Ports.** With `so`: leave `port = "auto"` in `hackathon.toml` and run `so ports assign` once. The
  helper remembers each board by its USB serial number, so port names can change without swapping
  leader and follower. With the scripts: run `lerobot-find-port` and put the ports in `robot.env`.
- **Cameras.** Run `so cameras` (or `lerobot-find-cameras opencv`) on each computer and look at
  `outputs/captured_images/opencv_<n>.png` to see which number is which camera. With `so`, put this
  computer's numbers in `hackathon.local.toml` (copy `hackathon.local.toml.example`); that file is not
  committed, so each laptop keeps its own. With the scripts, put them in `robot.env`.
  **Check the pictures before recording:** on a laptop one of the numbers is the built-in webcam, and
  recording with it would put people's faces into a public dataset.
  Camera **names** (`top`, `wrist`) must never change: they are stored in the dataset and a trained
  policy expects them.
- **`hackathon.local.toml`.** Holds one computer's camera numbers and, if wanted, fixed arm ports. It
  cannot change arm ids, camera names, resolution or the task text; `so` refuses to start if it tries.
- **Calibration.** `so calibrate` copies the result into `calibration/`. On another computer with the
  same arms, `so calib restore` reuses it.
- **Device.** `so train` passes no device, so LeRobot uses the best one present: `cuda`, then `mps`,
  then `cpu`. Force one with `so train --device mps`. `scripts/train.sh` uses `DEVICE` from `robot.env`.
- **Staying awake.** During recording and training `so` blocks idle sleep with the system's own tool:
  `SetThreadExecutionState` on Windows, `caffeinate` on macOS, `systemd-inhibit` on Linux.

## Check an installation without a robot

```bash
python -m unittest discover -s tests -v    # runs on any system
so doctor                                  # GPU, ffmpeg, login, ports, cameras
so show                                    # every lerobot command this repository would run
```
