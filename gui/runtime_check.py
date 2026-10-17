"""Check the Qt/Python combinations verified by the Linux guest matrix."""

import re
import sys


def check_runtime():
    import psutil  # noqa: F401
    import PySide6

    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 or newer is required")
    match = re.match(r"(\d+)\.(\d+)", getattr(PySide6, "__version__", ""))
    qt = tuple(map(int, match.groups())) if match else (0, 0)
    if not (6, 6) <= qt < (7, 0):
        raise RuntimeError("A supported PySide6 runtime is required; reinstall from requirements.txt")
    # The tested 6.12.0 bindings return borrowed None values on older CPython,
    # causing a reproducible refcount abort even for ordinary paint calls.
    if sys.version_info < (3, 12) and qt != (6, 8):
        raise RuntimeError("Python 3.10/3.11 requires the tested PySide6 6.8 runtime; reinstall from requirements.txt")
    # A namespace or partial PySide6 installation can expose __version__ while
    # omitting QtWidgets. Import the actual modules before accepting reuse.
    from PySide6.QtCore import QObject  # noqa: F401
    from PySide6.QtGui import QPainter  # noqa: F401
    from PySide6.QtWidgets import QApplication  # noqa: F401


def main():
    if sys.argv[1:] not in ([], ["--smoke"]):
        print("Usage: runtime_check.py [--smoke]", file=sys.stderr)
        return 2
    try:
        check_runtime()
        if sys.argv[1:] == ["--smoke"]:
            from PySide6.QtWidgets import QApplication

            app = QApplication([])
            app.quit()
    except ModuleNotFoundError as error:
        print("GUI Python package incomplete or missing: " + str(error), file=sys.stderr)
        return 69
    except RuntimeError as error:
        print("GUI runtime unavailable: " + str(error), file=sys.stderr)
        return 69
    except (ImportError, OSError) as error:
        print("Qt native library unavailable: " + str(error), file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
