"""Launch a lerobot console script in-process with the Windows symlink fallback applied.

    python -m sokit.lr lerobot-train --dataset.repo_id=... --policy.type=act ...

Behaves exactly like calling `lerobot-train ...` directly; the only difference is that
`sokit.winlinks.install()` runs first. `so` uses this automatically, and only when the
machine cannot create symlinks (Windows without Developer Mode).
"""

from __future__ import annotations

import sys
from importlib.metadata import entry_points


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m sokit.lr <lerobot-script> [args...]")
    name = sys.argv[1]
    matches = [ep for ep in entry_points(group="console_scripts") if ep.name == name]
    if not matches:
        raise SystemExit(f"unknown console script: {name}")

    from . import winlinks

    if winlinks.install():
        print("[so] Developer Mode is off: using junction fallback for the `last` checkpoint link "
              "(proper fix, once: powershell -ExecutionPolicy Bypass -File admin-setup.ps1)")
    func = matches[0].load()
    sys.argv = [name] + sys.argv[2:]
    sys.exit(func())


if __name__ == "__main__":
    main()
