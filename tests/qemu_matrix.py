"""Boot official distribution userspaces in disposable QEMU/TCG VMs.

Uses a common supplied Linux kernel, not each distribution's boot stack.
Requires QEMU, cpio, mkfs.ext4 and an extracted Alpine rescue initramfs/modules.
No host directories/devices are mounted in guests. Results require guest markers.
"""

import argparse
import concurrent.futures
import datetime
import hashlib
import io
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import tarfile
import time
import urllib.parse
import urllib.request

TARGETS = {
    "ubuntu22": "library/ubuntu:22.04",
    "ubuntu24": "library/ubuntu:24.04",
    "debian12": "library/debian:12",
    "debian13": "library/debian:13",
    "kali": "kalilinux/kali-rolling:latest",
    "fedora": "library/fedora:44",
    "arch": "library/archlinux:base",
    "opensuse": "opensuse/leap:16.0",
    "alpine": "library/alpine:3.22",
}
SOURCE = pathlib.Path(__file__).resolve().parents[1]


def fetch(url, token=None, accept=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if accept:
        headers["Accept"] = accept
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)


def unpack(root, archive, ownership):
    # Only digest-checked official image layers reach this helper.
    with tarfile.open(archive) as stream:
        modes = {}
        for member in stream:
            name = pathlib.PurePosixPath(member.name)
            if str(name) == ".":
                continue
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Unsafe layer member")
            if member.isdev() or member.isfifo():
                continue
            if name.name.startswith(".wh."):
                raise ValueError("Layer whiteout requires a fresh flattened image")
            destination = root / member.name
            if not destination.parent.resolve().is_relative_to(root.resolve()):
                raise ValueError("Layer member escapes through a symlink: " + member.name)
            ownership[member.name] = (member.uid, member.gid)
            if member.isdir():
                modes[member.name] = member.mode
                member.mode |= 0o700
            member.uid = member.gid = 0
            stream.extract(member, root, numeric_owner=True, filter="fully_trusted")
        for name, mode in sorted(modes.items(), key=lambda row: len(row[0]), reverse=True):
            (root / name).chmod(mode)


def pull(key, state):
    metadata = state / (key + "-image.json")
    root = state / (key + "-root")
    if metadata.exists():
        return root, json.loads(metadata.read_text())
    repo, tag = TARGETS[key].rsplit(":", 1)
    query = urllib.parse.urlencode({"service": "registry.docker.io", "scope": "repository:" + repo + ":pull"})
    with fetch("https://auth.docker.io/token?" + query) as response:
        token = json.load(response)["token"]
    accept = ",".join(
        [
            "application/vnd.oci.image.index.v1+json",
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
        ]
    )
    url = "https://registry-1.docker.io/v2/" + repo
    with fetch(url + "/manifests/" + tag, token, accept) as response:
        raw = response.read()
    manifest = json.loads(raw)
    if "manifests" in manifest:
        descriptor = next(
            m
            for m in manifest["manifests"]
            if m.get("platform", {}).get("architecture") == "amd64" and m.get("platform", {}).get("os") == "linux"
        )
        with fetch(url + "/manifests/" + descriptor["digest"], token, accept) as response:
            raw = response.read()
        assert "sha256:" + hashlib.sha256(raw).hexdigest() == descriptor["digest"]
        manifest = json.loads(raw)
    root.mkdir(exist_ok=True)
    ownership = {}
    for layer in manifest["layers"]:
        digest = layer["digest"].split(":", 1)[1]
        path = state / (digest + ".layer")
        if not path.exists():
            with fetch(url + "/blobs/" + layer["digest"], token) as src, path.open("wb") as dst:
                shutil.copyfileobj(src, dst)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        unpack(root, path, ownership)
    info = {
        "image": TARGETS[key],
        "manifest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "layers": manifest["layers"],
    }
    (root / "qa-ownership").write_text(
        "\n".join(
            "/qa/busybox chown " + str(uid) + ":" + str(gid) + " " + shlex.quote("/" + path)
            for path, (uid, gid) in ownership.items()
            if uid or gid
        )
        + "\n"
    )
    metadata.write_text(json.dumps(info, indent=2))
    return root, info


def prepare_boot(args):
    boot = args.state_dir / "rescue"
    if not boot.exists():
        shutil.copytree(args.boot_dir, boot, symlinks=True)
        shutil.copytree(args.modules_dir, boot / "lib/modules", dirs_exist_ok=True, symlinks=True)
    (boot / "init").write_text("""#!/bin/busybox sh
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
/bin/busybox mount -t devtmpfs devtmpfs /dev
/bin/busybox mount -t proc proc /proc
/bin/busybox mount -t sysfs sysfs /sys
/bin/busybox modprobe virtio_blk
/bin/busybox modprobe ext4
/bin/busybox mkdir -p /newroot
/bin/busybox mount -t ext4 /dev/vda /newroot || { echo ADMINW21_BOOT_FAILED; /bin/busybox poweroff -f; }
exec /bin/busybox switch_root /newroot /qa-init
""")
    (boot / "init").chmod(0o755)
    archive = args.state_dir / "rescue.gz"
    with archive.open("wb") as output:
        first = subprocess.Popen(["find", ".", "-print0"], cwd=boot, stdout=subprocess.PIPE)
        second = subprocess.Popen(
            [str(args.tools_dir / "usr/bin/cpio"), "--null", "-o", "-H", "newc"],
            cwd=boot,
            stdin=first.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(["gzip", "-1"], stdin=second.stdout, stdout=output, check=True)
        assert first.wait() == 0 and second.wait() == 0
    return archive


def run_guest(key, args, rescue):
    state = args.state_dir
    begin = time.monotonic()
    result = {
        "target": key,
        "mode": "probe" if args.probe else ("core" if args.core_only else "full"),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "QEMU TCG; common supplied kernel; native distribution userspace; no desktop/systemd boot",
    }
    label = key + ("-probe" if args.probe else ("-core" if args.core_only else ""))
    log_path = state / (label + ".log")
    if log_path.exists():
        shutil.copyfile(log_path, state / (label + "-previous-" + str(time.time_ns()) + ".log"))
    try:
        root, info = pull(key, state)
        result["image"] = info
        disk = state / (key + ".ext4")
        if not disk.exists():
            (root / "qa").mkdir(exist_ok=True)
            shutil.copy2(args.boot_dir / "bin/busybox", root / "qa/busybox")
            library_dir = root / "lib"
            library_mode = library_dir.stat().st_mode & 0o7777
            library_dir.chmod(library_mode | 0o700)
            loader = root / "lib/ld-musl-x86_64.so.1"
            shutil.copyfile(args.boot_dir / "lib/ld-musl-x86_64.so.1", loader)
            loader.chmod(0o755)
            shutil.copytree(args.modules_dir, root / "lib/modules", dirs_exist_ok=True, symlinks=True)
            library_dir.chmod(library_mode)
            with (root / "qa-ownership").open("a") as restoration:
                for item in root.rglob("*"):
                    if item.is_file() and not item.is_symlink() and not item.stat().st_mode & 0o400:
                        mode = item.stat().st_mode & 0o7777
                        item.chmod(mode | 0o400)
                        restoration.write(
                            "/qa/busybox chmod "
                            + oct(mode)[2:]
                            + " "
                            + shlex.quote("/" + str(item.relative_to(root)))
                            + "\n"
                        )
            (root / "qa-init").write_text("""#!/qa/busybox sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
/qa/busybox mount -t devtmpfs devtmpfs /dev
/qa/busybox mount -t proc proc /proc
/qa/busybox mount -t sysfs sysfs /sys
/qa/busybox mkdir -p /dev/pts /run /tmp
/qa/busybox mount -t devpts devpts /dev/pts
/qa/busybox chmod 1777 /tmp
/qa/busybox tar -xf /dev/vdb -C / || { echo ADMINW21_PAYLOAD_FAILED; /qa/busybox poweroff -f; }
. /qa-env
/qa/busybox modprobe virtio_net
/qa/busybox ip link set lo up
/qa/busybox ip link set eth0 up
/qa/busybox ip addr add 10.0.2.15/24 dev eth0
/qa/busybox ip route add default via 10.0.2.2
/qa/busybox rm -f /etc/resolv.conf
/qa/busybox printf 'nameserver 10.0.2.3\\n' >/etc/resolv.conf
/qa/busybox sh /qa-ownership
/qa/busybox cat /etc/os-release
/bin/sh /source/tests/guest_entry.sh "$ADMINW21_TARGET"
rc=$?
echo "ADMINW21_GUEST_RESULT=$rc"
/qa/busybox sync
/qa/busybox poweroff -f
""")
            (root / "qa-init").chmod(0o755)
            with disk.open("wb") as file:
                file.truncate(6 * 1024**3)
            subprocess.run(["mkfs.ext4", "-q", "-F", "-d", str(root), str(disk)], check=True, stdout=subprocess.DEVNULL)
        env_lines = [
            "export ADMINW21_DISPOSABLE_VM=yes",
            "export ADMINW21_TARGET=" + shlex.quote(key),
            "export ADMINW21_CORE_ONLY=" + ("yes" if args.core_only else "no"),
            "export TERM=dumb",
            "export ADMINW21_PROBE=" + ("yes" if args.probe else "no"),
            "export NO_COLOR=1",
        ]
        for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
            value = os.environ.get(name)
            if value:
                parsed = urllib.parse.urlsplit(value)
                if parsed.hostname in ("localhost", "127.0.0.1", "::1"):
                    value = value.replace(parsed.hostname, "10.0.2.2")
                env_lines.append("export " + name + "=" + shlex.quote(value))
        cert = os.environ.get("ADMINW21_TEST_CA")
        if cert and pathlib.Path(cert).is_file():
            env_lines += [
                "export SSL_CERT_FILE=/qa-cert.pem",
                "export REQUESTS_CA_BUNDLE=/qa-cert.pem",
                "export CURL_CA_BUNDLE=/qa-cert.pem",
                "export PIP_CERT=/qa-cert.pem",
            ]
        payload = state / (key + "-payload.tar")
        with tarfile.open(payload, "w") as archive:

            def add_filter(member):
                if any(
                    x in {"__pycache__", ".pytest_cache", ".ruff_cache", ".git"}
                    for x in pathlib.PurePosixPath(member.name).parts
                ):
                    return None
                member.uid = member.gid = 0
                return member

            archive.add(SOURCE, "source", filter=add_filter)
            if args.probe:
                archive.add(args.probe, "qa-probe.sh", filter=add_filter)
            data = ("\n".join(env_lines) + "\n").encode()
            entry = tarfile.TarInfo("qa-env")
            entry.size = len(data)
            entry.mode = 0o600
            archive.addfile(entry, io.BytesIO(data))
            if cert and pathlib.Path(cert).is_file():
                archive.add(cert, "qa-cert.pem", filter=add_filter)
            if args.wheelhouse:
                archive.add(args.wheelhouse, "wheels", filter=add_filter)
        env = dict(
            os.environ,
            QEMU_MODULE_DIR=str(args.tools_dir / "usr/lib/x86_64-linux-gnu/qemu"),
            LD_LIBRARY_PATH=str(args.tools_dir / "usr/lib/x86_64-linux-gnu"),
        )
        command = [
            str(args.tools_dir / "usr/bin/qemu-system-x86_64"),
            "-L",
            str(args.tools_dir / "usr/share/qemu"),
            "-bios",
            str(args.tools_dir / "usr/share/seabios/bios-256k.bin"),
            "-accel",
            "tcg,tb-size=64",
            "-cpu",
            "max",
            "-m",
            "1024",
            "-display",
            "none",
            "-nodefaults",
            "-serial",
            "stdio",
            "-monitor",
            "none",
            "-kernel",
            str(args.kernel),
            "-initrd",
            str(rescue),
            "-append",
            "console=ttyS0 quiet rdinit=/init init=/init panic=-1 adminw21.disposable=1",
            "-no-reboot",
            "-drive",
            f"file={disk},format=raw,if=virtio",
            "-drive",
            f"file={payload},format=raw,if=virtio,readonly=on",
            "-netdev",
            "user,id=net0",
            "-object",
            "rng-random,id=rng0,filename=/dev/urandom",
            "-device",
            "virtio-rng-pci,rng=rng0",
            "-device",
            "virtio-net-pci,netdev=net0,romfile=",
        ]
        with log_path.open("w") as stream:
            process = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout)
        output = log_path.read_text(errors="replace")
        match = re.search(r"ADMINW21_GUEST_RESULT=(\d+)", output)
        phases = re.findall(r"ADMINW21_PHASE=([a-z_]+)", output)
        result["phase"] = phases[-1] if phases else "unrecorded"
        result.update(
            qemu_exit=process.returncode,
            guest_exit=int(match[1]) if match else None,
            core_passed="ADMINW21_CORE_RESULT=0" in output,
            pytest_passed="ADMINW21_PYTEST_RESULT=0" in output,
        )
        result["status"] = "passed" if match and match[1] == "0" and process.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        result.update(status="timeout", reason="Guest deadline exceeded; QEMU terminated by its supervisor")
    except Exception as error:
        result.update(status="blocked", reason=str(error))
    result.update(seconds=round(time.monotonic() - begin, 1), log=log_path.name)
    (state / (label + "-result.json")).write_text(json.dumps(result, indent=2))
    print(key + ": " + result["status"], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("state-dir", "tools-dir", "boot-dir", "modules-dir", "kernel"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    parser.add_argument("--wheelhouse", type=pathlib.Path)
    parser.add_argument("--probe", type=pathlib.Path, help="Run a diagnostic script inside a prepared disposable guest")
    parser.add_argument("--distro", choices=TARGETS, action="append")
    parser.add_argument("--core-only", action="store_true")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=1)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run as root to preserve UID/GID metadata in staged guest filesystems")
    for name in ("state_dir", "tools_dir", "boot_dir", "modules_dir", "kernel", "wheelhouse"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    if any("," in str(getattr(args, name)) for name in ("state_dir", "kernel")):
        parser.error("Use paths without commas for QEMU drive options")
    args.state_dir.mkdir(parents=True, exist_ok=True)
    rescue = prepare_boot(args)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_guest, key, args, rescue) for key in (args.distro or TARGETS)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    (args.state_dir / "results.json").write_text(json.dumps(results, indent=2))
    return 0 if all(row["status"] == "passed" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
