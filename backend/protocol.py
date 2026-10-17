"""JSON serialization and passive validation only. Administration stays in Bash."""

import datetime
import json
import pathlib
import re
import sys
import tarfile


def archive_preview(path):
    records = []
    with tarfile.open(path, "r:*") as archive:
        total = 0
        for member in archive:
            name = pathlib.PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not name.parts:
                raise ValueError("Unsafe archive path")
            if not (member.isfile() or member.isdir()):
                raise ValueError("Links and special files are not supported in restores")
            total += member.size
            if total > 20 * 1024**3 or len(records) >= 100000:
                raise ValueError("Archive exceeds restore validation limits")
            records.append({"name": member.name, "bytes": member.size})
    return records


def validate_schedule(value):
    fields = value.split()
    if len(fields) != 5:
        raise ValueError("Five numeric cron fields required")
    for field, (lo, hi) in zip(fields, [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)], strict=True):
        for item in field.split(","):
            if not re.fullmatch(r"(\*|\d+(-\d+)?)(/\d+)?", item):
                raise ValueError("Invalid cron field")
            base, _, step = item.partition("/")
            if step and not 1 <= int(step) <= hi - lo + 1:
                raise ValueError("Invalid cron step")
            if base != "*":
                values = list(map(int, base.split("-")))
                if not all(lo <= v <= hi for v in values) or values != sorted(values):
                    raise ValueError("Cron value out of range")
    return " ".join(fields)


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    try:
        if mode == "response":
            action, status = args
            output = sys.stdin.read()
            print(
                json.dumps(
                    {
                        "schema": 1,
                        "version": "v1",
                        "action": action,
                        "ok": status == "0",
                        "status": int(status),
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "output": output,
                    },
                    ensure_ascii=False,
                )
            )
        elif mode == "archive":
            print(json.dumps(archive_preview(args[0]), ensure_ascii=False))
        elif mode == "cron":
            print(validate_schedule(args[0]))
    except (ValueError, OSError, tarfile.TarError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
