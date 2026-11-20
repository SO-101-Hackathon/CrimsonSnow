#!/usr/bin/env bash
# Teleoperate follower with leader, cameras shown in rerun.
source "$(dirname "$0")/_common.sh"
lerobot-teleoperate "${FOLLOWER_ARGS[@]}" "--robot.cameras=${CAMERAS}" \
  "${LEADER_ARGS[@]}" --display_data=true "$@"
