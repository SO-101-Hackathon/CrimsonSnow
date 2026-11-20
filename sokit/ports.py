"""Serial-port discovery for the SO-101 arms.

COM numbers (Windows) and /dev/ttyACM* order (Linux) can change when cables are
re-plugged. Swapping leader and follower silently produces wrong motion, so we
identify each controller board by its USB serial number once (`so ports assign`)
and resolve the right port by serial every time a command runs.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

ROLES = ("follower", "leader")


@dataclass
class PortInfo:
    device: str
    serial: str | None
    vid: int | None
    pid: int | None
    location: str | None
    description: str

    @property
    def usb_id(self) -> str:
        if self.vid is None or self.pid is None:
            return "----:----"
        return f"{self.vid:04X}:{self.pid:04X}"

    def label(self) -> str:
        return (
            f"{self.device:<14} usb={self.usb_id} serial={self.serial or '-':<14} "
            f"loc={self.location or '-':<10} {self.description}"
        )


def list_ports(usb_only: bool = True) -> list[PortInfo]:
    from serial.tools import list_ports as lp

    out = []
    for p in lp.comports():
        if usb_only and p.vid is None:
            continue  # skip Bluetooth / legacy ports
        out.append(
            PortInfo(
                device=p.device,
                serial=p.serial_number or None,
                vid=p.vid,
                pid=p.pid,
                location=p.location or None,
                description=p.description or "",
            )
        )
    return sorted(out, key=lambda x: x.device)


def _missing_port_hint() -> str:
    """What to check on this operating system when a board does not show up as a serial port."""
    import os
    import sys

    if os.name == "nt":
        return ("Windows: if a board shows up in Device Manager with a warning icon, install the WCH "
                "CH343 driver (see RUNBOOK).")
    if sys.platform == "darwin":
        return "macOS: the boards appear as /dev/cu.usbmodem* without a driver. Try another cable or hub."
    return ("Linux: the boards appear as /dev/ttyACM*. Your user must be in the 'dialout' group "
            "(`so doctor` checks this). On Ubuntu, `brltty` can grab the port: sudo apt remove brltty.\n"
            "WSL: attach each board first from Windows: usbipd attach --wsl --busid <id>  (docs/SETUP.md).")


def _wait_for_change(before: set[str], want_removed: bool, timeout_s: float = 60.0) -> set[str]:
    """Poll until a port disappears (want_removed) or appears; return the changed device names."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        now = {p.device for p in list_ports()}
        diff = (before - now) if want_removed else (now - before)
        if diff:
            time.sleep(0.8)  # let enumeration settle
            return diff
        time.sleep(0.3)
    return set()


def assign_wizard(state: dict) -> dict:
    """Interactive: identify which USB serial belongs to which arm. Updates and returns state."""
    print("\n== Identify the arms (USB power + USB cable connected on BOTH arms) ==")
    ports = list_ports()
    if len(ports) < 2:
        print(f"Found {len(ports)} USB serial port(s); need 2 (leader + follower):")
        for p in ports:
            print("  ", p.label())
        print("Check: both USB cables plugged, boards powered.\n" + _missing_port_hint())
        if not ports:
            return state
    for p in ports:
        print("  ", p.label())

    assigned: dict[str, PortInfo] = {}
    for role in ROLES:
        before_info = {p.device: p for p in list_ports()}
        input(f"\n>> UNPLUG the USB cable of the {role.upper()} arm, then press Enter... ")
        gone = set(before_info) - {p.device for p in list_ports()}
        if not gone:
            print("   No port disappeared yet, waiting up to 30 s...")
            gone = _wait_for_change(set(before_info), want_removed=True, timeout_s=30)
        if len(gone) != 1:
            print(f"   Expected exactly one port to disappear, got {sorted(gone) or 'none'}. Aborting.")
            return state
        dev = next(iter(gone))
        info = before_info[dev]
        assigned[role] = info
        print(f"   {role.upper()} = {info.label()}")
        print("   Plug it back in now...")
        back = _wait_for_change(set(before_info) - {dev}, want_removed=False, timeout_s=60)
        if not back:
            print("   (did not see it come back within 60 s; continue once it is plugged)")

    if len(assigned) == 2:
        a, b = assigned["follower"], assigned["leader"]
        if a.serial and a.serial == b.serial:
            print("\n!! Both boards report the SAME USB serial. Falling back to physical USB location;")
            print("   keep each cable in the same USB socket / hub port from now on.")
            for info in assigned.values():
                info.serial = None
        elif not a.serial or not b.serial:
            print("\n!! A board has no USB serial number. Matching by physical USB location instead;")
            print("   keep each cable in the same USB socket / hub port from now on.")
    state.setdefault("arms", {})
    for role, info in assigned.items():
        state["arms"][role] = asdict(info)
    print("\nSaved. `so ports` shows the current mapping; commands will pick the right port automatically.")
    return state


def resolve(role: str, configured: str, state: dict) -> str:
    """Return the serial device for an arm. `configured` is the value from hackathon.toml."""
    if configured and configured.lower() != "auto":
        return configured
    saved = (state.get("arms") or {}).get(role)
    ports = list_ports()
    if not saved:
        raise SystemExit(
            f"Port for the {role} arm is 'auto' but the arms were never identified.\n"
            f"Run:  so ports assign     (or set an explicit port in hackathon.toml)"
        )
    if saved.get("serial"):
        hits = [p for p in ports if p.serial == saved["serial"]]
    else:
        hits = [p for p in ports if p.location and p.location == saved.get("location")]
    if len(hits) == 1:
        return hits[0].device
    listing = "\n".join("   " + p.label() for p in ports) or "   (no USB serial ports present)"
    key = f"serial {saved['serial']}" if saved.get("serial") else f"USB location {saved.get('location')}"
    raise SystemExit(
        f"Cannot find the {role} arm ({key}); {len(hits)} matching port(s).\n"
        f"Ports present now:\n{listing}\n"
        f"Check the USB cable / power, or re-run:  so ports assign"
    )


def show(state: dict) -> None:
    ports = list_ports(usb_only=False)
    arms = state.get("arms") or {}
    by_serial = {v.get("serial"): r for r, v in arms.items() if v.get("serial")}
    by_loc = {v.get("location"): r for r, v in arms.items() if not v.get("serial") and v.get("location")}
    if not ports:
        print("No serial ports present. Plug in the arms (USB + power).")
    for p in ports:
        role = by_serial.get(p.serial) or by_loc.get(p.location) or ""
        tag = f"<-- {role.upper()}" if role else ""
        print(f"  {p.label()} {tag}")
    for role in ROLES:
        if role not in arms:
            print(f"  ({role} not identified yet -> run: so ports assign)")
