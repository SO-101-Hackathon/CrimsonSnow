"""Submit a lerobot-train run to Hugging Face Jobs from Windows.

    python -m sokit.cloud [--base-model=<hub id>] lerobot-train --job.target=a100-large ...

Behaves like `lerobot-train --job.target=...`, which stages a train_config.json on the Hub
for the cloud machine to run. Written on Windows, that file carries Windows paths the Linux
machine cannot use:

- `policy.pretrained_path` is the local snapshot folder `so` passes as `--policy.path`
  (a Hub id cannot be passed directly on Windows, see `cli._local_model`);
- `output_dir` is spelled with backslashes.

This shim rewrites both in the staged file: the base model becomes its Hub id again and the
output folder gets forward slashes. Nothing else about the run changes.
"""

from __future__ import annotations

import json
import sys
from importlib.metadata import entry_points
from pathlib import Path


def fix_remote_config(data: dict, base_model: str | None) -> dict[str, tuple[str, str]]:
    """Make a staged train config usable on the Linux pod. Returns {field: (before, after)}."""
    changed: dict[str, tuple[str, str]] = {}
    policy = data.get("policy")
    if isinstance(policy, dict) and policy.get("pretrained_path"):
        before = str(policy["pretrained_path"])
        if base_model:
            policy["pretrained_path"] = base_model
            changed["policy.pretrained_path"] = (before, base_model)
        elif Path(before).exists() or "\\" in before or ":" in before:
            raise SystemExit(
                f"[so] the base model is a folder on this computer ({before}); a cloud job cannot read it.\n"
                "     Upload it first (so push policy ...) and pass its Hub id with --policy-path <you>/<repo>."
            )
    out = data.get("output_dir")
    if isinstance(out, str) and "\\" in out:
        data["output_dir"] = out.replace("\\", "/")
        changed["output_dir"] = (out, data["output_dir"])
    return changed


def install(base_model: str | None) -> None:
    """Wrap LeRobot's staging step so the file it uploads is fixed first."""
    from lerobot.jobs import hf

    original = hf.build_remote_config_file

    def build_remote_config_file(cfg, repo_id, dest, tags=None):
        path = original(cfg, repo_id, dest, tags=tags)
        data = json.loads(Path(path).read_text())
        for field, (before, after) in fix_remote_config(data, base_model).items():
            print(f"[so] cloud config: {field} = {after}   (was {before})")
        Path(path).write_text(json.dumps(data, indent=4))
        return path

    hf.build_remote_config_file = build_remote_config_file


def main() -> None:
    args = sys.argv[1:]
    base_model = None
    if args and args[0].startswith("--base-model="):
        base_model = args.pop(0).split("=", 1)[1] or None
    if not args:
        raise SystemExit("usage: python -m sokit.cloud [--base-model=<hub id>] <lerobot-script> [args...]")
    name = args[0]
    matches = [ep for ep in entry_points(group="console_scripts") if ep.name == name]
    if not matches:
        raise SystemExit(f"unknown console script: {name}")
    install(base_model)
    func = matches[0].load()
    sys.argv = [name] + args[1:]
    sys.exit(func())


if __name__ == "__main__":
    main()
