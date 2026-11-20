#!/usr/bin/env bash
# Add episodes to an existing dataset:
#   scripts/resume_record.sh crimson_dataset_YYYYMMDD_HHMMSS [NUM_NEW_EPISODES]
# List local datasets: ls ~/.cache/huggingface/lerobot/$HF_USER
source "$(dirname "$0")/_common.sh"
DS="${1:?usage: $0 <dataset_name_with_timestamp> [num_new_episodes]}"; N="${2:-10}"
shift $(( $# >= 2 ? 2 : 1 ))
lerobot-record "${FOLLOWER_ARGS[@]}" "--robot.cameras=${CAMERAS}" "${LEADER_ARGS[@]}" \
  "--dataset.repo_id=${HF_USER}/${DS}" \
  "--dataset.root=${HOME}/.cache/huggingface/lerobot/${HF_USER}/${DS}" \
  "--dataset.num_episodes=${N}" \
  "--dataset.single_task=${TASK}" \
  --resume=true --display_data=true "$@"
