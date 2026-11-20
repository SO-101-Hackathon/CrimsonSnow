#!/usr/bin/env bash
# Run the trained policy on the follower.
#   scripts/rollout.sh [DURATION_S]          autonomous, nothing recorded (0 = no limit)
#   scripts/rollout.sh episodic [N]          recorded attempts -> ${HF_USER}/rollout_${JOB_NAME}
# Test an intermediate checkpoint: add --policy.pretrained_revision=010000
source "$(dirname "$0")/_common.sh"
if [[ "${1:-}" == "episodic" ]]; then
  N="${2:-10}"; shift $(( $# >= 2 ? 2 : 1 ))
  lerobot-rollout --strategy.type=episodic \
    "--policy.path=${HF_USER}/${POLICY_NAME}" \
    "${FOLLOWER_ARGS[@]}" "--robot.cameras=${CAMERAS}" "${LEADER_ARGS[@]}" \
    "--dataset.repo_id=${HF_USER}/rollout_${JOB_NAME}" \
    "--dataset.num_episodes=${N}" --dataset.episode_time_s=30 --dataset.reset_time_s=10 \
    "--dataset.single_task=${TASK}" "$@"
else
  D="${1:-60}"; shift || true
  lerobot-rollout --strategy.type=base \
    "--policy.path=${HF_USER}/${POLICY_NAME}" \
    "${FOLLOWER_ARGS[@]}" "--robot.cameras=${CAMERAS}" \
    "--task=${TASK}" "--duration=${D}" --display_data=true "$@"
fi
