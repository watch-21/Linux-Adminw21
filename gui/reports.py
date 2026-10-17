import html
import json
import pathlib


def write(path, data, checks):
    record = {
        "application": "Linux Adminw21 v1",
        "collection": data,
        "checks": checks,
        "limitations": data.get("limitations", []),
    }
    text = json.dumps(record, ensure_ascii=False, indent=2)
    suffix = pathlib.Path(path).suffix.lower()
    if suffix == ".html":
        text = (
            '<!doctype html><html lang="en"><meta charset="utf-8"><title>Linux Adminw21 v1</title><style>body{background:#101b2c;color:#e3edf8;font:16px system-ui;margin:40px}pre{white-space:pre-wrap}h1{color:#37d5ca}</style><h1>Linux Adminw21 v1</h1><pre>'
            + html.escape(text)
            + "</pre></html>"
        )
    elif suffix not in (".json", ".txt"):
        raise ValueError("Use .json, .txt or .html")
    # Exclusive creation, restrictive mode, no accidental overwrite.
    import os

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(text)
