"""Read-only login session discovery with an explicit source and NSS groups."""

import datetime
import grp
import json
import os
import pathlib
import pwd
import re
import shutil
import subprocess
import time


def run(argv):
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
        env={**os.environ, "LC_ALL": "C", "SYSTEMD_PAGER": ""},
    )
    if result.returncode:
        raise OSError((result.stderr or "Session source failed").strip()[:300])
    return result.stdout


def session_epoch(value):
    if not value:
        return None
    try:
        # systemd prints the timestamp in the invoking machine's local timezone.
        return datetime.datetime.strptime(" ".join(value.split()[1:3]), "%Y-%m-%d %H:%M:%S").timestamp()
    except (ValueError, OverflowError):
        return None


def group_record(username, leader=None):
    try:
        account = pwd.getpwnam(username)
        gids = os.getgrouplist(username, account.pw_gid)
        names = []
        for gid in dict.fromkeys([account.pw_gid, *gids]):
            try:
                names.append(grp.getgrgid(gid).gr_name)
            except KeyError:
                names.append(str(gid))
        try:
            primary = grp.getgrgid(account.pw_gid).gr_name
        except KeyError:
            primary = str(account.pw_gid)
        effective = None
        if leader and str(leader).isdigit():
            try:
                text = pathlib.Path(f"/proc/{int(leader)}/status").read_text()
                line = next(line for line in text.splitlines() if line.startswith("Groups:"))
                effective = []
                for gid in line.split()[1:]:
                    try:
                        effective.append(grp.getgrgid(int(gid)).gr_name)
                    except KeyError:
                        effective.append(gid)
            except (OSError, StopIteration):
                pass
        return {
            "uid": account.pw_uid,
            "primary_group": primary,
            "groups": names,
            "supplementary_groups": [n for n in names if n != primary],
            "session_groups": effective,
            "admin_group": any(n in ("sudo", "wheel") for n in names),
        }
    except (OSError, KeyError):
        return {
            "uid": None,
            "primary_group": None,
            "groups": [],
            "supplementary_groups": [],
            "session_groups": None,
            "admin_group": None,
        }


def parse_logind(text):
    sessions = []
    for block in re.split(r"\n\s*\n", text.strip()):
        values = dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        if values.get("Class", "user") not in ("user", "user-early", "user-light"):
            continue
        if values.get("State") == "closing" or not values.get("Name"):
            continue
        sessions.append(
            {
                "id": values.get("Id"),
                "username": values["Name"],
                "type": "SSH" if values.get("Service", "").startswith("sshd") else values.get("Type", "unknown"),
                "tty": values.get("TTY") or None,
                "host": values.get("RemoteHost") or None,
                "remote": values.get("Remote") == "yes",
                "start": session_epoch(values.get("Timestamp")),
                "start_text": values.get("Timestamp") or None,
                "leader": values.get("Leader"),
                "state": values.get("State", "unknown"),
                "source": "systemd-logind",
            }
        )
    return sessions


def parse_who(text):
    sessions = []
    for index, line in enumerate(text.splitlines()):
        parts = line.split()
        if len(parts) < 2:
            continue
        host = re.search(r"\(([^)]+)\)\s*$", line)
        remote = host.group(1) if host else None
        is_remote = bool(remote and not re.fullmatch(r":\d+(?:\.\d+)?", remote))
        sessions.append(
            {
                "id": f"utmp-{index}",
                "username": parts[0],
                "type": "SSH/remote" if is_remote else "TTY/local",
                "tty": parts[1],
                "host": remote,
                "remote": is_remote,
                "start": None,
                "start_text": " ".join(parts[2:4]) or None,
                "leader": None,
                "state": "recorded",
                "source": "utmp/who",
            }
        )
    return sessions


def collect():
    sessions, issues, source, available = [], [], None, False
    if shutil.which("loginctl") and pathlib.Path("/run/systemd/system").is_dir():
        try:
            ids = [
                line.split()[0]
                for line in run(["loginctl", "list-sessions", "--no-legend", "--no-pager"]).splitlines()
                if line.split() and re.fullmatch(r"[A-Za-z0-9_-]+", line.split()[0])
            ][:128]
            if ids:
                props = [
                    "Id",
                    "Name",
                    "Type",
                    "Class",
                    "State",
                    "Remote",
                    "RemoteHost",
                    "TTY",
                    "Leader",
                    "Timestamp",
                    "Service",
                ]
                args = ["loginctl", "show-session", "--no-pager", *ids]
                for prop in props:
                    args.extend(["-p", prop])
                sessions = parse_logind(run(args))
            available, source = True, "systemd-logind"
        except (OSError, subprocess.TimeoutExpired) as error:
            issues.append("logind: " + str(error)[:200])
    if not available and shutil.which("who"):
        try:
            sessions = parse_who(run(["who"]))[:128]
            available, source = True, "utmp/who"
            issues.append("utmp may omit graphical/Wayland sessions; no sessions are invented.")
        except (OSError, subprocess.TimeoutExpired) as error:
            issues.append("utmp: " + str(error)[:200])
    cache = {}
    for session in sessions:
        username = session["username"]
        if username not in cache:
            cache[username] = group_record(username)
        session.update(cache[username])
        session["session_groups"] = (
            group_record(username, session["leader"])["session_groups"] if session["leader"] else None
        )
    return {
        "available": available,
        "source": source,
        "collected_at": time.time(),
        "sessions": sessions,
        "limitations": issues,
        "groups_kind": "configured NSS membership; session groups may differ",
    }


if __name__ == "__main__":
    print(json.dumps(collect(), ensure_ascii=False))
