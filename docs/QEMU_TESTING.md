# Disposable QEMU checks — v1

`tests/qemu_matrix.py` runs native distribution userspaces on one supplied x86_64 Linux kernel using software CPU emulation. The test host does not need KVM, chroot, ptrace, user namespaces or a container daemon. Guests have independent kernels and private ext4 disks; no host directory, host device, Docker socket or privileged host mount is exposed. The only host device read by QEMU is the random source for the guest RNG.

This helper currently expects the Ubuntu/Debian QEMU installation layout (or an extracted package tree in that layout). Run preparation as root so ownership metadata is represented correctly. QEMU itself uses TCG and does not require hardware virtualization.

## Prepare a test host

Install QEMU, cpio, squashfs-tools, e2fsprogs, Python 3 and pip using the host package manager. On Ubuntu, for example:

```bash
sudo apt install qemu-system-x86 cpio squashfs-tools e2fsprogs python3 python3-pip
mkdir -p qa/downloads qa/boot
curl -fL -o qa/downloads/vmlinuz https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/x86_64/netboot/vmlinuz-virt
curl -fL -o qa/downloads/initramfs https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/x86_64/netboot/initramfs-virt
curl -fL -o qa/downloads/modloop https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/x86_64/netboot/modloop-virt
(cd qa/boot && gzip -dc ../downloads/initramfs | cpio -id --no-absolute-filenames)
unsquashfs -no-xattrs -d qa/modules qa/downloads/modloop
python3 -m pip download --dest qa/wheels --only-binary=:all: -r requirements.txt -r requirements-dev.txt
python3 -m pip download --dest qa/wheels --only-binary=:all: --platform manylinux_2_28_x86_64 --implementation cp --python-version 310 --abi cp310 PySide6-Essentials==6.8.3 shiboken6==6.8.3
python3 -m pip download --dest qa/wheels --only-binary=:all: --platform any --abi none --implementation py --python-version 310 tomli exceptiongroup typing_extensions
```

The extra legacy-Qt download supplies the 6.8.3 abi3 wheels needed by Python 3.10/3.11 even when preparing on newer Python. The final command includes the Python 3.10-only pytest backports required by Ubuntu 22.04. Alpine uses its native musl-compatible Python/Qt packages instead of the glibc wheelhouse.

Download endpoints and moving image tags can change. Keep the recorded image manifests, kernel SHA-256 and the actual cached inputs when exact reproduction is required.

## Run

```bash
sudo python3 tests/qemu_matrix.py --state-dir qa/state --tools-dir / --boot-dir qa/boot --modules-dir qa/modules/modules --kernel qa/downloads/vmlinuz --wheelhouse qa/wheels --jobs 2
```

`--distro` selects one target and can be repeated. `--core-only` stops after native administration and terminal install/uninstall checks. `--probe path/to/script.sh` runs an explicitly supplied diagnostic in an already prepared disposable guest. Probe results have separate filenames and never replace the full test record.

Each guest uses its own disk, source copy and result markers. Runs are bounded, the supervisor terminates timed-out QEMU processes, and previous logs are retained. Failed discovery/bootstrap is not an application compatibility success. Re-running a target reuses its disposable disk and installs fresh project source, which allows a fix to be checked without rebuilding the whole environment. The APT recipe repairs interrupted *test-guest* package transactions before resuming.

The optional `ADMINW21_TEST_CA` environment variable names a local PEM certificate file for a test proxy. Only the disposable guest's native certificate stores are updated; TLS and package-signature verification remain enabled. Test payloads may contain proxy configuration from the host environment; keep the state directory private and outside release archives.

## Scope

Core checks change disposable accounts, passwords/lock states, group membership and crontabs; verify backup/restore and native installed-package inventory; and perform real terminal installation/uninstallation. Full runs add native Qt libraries and the pytest suite with offscreen Qt, installer rollback and disposable-child signalling checks.

The supplied `desktop_install_vm.sh` separately checks desktop registration, the PolicyKit XML target, the installed Qt runtime and complete removal of the owned launchers/policy. It requires native `pkexec` and the same explicit disposable-VM flag.

These guests do not boot the distribution's normal systemd/OpenRC/SELinux/AppArmor or desktop stack. A passing result does not certify a native X11/Wayland login, an actual PolicyKit agent prompt, service startup at boot, firewall changes, packet capture, all package mutations or ARM hardware. See `LINUX_COMPATIBILITY.md` for the validation scope.
