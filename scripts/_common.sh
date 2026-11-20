#!/usr/bin/env bash
# Shared config for all scripts. Sourced, not executed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$ROOT/robot.env" ]]; then
  echo "Missing $ROOT/robot.env. Run: cp robot.env.example robot.env  (then edit ports)" >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$ROOT/robot.env"

if ! command -v lerobot-record >/dev/null; then
  echo "lerobot not on PATH. Run: conda activate lerobot" >&2
  exit 1
fi

HF_USER="${HF_USER:-$(NO_COLOR=1 hf auth whoami 2>/dev/null | awk -F': *' 'NR==1 {print $2}')}"
if [[ -z "$HF_USER" ]]; then
  echo "Not logged in to Hugging Face. Run: hf auth login" >&2
  exit 1
fi
export HF_USER

CAMERAS="{ top: {type: opencv, index_or_path: ${CAM_TOP}, width: ${CAM_W}, height: ${CAM_H}, fps: ${CAM_FPS}}, wrist: {type: opencv, index_or_path: ${CAM_WRIST}, width: ${CAM_W}, height: ${CAM_H}, fps: ${CAM_FPS}} }"

FOLLOWER_ARGS=(--robot.type=so101_follower "--robot.port=${FOLLOWER_PORT}" "--robot.id=${FOLLOWER_ID}")
LEADER_ARGS=(--teleop.type=so101_leader "--teleop.port=${LEADER_PORT}" "--teleop.id=${LEADER_ID}")
