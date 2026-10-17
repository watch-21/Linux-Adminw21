import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend/backend.sh"


def command(action, args, privileged=False):
    cmd = [str(BACKEND), action, *args]
    if privileged and os.geteuid() != 0:
        # Use the fixed PolicyKit installation; caller-controlled source cannot be elevated.
        if str(ROOT) != "/usr/local/share/adminw21":
            raise RuntimeError("Install Linux Adminw21 before privileged GUI operations.")
        cmd.insert(0, "/usr/bin/pkexec")
    return cmd
