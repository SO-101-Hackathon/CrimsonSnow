"""Upload a local dataset to the Hub the way `lerobot-record` does when a session ends.

    python -m sokit.push <user/name> <local dataset folder> [--private]

Why not a plain `hf upload`: LeRobot refuses to load a Hub dataset that has no
codebase-version tag ("Your dataset must be tagged with a codebase version").
`LeRobotDataset.push_to_hub` uploads the files (skipping the temporary images/ folder),
writes the dataset card and sets that tag, so the result is the same as what `so record`
uploads by itself. Running it again after `so record --resume` only sends what changed.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sokit.push", description="Upload a local LeRobot dataset to the Hub.")
    ap.add_argument("repo_id", help="destination, e.g. user/pickplace_20261121_101500")
    ap.add_argument("root", help="local dataset folder")
    ap.add_argument("--private", action="store_true", help="create the repo as private (default: public)")
    args = ap.parse_args(argv)

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    dataset = LeRobotDataset(args.repo_id, root=args.root)
    url = f"https://huggingface.co/datasets/{args.repo_id}"
    print(f"[so] uploading {dataset.meta.total_episodes} episodes / {dataset.meta.total_frames} frames "
          f"to {url} ({'private' if args.private else 'public'}) ...")
    dataset.push_to_hub(private=args.private)
    print(f"[so] uploaded: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
