import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def bash(script, *args):
    return subprocess.run(
        ["bash", "-c", script, "fixture", str(ROOT), *args], capture_output=True, text=True, timeout=10, check=False
    )


def test_partial_read_failure_not_hidden_by_later_success():
    script = r"""
ROOT=$1
source "$ROOT/modules/backend_actions.sh"
aw_fail() { echo "$1";return "${2:-2}"; }
ip() { echo 'synthetic ip failure';return 1; }
ss() { echo 'synthetic socket success';return 0; }
aw_dispatch network.info
"""
    result = bash(script)
    assert result.returncode == 10
    assert "[FAILED: 1]" in result.stdout
    assert "[OK]" in result.stdout


def test_pacman_no_updates_and_real_error_are_different():
    script = r"""
ROOT=$1
source "$ROOT/modules/backend_actions.sh"
lat_detect_distro() { LAT_PKGMGR=pacman; }
pacman() { if [[ $2 == error ]];then echo 'database error' >&2;fi;return 1; }
aw_package updates
"""
    result = bash(script)
    assert result.returncode == 0
    error_script = script.replace("if [[ $2 == error ]];then", "if true;then")
    result = bash(error_script)
    assert result.returncode == 1
    assert "database error" in result.stdout


@pytest.mark.parametrize(
    "manager,op,name,expected",
    [
        ("apt", "install", "example", "apt-get|-y|install|--|example"),
        ("dnf", "updates", "", "dnf|list|--upgrades"),
        ("dnf", "list", "", "dnf|list|--installed"),
        ("yum", "remove", "example", "yum|-y|remove|example"),
        ("pacman", "install", "example", "pacman|--noconfirm|-S|--|example"),
        ("zypper", "remove", "example", "zypper|--non-interactive|remove|--|example"),
        ("apk", "install", "example", "apk|add|example"),
        ("xbps", "install", "example", "xbps-install|-y|example"),
        ("portage", "install", "example", "emerge|--|example"),
    ],
)
def test_package_adapter_argv_mocked(manager, op, name, expected):
    script = r"""
ROOT=$1;manager=$2;op=$3;name=$4
source "$ROOT/modules/backend_actions.sh"
lat_detect_distro() { LAT_PKGMGR=$manager; }
record() { local first=yes;for arg in "$@";do if [[ $first == no ]];then printf '|';fi;printf '%s' "$arg";first=no;done;printf '\n'; }
apt-get() { record apt-get "$@"; }
dnf() { record dnf "$@"; }
yum() { record yum "$@"; }
pacman() { record pacman "$@"; }
zypper() { record zypper "$@"; }
apk() { record apk "$@"; }
xbps-install() { record xbps-install "$@"; }
emerge() { record emerge "$@"; }
aw_package "$op" "$name"
"""
    result = bash(script, manager, op, name)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@pytest.mark.skipif(os.geteuid() != 0, reason="Temporary root-owned backup fixtures")
def test_retention_ignores_names_not_created_by_application(tmp_path):
    for name in [
        "adminw21-20261010T100000Z-10.tar.gz",
        "adminw21-20261011T100000Z-11.tar.gz",
        "adminw21-20261012T100000Z-12.tar.gz",
        "adminw21-999-other.tar.gz",
        "unrelated.tar.gz",
    ]:
        (tmp_path / name).write_text("fixture")
    backend = ROOT / "backend/backend.sh"
    result = subprocess.run(
        [str(backend), "backup.retention", str(tmp_path), "2"], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "adminw21-20261010T100000Z-10.tar.gz").exists()
    assert (tmp_path / "adminw21-20261011T100000Z-11.tar.gz").exists()
    assert (tmp_path / "adminw21-999-other.tar.gz").exists()
    assert (tmp_path / "unrelated.tar.gz").exists()


def test_retention_discovery_failure_is_not_reported_as_success(tmp_path):
    candidate = tmp_path / "adminw21-20261010T100000Z-10.tar.gz"
    candidate.write_text("preserve me")
    result = bash(
        r"""
ROOT=$1
source "$ROOT/modules/backend_actions.sh"
aw_trusted_path() { return 0; }
find() { echo 'discovery unavailable' >&2;return 1; }
aw_dispatch backup.retention "$2" 1
""",
        str(tmp_path),
    )
    assert result.returncode != 0
    assert "discovery unavailable" in result.stderr
    assert candidate.read_text() == "preserve me"
