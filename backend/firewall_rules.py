"""Parse only exact application-owned UFW rules; no substring port matching."""

import re
import sys


def indices(text, port, protocol):
    pattern = re.compile(r"^\[\s*(\d+)\]\s+(\d+)/(tcp|udp)(?:\s+\(v6\))?\s+ALLOW IN\s+.*?\s+#\s*adminw21\s*$")
    found = set()
    for line in text.splitlines():
        match = pattern.fullmatch(line.strip())
        if match and int(match[2]) == int(port) and match[3] == protocol:
            found.add(int(match[1]))
    return sorted(found, reverse=True)


if __name__ == "__main__":
    for index in indices(sys.stdin.read(), sys.argv[1], sys.argv[2]):
        print(index)
