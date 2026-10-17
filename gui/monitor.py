"""Read-only Linux collectors. All unavailable data is explicit, never fabricated."""

import datetime
import json
import os
import pathlib
import platform
import socket
import subprocess
import time

import psutil


def cpu_ratio(previous, current):
    # Linux user/nice counters already include guest/guest_nice.
    names = ("user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal")
    total = sum(getattr(current, k, 0) - getattr(previous, k, 0) for k in names)
    idle = sum(getattr(current, k, 0) - getattr(previous, k, 0) for k in ("idle", "iowait"))
    return max(0, min(100, (total - idle) * 100 / total)) if total > 0 else None


def counter_rate(current, previous, elapsed):
    if previous is None or elapsed is None or elapsed <= 0 or current < previous:
        return None
    return (current - previous) / elapsed


def start_ticks(pid):
    raw = pathlib.Path(f"/proc/{pid}/stat").read_text()
    return raw[raw.rfind(")") + 2 :].split()[19]


class Collector:
    def __init__(self):
        self.last_time = None
        self.last_cpu = None
        self.last_net = None
        self.last_disk = None
        self.processes = {}
        self.services = {"active": None, "failed": None, "status": "unavailable"}
        self.last_services = 0
        self.last_sessions = -10
        self.session_data = {"available": False, "source": None, "sessions": [], "limitations": []}

    def sample(self):
        warnings = []
        now = time.monotonic()
        collected_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        elapsed = now - self.last_time if self.last_time else None
        cpu = psutil.cpu_times(percpu=True)
        per_core = (
            [cpu_ratio(a, b) for a, b in zip(self.last_cpu, cpu, strict=True)]
            if self.last_cpu and len(self.last_cpu) == len(cpu)
            else [None] * len(cpu)
        )
        usable = [v for v in per_core if v is not None]
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        net = psutil.net_io_counters(pernic=True)
        interfaces = {}
        try:
            addresses = psutil.net_if_addrs()
        except (OSError, psutil.Error):
            addresses = {}
            warnings.append("Interface addresses unavailable: permissions or netlink access")
        try:
            states = psutil.net_if_stats()
        except (OSError, psutil.Error):
            states = {}
            warnings.append("Interface state unavailable: permissions or ioctl access")
        for name, n in net.items():
            prev = (self.last_net or {}).get(name)

            def rate(field, previous=prev, current=n):
                return counter_rate(getattr(current, field), getattr(previous, field) if previous else None, elapsed)

            interfaces[name] = {
                "rx": n.bytes_recv,
                "tx": n.bytes_sent,
                "download": rate("bytes_recv"),
                "upload": rate("bytes_sent"),
                "errors_in": n.errin,
                "errors_out": n.errout,
                "drops_in": n.dropin,
                "drops_out": n.dropout,
                "up": states[name].isup if name in states else None,
                "addresses": [
                    a.address for a in addresses.get(name, []) if a.family in (socket.AF_INET, socket.AF_INET6)
                ],
            }
        disk = psutil.disk_io_counters()
        disk_rates = {"read": None, "write": None}
        if disk and self.last_disk and elapsed:
            disk_rates = {
                k: counter_rate(getattr(disk, f"{k}_bytes"), getattr(self.last_disk, f"{k}_bytes"), elapsed)
                for k in ("read", "write")
            }
        storage = []
        partitions = psutil.disk_partitions(all=False)
        if not any(p.mountpoint == "/" for p in partitions):
            import collections

            Partition = collections.namedtuple("Partition", "device mountpoint fstype")
            partitions.append(Partition("root", "/", "host-visible"))
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                stat = os.statvfs(partition.mountpoint)
                storage.append(
                    {
                        "mount": partition.mountpoint,
                        "device": partition.device,
                        "fs": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                        "inode_percent": 100 * (stat.f_files - stat.f_ffree) / stat.f_files if stat.f_files else None,
                    }
                )
                if usage.percent >= 90:
                    warnings.append(f"Filesystem {partition.mountpoint}: {usage.percent}%")
            except (OSError, psutil.Error) as error:
                warnings.append(f"{partition.mountpoint}: {type(error).__name__}")
        procs = []
        active = {}
        for proc in psutil.process_iter(
            ["pid", "ppid", "name", "username", "cmdline", "memory_percent", "status", "create_time", "num_threads"]
        ):
            try:
                pid = proc.pid
                identity = (pid, proc.info["create_time"])
                tracked = self.processes.get(identity, proc)
                cpu_pct = tracked.cpu_percent(None)
                active[identity] = tracked
                p = dict(proc.info)
                p["command"] = " ".join(p.pop("cmdline") or [])
                p["cpu_percent"] = cpu_pct if identity in self.processes else None
                p["rss"] = proc.memory_info().rss
                p["start_ticks"] = start_ticks(pid)
                p["service"] = None
                try:
                    parts = pathlib.Path(f"/proc/{pid}/cgroup").read_text().split("/")
                    p["service"] = next((v.strip() for v in reversed(parts) if v.strip().endswith(".service")), None)
                except OSError:
                    pass
                procs.append(p)
            except (psutil.Error, OSError, ValueError, IndexError):
                continue
        self.processes = active
        try:
            frequency = psutil.cpu_freq()
        except (OSError, NotImplementedError):
            frequency = None
        try:
            model = next(
                line.split(":", 1)[1].strip()
                for line in pathlib.Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            )
        except (OSError, StopIteration):
            model = platform.processor() or None
        try:
            distro = platform.freedesktop_os_release().get("PRETTY_NAME")
        except OSError:
            distro = None
        if now - self.last_services >= 30:
            self.last_services = now
            if pathlib.Path("/run/systemd/system").is_dir():
                try:
                    backend = pathlib.Path(__file__).resolve().parents[1] / "backend/backend.sh"
                    response = subprocess.run(
                        [str(backend), "services.list"], capture_output=True, text=True, timeout=8, check=False
                    )
                    record = json.loads(response.stdout)
                    if record["ok"]:
                        lines = [line.split() for line in record["output"].splitlines()]
                        services = [line for line in lines if line and line[0].endswith(".service") and len(line) >= 4]
                        self.services = {
                            "active": sum(line[2] == "active" for line in services),
                            "failed": sum(line[2] == "failed" for line in services),
                            "status": "collected",
                            "items": [
                                {"unit": line[0], "state": line[2], "substate": line[3]} for line in services[:24]
                            ],
                        }
                    else:
                        self.services = {"active": None, "failed": None, "status": "collection failed"}
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    self.services = {"active": None, "failed": None, "status": "collection failed"}
            else:
                self.services = {"active": None, "failed": None, "status": "systemd unavailable"}
        if now - self.last_sessions >= 10:
            self.last_sessions = now
            try:
                backend = pathlib.Path(__file__).resolve().parents[1] / "backend/backend.sh"
                reply = subprocess.run(
                    [str(backend), "sessions.list"], capture_output=True, text=True, timeout=7, check=False
                )
                envelope = json.loads(reply.stdout)
                if not envelope.get("ok"):
                    raise ValueError(envelope.get("output", "Session collection failed"))
                self.session_data = json.loads(envelope["output"])
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                self.session_data = {
                    "available": False,
                    "source": None,
                    "sessions": [],
                    "limitations": [str(error)[:250]],
                }
        result = {
            "timestamp": collected_at,
            "monotonic": now,
            "cpu": sum(usable) / len(usable) if usable else None,
            "per_core": per_core,
            "logical": psutil.cpu_count(),
            "physical": psutil.cpu_count(logical=False),
            "frequency_mhz": frequency.current if frequency else None,
            "model": model,
            "load": os.getloadavg(),
            "memory": {
                "total": memory.total,
                "used": memory.total - memory.available,
                "available": memory.available,
                "percent": (memory.total - memory.available) * 100 / memory.total,
                "cache": getattr(memory, "cached", None),
                "buffers": getattr(memory, "buffers", None),
            },
            "swap": swap._asdict(),
            "network": interfaces,
            "disk": disk_rates,
            "storage": storage,
            "system": {
                "host": socket.gethostname(),
                "kernel": platform.release(),
                "architecture": platform.machine(),
                "distribution": distro,
                "services": self.services,
                "uptime": time.time() - psutil.boot_time(),
            },
            "processes": procs,
            "warnings": warnings,
            "session_data": self.session_data,
            "limitations": [
                "Host-visible metrics; container limits may differ.",
                "Process CPU is per logical core; values may exceed 100%.",
                "Socket owners and system journals depend on caller permissions.",
                "Non-systemd service management is unavailable.",
            ],
        }
        self.last_time, self.last_cpu, self.last_net, self.last_disk = now, cpu, net, disk
        return result
