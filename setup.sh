#!/usr/bin/env bash
# One-time setup on Linux (Ubuntu), macOS and WSL. Windows without WSL: see docs/SETUP.md.
#
#   ./setup.sh               LeRobot 0.7.0 for recording and ACT training, plus the `so` helper
#   ./setup.sh --smolvla     also the SmolVLA policy
#   ./setup.sh --check       install nothing, only report what this script would do
#
# It creates a conda environment called `lerobot` (override: SO_ENV=name ./setup.sh) and never
# uses sudo. Steps that need administrator rights are printed at the end for you to run.
set -euo pipefail
cd "$(dirname "$0")"

ENV_NAME="${SO_ENV:-lerobot}"
LEROBOT_VERSION="0.7.0"
EXTRAS="core_scripts,training,feetech"
CHECK=0
for arg in "$@"; do
  case "$arg" in
    --smolvla)   EXTRAS="$EXTRAS,smolvla" ;;
    --diffusion) EXTRAS="$EXTRAS,diffusion" ;;
    --check)     CHECK=1 ;;
    -h|--help)   sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (see ./setup.sh --help)" >&2; exit 2 ;;
  esac
done

OS="$(uname -s)"
ARCH="$(uname -m)"
WSL=0
if [ "$OS" = "Linux" ] && grep -qi microsoft /proc/version 2>/dev/null; then WSL=1; fi
case "$OS" in
  Linux)  PLATFORM=$([ "$WSL" = 1 ] && echo "WSL" || echo "Linux") ;;
  Darwin) PLATFORM="macOS" ;;
  *) echo "This script supports Linux, macOS and WSL. On Windows follow docs/SETUP.md." >&2; exit 1 ;;
esac
echo "== SO-101 setup on $PLATFORM ($ARCH): environment '$ENV_NAME', lerobot[$EXTRAS]==$LEROBOT_VERSION"

if ! command -v conda >/dev/null 2>&1; then
  cat >&2 <<EOF
conda was not found. Install Miniforge, then close and reopen the terminal and run ./setup.sh again:

  curl -LO "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$OS-$ARCH.sh"
  bash "Miniforge3-$OS-$ARCH.sh"
EOF
  exit 1
fi

if [ "$CHECK" = 1 ]; then
  echo "conda: $(conda --version)"
  if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "environment '$ENV_NAME' exists"
  else
    echo "environment '$ENV_NAME' would be created (python 3.12 + ffmpeg from conda-forge)"
  fi
  exit 0
fi

# shellcheck disable=SC1091
eval "$(conda shell.bash hook)"
if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "-- environment '$ENV_NAME' already exists: reusing it"
else
  # ffmpeg from conda-forge brings the libsvtav1 encoder LeRobot records video with.
  conda create -y -n "$ENV_NAME" -c conda-forge python=3.12 ffmpeg
fi
conda activate "$ENV_NAME"

if [ "$WSL" = 1 ]; then
  # LeRobot's install guide: WSL needs evdev for keyboard control while recording.
  conda install -y -c conda-forge evdev
fi

python -m pip install --upgrade pip
python -m pip install "lerobot[$EXTRAS]==$LEROBOT_VERSION"
python -m pip install -e . --no-deps   # this repository's `so` helper

echo
echo "== Installed. Checking the environment:"
so doctor || true

cat <<EOF

== Next steps
  conda activate $ENV_NAME
  hf auth login            # only if you want to upload datasets and models
  so doctor                # repeat until it reports no problems
EOF

if [ "$PLATFORM" = "Linux" ] || [ "$PLATFORM" = "WSL" ]; then
  cat <<'EOF'

== Needs administrator rights (run these yourself, once)
  sudo usermod -aG dialout $USER     # lets you open the arms' serial ports; then log out and in
  sudo apt remove brltty             # Ubuntu only, if a board never shows up as /dev/ttyACM*
EOF
fi
if [ "$PLATFORM" = "WSL" ]; then
  cat <<'EOF'

== WSL: share the USB devices from Windows (PowerShell as administrator)
  winget install --interactive --exact dorssel.usbipd-win
  usbipd list
  usbipd bind --busid <BUSID>
  usbipd attach --wsl --busid <BUSID>      # repeat after every re-plug
  USB cameras do not work in WSL without a custom kernel: record on native Windows,
  Linux or macOS, and use WSL for training. See docs/SETUP.md.
EOF
fi
if [ "$PLATFORM" = "macOS" ]; then
  cat <<'EOF'

== macOS
  Allow camera access for your terminal app when macOS asks (System Settings > Privacy & Security > Camera).
  Training on Apple GPUs is slow: train on an NVIDIA computer, in Colab, or with `so train --cloud a10g-small`.
EOF
fi
