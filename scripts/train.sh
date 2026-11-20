#!/usr/bin/env bash
# Train ACT: scripts/train.sh <dataset_name_with_timestamp> [STEPS] [extra args]
# Resume: lerobot-train --config_path=outputs/train/$JOB_NAME/checkpoints/last/pretrained_model/train_config.json --resume=true
# No GPU? add: --job.target=a10g-small  (Hugging Face Jobs, paid)
source "$(dirname "$0")/_common.sh"
DS="${1:?usage: $0 <dataset_name_with_timestamp> [steps]}"; STEPS="${2:-20000}"
shift $(( $# >= 2 ? 2 : 1 ))
cd "$ROOT"
lerobot-train \
  "--dataset.repo_id=${HF_USER}/${DS}" --policy.type=act \
  "--output_dir=outputs/train/${JOB_NAME}" "--job_name=${JOB_NAME}" \
  "--policy.device=${DEVICE}" "--policy.repo_id=${HF_USER}/${POLICY_NAME}" \
  "--steps=${STEPS}" "$@"
