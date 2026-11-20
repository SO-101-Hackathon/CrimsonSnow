#!/usr/bin/env bash
# Record a new dataset: scripts/record.sh [NUM_EPISODES] [extra lerobot args]
# Keys: -> / n save+next, <- / r redo episode, Esc / q finish+upload.
# Output name gets a timestamp suffix: ${DATASET_NAME}_YYYYMMDD_HHMMSS
source "$(dirname "$0")/_common.sh"
N="${1:-50}"; shift || true
lerobot-record "${FOLLOWER_ARGS[@]}" "--robot.cameras=${CAMERAS}" "${LEADER_ARGS[@]}" \
  "--dataset.repo_id=${HF_USER}/${DATASET_NAME}" \
  "--dataset.num_episodes=${N}" \
  "--dataset.single_task=${TASK}" \
  --display_data=true "$@"
