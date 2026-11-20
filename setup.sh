#!/usr/bin/env bash
# One-shot environment setup (macOS / Linux), per https://hackathonbilbao.eus/guia-so-101
set -euo pipefail
LEROBOT_VERSION=0.7.0

if [[ ! -x "$HOME/miniforge3/bin/conda" ]] && ! command -v conda >/dev/null; then
  echo ">> Installing Miniforge"
  tmp="$(mktemp -d)"
  curl -fsSLo "$tmp/miniforge.sh" "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
  bash "$tmp/miniforge.sh" -b -p "$HOME/miniforge3"
  "$HOME/miniforge3/bin/conda" init "$(basename "$SHELL")"
fi
CONDA="$(command -v conda || echo "$HOME/miniforge3/bin/conda")"

if ! "$CONDA" env list | grep -qE '^lerobot\s'; then
  echo ">> Creating conda env 'lerobot' (python 3.12)"
  "$CONDA" create -y -n lerobot python=3.12
fi
"$CONDA" install -y -n lerobot ffmpeg -c conda-forge
"$CONDA" run -n lerobot pip install "lerobot[core_scripts,training,feetech]==${LEROBOT_VERSION}"

[[ -f robot.env ]] || cp robot.env.example robot.env

"$CONDA" run -n lerobot python -c "import lerobot, torch; print('lerobot', lerobot.__version__, '| torch', torch.__version__, '| mps', torch.backends.mps.is_available(), '| cuda', torch.cuda.is_available())"
cat <<MSG

Done. Next:
  conda activate lerobot
  hf auth login                 # token with WRITE access: https://huggingface.co/settings/tokens
  lerobot-find-port             # then edit robot.env
MSG
