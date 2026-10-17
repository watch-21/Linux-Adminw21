import json
import pathlib
import subprocess
from types import SimpleNamespace

import pytest
import sessions
from firewall_rules import indices
from monitor import counter_rate


@pytest.mark.parametrize("host,remote", [("192.168.1.20", True), ("::1", True), (":0", False), (":0.1", False)])
def test_utmp_remote_source(host, remote):
    row = sessions.parse_who(f"alex pts/1 2026-10-15 00:10 ({host})")[0]
    assert row["username"] == "alex"
    assert row["remote"] is remote
    assert row["start"] is None  # Do not invent an elapsed time from ambiguous utmp text.


def test_logind_filters_and_multiple_sessions():
    text = """Id=2
Name=alex
Type=wayland
Class=user
State=active
Remote=no
TTY=tty2
Leader=700

Id=3
Name=alex
Type=tty
Class=user
State=online
Remote=yes
RemoteHost=192.168.1.20
Service=sshd

Id=c1
Name=gdm
Class=greeter
State=active

Id=b4
Name=cron-fixture
Class=background
State=online

Id=4
Name=old
Class=user
State=closing
"""
    rows = sessions.parse_logind(text)
    assert len(rows) == 2
    assert rows[0]["type"] == "wayland"
    assert rows[1]["type"] == "SSH"
    assert len({row["username"] for row in rows}) == 1


def test_groups_primary_not_in_supplementary(monkeypatch):
    monkeypatch.setattr(sessions.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=1000, pw_gid=1000))
    monkeypatch.setattr(sessions.os, "getgrouplist", lambda name, gid: [1000, 27, 999])
    monkeypatch.setattr(
        sessions.grp, "getgrgid", lambda gid: SimpleNamespace(gr_name={1000: "alex", 27: "sudo", 999: "docker"}[gid])
    )
    record = sessions.group_record("alex")
    assert record["primary_group"] == "alex"
    assert record["supplementary_groups"] == ["sudo", "docker"]
    assert record["admin_group"] is True
    assert record["session_groups"] is None


def test_unknown_primary_group_keeps_uid(monkeypatch):
    monkeypatch.setattr(sessions.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=1000, pw_gid=1000))
    monkeypatch.setattr(sessions.os, "getgrouplist", lambda name, gid: [1000])

    def missing(gid):
        raise KeyError(gid)

    monkeypatch.setattr(sessions.grp, "getgrgid", missing)
    assert sessions.group_record("alex")["primary_group"] == "1000"
    assert sessions.group_record("alex")["uid"] == 1000


def test_unavailable_source_does_not_invent_current_user(monkeypatch):
    monkeypatch.setattr(sessions.shutil, "which", lambda program: None)
    record = sessions.collect()
    assert record["available"] is False
    assert record["sessions"] == []
    assert record["source"] is None


def test_backend_sessions_contract():
    backend = pathlib.Path(__file__).resolve().parents[1] / "backend/backend.sh"
    result = subprocess.run([str(backend), "sessions.list"], capture_output=True, text=True, timeout=10, check=False)
    envelope = json.loads(result.stdout)
    assert envelope["ok"]
    record = json.loads(envelope["output"])
    assert isinstance(record["sessions"], list)
    assert "source" in record and "available" in record


def test_exact_ufw_ownership_port_and_reverse_indices():
    text = """[ 1] 2222/tcp                   ALLOW IN    Anywhere                   # adminw21
[ 2] 22/tcp                     ALLOW IN    Anywhere                   # adminw21
[ 3] 22/udp                     ALLOW IN    Anywhere                   # adminw21
[ 4] 22/tcp                     ALLOW IN    Anywhere                   # other-tool
[10] 22/tcp (v6)                ALLOW IN    Anywhere (v6)              # adminw21
[11] 22/tcp                     DENY IN     Anywhere                   # adminw21
"""
    assert indices(text, 22, "tcp") == [10, 2]
    assert indices(text, 2222, "tcp") == [1]
    assert indices(text, 22, "udp") == [3]


@pytest.mark.parametrize(
    "current,previous,elapsed,expected",
    [(100, 50, 2, 25), (0, 100, 2, None), (100, None, 2, None), (100, 50, 0, None), (100, 50, None, None)],
)
def test_counter_reset_unavailable(current, previous, elapsed, expected):
    assert counter_rate(current, previous, elapsed) == expected
