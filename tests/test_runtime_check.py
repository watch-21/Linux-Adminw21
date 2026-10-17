"""Isolated partial-package reproductions: never poison the test runner's Qt."""

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = ROOT / "gui/runtime_check.py"


def fake_runtime(tmp_path, broken=None):
    (tmp_path / "psutil.py").write_text("")
    qt = tmp_path / "PySide6"
    qt.mkdir()
    (qt / "__init__.py").write_text("__version__ = '6.8.3'\n")
    for module, body in {
        "QtCore": "class QObject: pass\n",
        "QtGui": "class QPainter: pass\n",
        "QtWidgets": "class QApplication:\n def __init__(self, args): pass\n def quit(self): pass\n",
    }.items():
        if module != broken:
            (qt / (module + ".py")).write_text(body)
    return qt


def probe(fake, *args):
    code = (
        "import runpy,sys;sys.path.insert(0," + json.dumps(str(fake)) + ");"
        "sys.argv=[" + json.dumps(str(CHECK)) + "]+" + repr(list(args)) + ";"
        "runpy.run_path(" + json.dumps(str(CHECK)) + ",run_name='__main__')"
    )
    return subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=10, check=False)


@pytest.mark.parametrize("missing", ["QtCore", "QtGui", "QtWidgets"])
def test_partial_pyside_rejected_as_python_package_problem(tmp_path, missing):
    fake_runtime(tmp_path, missing)
    result = probe(tmp_path)
    assert result.returncode == 69, result.stderr
    assert "No module named 'PySide6." + missing + "'" in result.stderr
    assert "Python package incomplete" in result.stderr
    assert "Traceback" not in result.stderr


def test_native_library_failure_is_distinct_from_missing_python_module(tmp_path):
    qt = fake_runtime(tmp_path)
    (qt / "QtWidgets.py").write_text("raise ImportError('libEGL.so.1: cannot open shared object file')\n")
    result = probe(tmp_path)
    assert result.returncode == 78
    assert "native library unavailable" in result.stderr
    assert "libEGL.so.1" in result.stderr
    assert "Traceback" not in result.stderr


def test_complete_python_modules_support_smoke_option(tmp_path):
    fake_runtime(tmp_path)
    assert probe(tmp_path).returncode == 0
    assert probe(tmp_path, "--smoke").returncode == 0


def test_empty_pyside_namespace_is_repairable_without_traceback(tmp_path):
    qt = fake_runtime(tmp_path)
    (qt / "__init__.py").write_text("")
    result = probe(tmp_path)
    assert result.returncode == 69
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(os.geteuid() != 0, reason="Root-owned staging fixture required")
@pytest.mark.parametrize("status", [69, 78])
def test_desktop_preflight_selects_repair_only_for_python_package_failure(tmp_path, status):
    import shutil

    source = tmp_path / "source"
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"))
    base = tmp_path / "root"
    base.mkdir()
    # A local command fixture exercises the real installer transaction; it
    # never installs pkexec, Python packages or registrations on the host.
    binary = tmp_path / "bin"
    binary.mkdir()
    (binary / "pkexec").write_text("#!/bin/sh\nexit 0\n")
    (binary / "pkexec").chmod(0o755)
    (binary / "python3").write_text(
        "#!/bin/bash\n"
        'if [[ $* == *runtime_check.py* ]];then exit ' + str(status) + ';fi\n'
        'if [[ $1 == -m && $2 == venv ]];then\n'
        ' mkdir -p "$3/bin"\n'
        " cat >\"$3/bin/python3\" <<'STUB'\n"
        "#!/bin/sh\n"
        "# Test fixture stops the transaction after reaching private pip.\n"
        "echo PRIVATE_PIP_REACHED >&2\nexit 55\nSTUB\n"
        ' chmod 755 "$3/bin/python3"\nexit 0\nfi\n'
        'exec /usr/bin/python3 "$@"\n'
    )
    (binary / "python3").chmod(0o755)
    entry = source / "install.sh"
    entry.write_text(entry.read_text().replace("PATH=/usr/sbin:/usr/bin:/sbin:/bin", "PATH=" + str(binary) + ":/usr/sbin:/usr/bin:/sbin:/bin", 1))
    result = subprocess.run(
        ["bash", str(entry), "--yes", "--destdir", str(base)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode != 0
    assert ("PRIVATE_PIP_REACHED" in result.stderr) == (status == 69), result.stdout + result.stderr
    if status == 78:
        assert "native libraries" in result.stderr
    assert not (base / "usr/local/share/adminw21").exists()
    assert not (base / "usr/local/bin/adminw21").exists()
