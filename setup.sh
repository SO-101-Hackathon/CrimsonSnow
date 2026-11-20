#!/usr/bin/env bash
# One-time setup on Linux (Ubuntu), macOS and WSL, per https://hackathonbilbao.eus/guia-so-101
# Windows without WSL: see docs/SETUP.md.
#
#   ./setup.sh               Miniforge if missing, conda env "lerobot" (Python 3.12), ffmpeg,
#                            lerobot==0.7.0 for recording and ACT training, and the `so` helper
#   ./setup.sh --smolvla     also the SmolVLA policy
#   ./setup.sh --check       install nothing, only report what this script would do
#
# Never uses sudo. Steps that need administrator rights are printed at the end for you to run.
set -euo pipefail
cd "$(dirname "$0")"

ENV_NAME="${SO_ENV:-lerobot}"
LEROBOT_VERSION=0.7.0
EXTRAS="core_scripts,training,feetech"
CHECK=0
for arg in "$@"; do
  case "$arg" in
    --smolvla)   EXTRAS="$EXTRAS,smolvla" ;;
    --diffusion) EXTRAS="$EXTRAS,diffusion" ;;
    --check)     CHECK=1 ;;
    -h|--help)   sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
echo ">> SO-101 setup on $PLATFORM ($ARCH): environment '$ENV_NAME', lerobot[$EXTRAS]==$LEROBOT_VERSION"

have_conda() { command -v conda >/dev/null 2>&1 || [ -x "$HOME/miniforge3/bin/conda" ]; }
env_exists() { "$CONDA" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; }

if [ "$CHECK" = 1 ]; then
  if have_conda; then
    CONDA="$(command -v conda || echo "$HOME/miniforge3/bin/conda")"
    echo "conda: $("$CONDA" --version)"
    if env_exists; then echo "environment '$ENV_NAME' exists"; else echo "environment '$ENV_NAME' would be created"; fi
  else
    echo "conda is missing: Miniforge would be installed into $HOME/miniforge3"
  fi
  exit 0
fi

if ! have_conda; then
  echo ">> Installing Miniforge into $HOME/miniforge3"
  tmp="$(mktemp -d)"
  curl -fsSLo "$tmp/miniforge.sh" "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$OS-$ARCH.sh"
  bash "$tmp/miniforge.sh" -b -p "$HOME/miniforge3"
  "$HOME/miniforge3/bin/conda" init "$(basename "${SHELL:-bash}")"
fi
CONDA="$(command -v conda || echo "$HOME/miniforge3/bin/conda")"

if env_exists; then
  echo ">> Conda env '$ENV_NAME' already exists: reusing it"
else
  echo ">> Creating conda env '$ENV_NAME' (python 3.12)"
  "$CONDA" create -y -n "$ENV_NAME" python=3.12
fi
# ffmpeg from conda-forge brings the libsvtav1 encoder LeRobot records video with.
"$CONDA" install -y -n "$ENV_NAME" ffmpeg -c conda-forge
if [ "$WSL" = 1 ]; then
  # LeRobot's install guide: WSL needs evdev for keyboard control while recording.
  "$CONDA" install -y -n "$ENV_NAME" evdev -c conda-forge
fi

in_env() { "$CONDA" run --no-capture-output -n "$ENV_NAME" "$@"; }
in_env python -m pip install "lerobot[$EXTRAS]==$LEROBOT_VERSION"
in_env python -m pip install -e . --no-deps   # this repository's `so` helper

[ -f robot.env ] || cp robot.env.example robot.env   # machine config for scripts/*.sh

in_env python -c "import lerobot, torch; print('lerobot', lerobot.__version__, '| torch', torch.__version__, '| mps', torch.backends.mps.is_available(), '| cuda', torch.cuda.is_available())"
echo
echo ">> Checking the environment (warnings about arms and cameras are normal before they are plugged in):"
in_env so doctor || true

cat <<MSG

Done. Next:
  conda activate $ENV_NAME      (new terminal first, if Miniforge was just installed)
  hf auth login                 # token with WRITE access: https://huggingface.co/settings/tokens
  so ports assign               # or: lerobot-find-port, then edit robot.env
MSG

if [ "$PLATFORM" = "Linux" ] || [ "$PLATFORM" = "WSL" ]; then
  cat <<'MSG'

Needs administrator rights (run these yourself, once):
  sudo usermod -aG dialout $USER     # lets you open the arms' serial ports; then log out and in
  sudo apt remove brltty             # Ubuntu only, if a board never shows up as /dev/ttyACM*
MSG
fi
if [ "$PLATFORM" = "WSL" ]; then
  cat <<'MSG'

WSL: share the USB devices from Windows (PowerShell as administrator):
  winget install --interactive --exact dorssel.usbipd-win
  usbipd list
  usbipd bind --busid <BUSID>
  usbipd attach --wsl --busid <BUSID>      # repeat after every re-plug
  USB cameras do not work in WSL without a custom kernel: record on native Windows,
  Linux or macOS, and use WSL for training. See docs/SETUP.md.
MSG
fi
if [ "$PLATFORM" = "macOS" ]; then
  cat <<'MSG'

macOS: in System Settings > Privacy & Security, give your terminal or VS Code
  Camera access (for the cameras) and Input Monitoring (or the recording keys won't work).
  Training on Apple GPUs is slow: use Colab or Hugging Face Jobs for the real run.
MSG
fi
