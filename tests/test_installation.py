import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.geteuid() != 0, reason="Root-owned staging fixture required")


def install(base, source=ROOT):
    return subprocess.run(
        ["bash", str(source / "install.sh"), "--terminal-only", "--yes", "--destdir", str(base)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_staged_install_upgrade_uninstall_preserves_data(tmp_path):
    base = tmp_path / "root"
    base.mkdir()
    result = install(base)
    assert result.returncode == 0, result.stdout + result.stderr
    dest = base / "usr/local/share/adminw21"
    assert (dest / ".adminw21-owned").read_text().strip() == "Linux Adminw21 v1"
    assert os.access(base / "usr/local/bin/adminw21", os.X_OK)
    assert (base / "usr/share/applications/adminw21-terminal.desktop").exists()
    (dest / "old-only.txt").write_text("old app fixture")
    config = base / "root/.config/adminw21/settings.conf"
    config.parent.mkdir(parents=True)
    config.write_text("LANGUAGE=en\n")
    assert install(base).returncode == 0
    archives = list((base / "var/backups/adminw21").glob("*/application/old-only.txt"))
    assert len(archives) == 1
    assert config.read_text() == "LANGUAGE=en\n"
    assert not (dest / "old-only.txt").exists()
    result = subprocess.run(
        ["bash", str(ROOT / "uninstall.sh"), "--yes", "--destdir", str(base)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not dest.exists()
    assert not (base / "usr/local/bin/adminw21").exists()
    assert config.read_text() == "LANGUAGE=en\n"


def test_unknown_registration_rejected_before_writes(tmp_path):
    base = tmp_path / "root"
    foreign = base / "usr/share/applications/adminw21.desktop"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("foreign application\n")
    assert install(base).returncode != 0
    assert foreign.read_text() == "foreign application\n"
    assert not (base / "usr/local/bin/adminw21").exists()


def test_failure_after_switch_rolls_back_previous_app_and_launcher(tmp_path):
    base = tmp_path / "root"
    base.mkdir()
    assert install(base).returncode == 0
    dest = base / "usr/local/share/adminw21"
    (dest / "preserved.txt").write_text("previous version fixture")
    original_launcher = (base / "usr/local/bin/adminw21").read_bytes()
    altered_source = tmp_path / "source"
    shutil.copytree(ROOT, altered_source, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".ruff_cache"))
    entry = altered_source / "admin.sh"
    old = entry.read_text()
    # Fail only at the installed location, not at the staging preflight.
    entry.write_text(
        old.replace("set -o pipefail", f"set -o pipefail\nif [[ $0 == '{dest}/admin.sh' ]];then exit 42;fi", 1)
    )
    result = install(base, altered_source)
    assert result.returncode != 0
    assert (dest / "preserved.txt").read_text() == "previous version fixture"
    assert (base / "usr/local/bin/adminw21").read_bytes() == original_launcher


def test_uninstall_checks_all_registrations_before_removing_any(tmp_path):
    base = tmp_path / "root"
    base.mkdir()
    assert install(base).returncode == 0
    foreign = base / "usr/share/applications/adminw21.desktop"
    foreign.write_text("different application\n")
    result = subprocess.run(
        ["bash", str(ROOT / "uninstall.sh"), "--yes", "--destdir", str(base)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert (base / "usr/local/bin/adminw21").exists()
    assert (base / "usr/local/share/adminw21").exists()
