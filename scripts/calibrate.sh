#!/usr/bin/env bash
# Calibrate one arm: scripts/calibrate.sh follower|leader
# Put joints mid-range, press Enter, then move each joint end to end.
source "$(dirname "$0")/_common.sh"
case "${1:-}" in
  follower) lerobot-calibrate "${FOLLOWER_ARGS[@]}" ;;
  leader)   lerobot-calibrate "${LEADER_ARGS[@]}" ;;
  *) echo "usage: $0 follower|leader" >&2; exit 1 ;;
esac
