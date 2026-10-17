import json
import subprocess
import sys
import time

from client import BACKEND

try:
    from monitor import Collector
except ImportError:
    Collector = None
from reports import write

if Collector:
    collector = Collector()
    collector.sample()
    time.sleep(0.3)
    data = collector.sample()
else:
    import datetime
    import pathlib

    data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "memory_source": pathlib.Path("/proc/meminfo").read_text(),
        "network_source": pathlib.Path("/proc/net/dev").read_text(),
        "limitations": ["Install psutil for structured CPU/process/network samples."],
    }
checks = []
for action in ["capabilities", "users.list", "groups.list", "services.list", "security.inspect"]:
    try:
        result = subprocess.run([str(BACKEND), action], capture_output=True, text=True, timeout=15, check=False)
        response = json.loads(result.stdout)
        checks.append(response)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        checks.append({"action": action, "ok": False, "error": str(error)})
write(sys.argv[1], data, checks)
