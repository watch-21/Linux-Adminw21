"""Run source checks in disposable official Linux container userspaces.

A container shares the host kernel and does not validate desktop PolicyKit/systemd.
No Docker socket, host network, privileged mode or writable host source is mounted.
"""

import argparse
import datetime
import json
import pathlib
import shutil
import subprocess
import sys
import time

TARGETS = {
    "ubuntu22": "ubuntu:22.04",
    "ubuntu24": "ubuntu:24.04",
    "debian12": "debian:12",
    "debian13": "debian:13",
    "kali": "kalilinux/kali-rolling:latest",
    "fedora": "fedora:44",
    "arch": "archlinux:base",
    "opensuse": "opensuse/leap:16.0",
    "alpine": "alpine:3.22",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distro", choices=TARGETS)
    parser.add_argument("--engine", choices=["docker", "podman"], default="docker")
    parser.add_argument("--output", default="linux-matrix-results.json")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    selected = [args.distro] if args.distro else list(TARGETS)
    if args.list:
        print(json.dumps({key: TARGETS[key] for key in selected}, indent=2))
        return 0
    root = pathlib.Path(__file__).resolve().parents[1]
    if "," in str(root) or "\n" in str(root):
        parser.error("Use a source path without commas/newlines for container bind mounts")
    rows = []
    engine = shutil.which(args.engine)
    for key in selected:
        item = {
            "target": key,
            "image": TARGETS[key],
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "container userspace; shared host kernel; no desktop authentication",
        }
        if not engine:
            item.update(status="blocked", reason=f"{args.engine} is unavailable")
        else:
            command = [
                engine,
                "run",
                "--rm",
                "--init",
                "--mount",
                f"type=bind,source={root},target=/source,readonly",
                TARGETS[key],
                "/bin/sh",
                "/source/tests/container_entry.sh",
                key,
            ]
            begin = time.monotonic()
            log = pathlib.Path(args.output).with_name(f"linux-{key}.log")
            try:
                with log.open("w") as stream:
                    result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1800, check=False)
                item.update(
                    status="passed" if result.returncode == 0 else "failed",
                    exit_code=result.returncode,
                    seconds=round(time.monotonic() - begin, 2),
                    log=str(log),
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                item.update(status="failed", reason=str(error), log=str(log))
        rows.append(item)
        print(key + ": " + item["status"], flush=True)
    pathlib.Path(args.output).write_text(json.dumps(rows, indent=2))
    return 0 if all(row["status"] == "passed" for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
