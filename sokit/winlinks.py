"""Windows fallback for directory symlinks.

lerobot-train writes `checkpoints/last` as a symlink. On Windows that needs Developer
Mode (or admin); without it the run dies with `WinError 1314` at the first checkpoint
save, i.e. possibly hours into training. The proper fix is `admin-setup.ps1`
(enables Developer Mode). Until that has been run, `install()` makes pathlib fall back
to an NTFS junction, which needs no privilege and behaves the same for our purposes.

Limitation of the fallback: a junction stores an absolute target, so `last` goes stale
if you move the run folder. Use the numbered checkpoint folders after moving.
"""

from __future__ import annotations

import os
import pathlib
import tempfile

_installed = False


def can_symlink() -> bool:
    """True if this process may create symlinks (non-Windows, admin, or Developer Mode)."""
    if os.name != "nt":
        return True
    with tempfile.TemporaryDirectory() as tmp:
        target = pathlib.Path(tmp) / "t"
        target.mkdir()
        try:
            os.symlink("t", pathlib.Path(tmp) / "l", target_is_directory=True)
        except OSError:
            return False
        return True


def install() -> bool:
    """Patch pathlib so directory symlinks degrade to junctions. Returns True if patched."""
    global _installed
    if _installed or os.name != "nt" or can_symlink():
        return _installed
    import _winapi

    orig_symlink_to = pathlib.Path.symlink_to
    orig_is_symlink = pathlib.Path.is_symlink

    def symlink_to(self, target, target_is_directory=False):
        try:
            return orig_symlink_to(self, target, target_is_directory)
        except OSError as exc:
            if getattr(exc, "winerror", None) != 1314:
                raise
            tgt = pathlib.Path(target)
            absolute = tgt if tgt.is_absolute() else self.parent / tgt
            if not absolute.is_dir():
                raise
            _winapi.CreateJunction(str(absolute.resolve()), str(self))

    def is_symlink(self):
        return orig_is_symlink(self) or self.is_junction()

    pathlib.Path.symlink_to = symlink_to
    pathlib.Path.is_symlink = is_symlink
    _installed = True
    return True
