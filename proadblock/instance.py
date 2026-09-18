import os
import subprocess
import sys

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def kill_other_instances(exe_name: str = "ProAdBlock.exe") -> None:
    """Terminates any other running copies of this app left over from a
    previous launch, so ports 53/80/443 aren't already held by them."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return

    my_pid = os.getpid()
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=False, creationflags=_NO_WINDOW,
        )
    except OSError:
        return

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("info:"):
            continue
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        if pid == my_pid:
            continue
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=False, creationflags=_NO_WINDOW)
