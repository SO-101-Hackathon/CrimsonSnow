#!/usr/bin/env bash
# Replay an episode on the follower: scripts/replay.sh <dataset_name> [EPISODE]
source "$(dirname "$0")/_common.sh"
DS="${1:?usage: $0 <dataset_name_with_timestamp> [episode]}"
lerobot-replay "${FOLLOWER_ARGS[@]}" "--dataset.repo_id=${HF_USER}/${DS}" "--dataset.episode=${2:-0}"
