import json
import os
import pathlib
import tempfile


def config_path():
    return pathlib.Path(os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config")) / "adminw21/gui.json"


def read():
    try:
        value = json.loads(config_path().read_text())
        return {
            "language": value.get("language") if value.get("language") in ("de", "en") else "de",
            "theme": value.get("theme") if value.get("theme") in ("dark", "light") else "dark",
        }
    except (OSError, ValueError, AttributeError):
        return {"language": "de", "theme": "dark"}


def save(value):
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
