import collections
import json
import pathlib
import subprocess
import tarfile
import time

import pytest
from monitor import Collector, cpu_ratio, start_ticks
from protocol import archive_preview, validate_schedule
from reports import write

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend/backend.sh"


def call(action, *args, secret=None):
    run = subprocess.run([str(BACKEND), action, *args], input=secret, text=True, capture_output=True, timeout=20)
    data = json.loads(run.stdout)
    assert data["status"] == run.returncode
    assert data["version"] == "v1"
    return data


@pytest.mark.parametrize(
    "schedule",
    [
        "60 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * * 13 *",
        "* * * * 8",
        "*/0 * * * *",
        "1-0 * * * *",
        "* * * *",
        "* * * * *;id",
        "* * * * 0/99",
    ],
)
def test_invalid_schedule(schedule):
    with pytest.raises(ValueError):
        validate_schedule(schedule)


@pytest.mark.parametrize("schedule", ["*/5 * * * *", "0 2 * * 1-5", "0,30 0-23/2 1-31 1-12 0-7"])
def test_schedule(schedule):
    assert validate_schedule(schedule) == schedule


@pytest.mark.parametrize(
    "action,args",
    [
        ("shell", ("id",)),
        ("user.create", ("bad;name", "yes", "/bin/bash", "", "", "no")),
        ("user.password", ("root",)),
        ("user.delete", ("root", "remove")),
        ("group.delete", ("root",)),
        ("process.signal", ("1", "0", "KILL")),
        ("process.signal", ("-1", "0", "TERM")),
        ("process.signal", ("nonsense", "0", "TERM")),
        ("service.start", ("--all",)),
        ("file.mkdir", ("relative",)),
        ("file.chmod", ("/tmp", "7777")),
        ("packages.search", ("bad;name",)),
        ("capture.start", ("missing", "1", "1", "")),
        ("firewall.add", ("22", "tcp")),
    ],
)
def test_rejected_operations(action, args):
    assert not call(action, *args)["ok"]


def test_live_capabilities():
    assert call("capabilities")["ok"]
    assert "Distribution" in call("capabilities")["output"]


def test_cpu_guest_not_double_counted():
    Times = collections.namedtuple("Times", "user nice system idle iowait irq softirq steal guest guest_nice")
    before = Times(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    after = Times(40, 0, 10, 50, 0, 0, 0, 0, 40, 0)
    assert cpu_ratio(before, after) == 50
    assert cpu_ratio(after, after) is None


@pytest.mark.parametrize(
    "name,kind", [("../escape", "file"), ("/etc/shadow", "file"), ("folder/link", "link"), ("device", "device")]
)
def test_unsafe_archive(tmp_path, name, kind):
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo(name)
        if kind == "link":
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc"
        elif kind == "device":
            member.type = tarfile.CHRTYPE
        tar.addfile(member)
    with pytest.raises(ValueError):
        archive_preview(archive)


def test_real_backup_restore(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "text.txt").write_text("Bilingual: Deutsch / English")
    archive = tmp_path / "backup.tar.gz"
    destination = tmp_path / "restore"
    destination.mkdir()
    assert call("backup.create", str(source), str(archive))["ok"]
    assert call("backup.verify", str(archive))["ok"]
    assert call("backup.restore", str(archive), str(destination))["ok"]
    assert (destination / "source/text.txt").read_text() == (source / "text.txt").read_text()
    assert not call("backup.restore", str(archive), str(destination))["ok"]
    assert oct(archive.stat().st_mode & 0o777) == "0o600"


def test_symlink_paths_rejected(tmp_path):
    (tmp_path / "link").symlink_to("/tmp", target_is_directory=True)
    assert not call("file.touch", str(tmp_path / "link/unsafe-created-by-test"))["ok"]


def test_process_identity_and_termination():
    # Only the disposable child launched by this test receives a signal.
    process = subprocess.Popen(["/bin/sleep", "30"])
    try:
        for _ in range(20):
            try:
                start = start_ticks(process.pid)
                break
            except FileNotFoundError:
                time.sleep(0.05)
        else:
            pytest.skip("Disposable child /proc identity unavailable in the test environment")
        assert not call("process.signal", str(process.pid), "0", "TERM")["ok"]
        assert process.poll() is None
        response = call("process.signal", str(process.pid), start, "TERM")
        assert response["ok"]
        assert "Signal sent" in response["output"]
        process.wait(timeout=3)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)


def test_live_metrics():
    collector = Collector()
    first = collector.sample()
    time.sleep(0.1)
    second = collector.sample()
    assert first["cpu"] is None
    assert 0 <= second["cpu"] <= 100
    assert second["memory"]["used"] == second["memory"]["total"] - second["memory"]["available"]
    assert second["network"]
    assert all(v["download"] is not None for v in second["network"].values())
    assert second["processes"]


@pytest.mark.parametrize("suffix", ["json", "html", "txt"])
def test_reports_private_and_no_overwrite(tmp_path, suffix):
    path = tmp_path / ("report." + suffix)
    write(path, {"timestamp": "now", "limitations": ["permission-dependent"]}, [{"ok": False}])
    assert path.stat().st_mode & 0o777 == 0o600
    assert "permission-dependent" in path.read_text()
    with pytest.raises(FileExistsError):
        write(path, {}, [])


def test_argument_count():
    assert not call("capabilities", "unexpected")["ok"]
    assert not call("user.lock")["ok"]
    assert not call("backup.restore", "/tmp")["ok"]
