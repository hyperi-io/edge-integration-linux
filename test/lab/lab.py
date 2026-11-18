"""Boot throwaway real-kernel VMs on a KVM-capable docker host for audit tests.

QEMU runs inside a container on that host with /dev/kvm passed through. Each VM
is reached through an ssh ProxyJump to the host, because the VM's ssh port is
published on the host's loopback only. Set AUDITLAB_DOCKER_CONTEXT,
AUDITLAB_JUMP (user@host) and AUDITLAB_CACHE (an absolute path on that host).
"""

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


def _setting(name: str) -> str:
    """Return a required lab setting from the environment, or exit naming it."""
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"{name} is not set: see the module docstring of {__file__}")
    return value


CONTEXT = os.environ.get("AUDITLAB_DOCKER_CONTEXT", "")
JUMP = os.environ.get("AUDITLAB_JUMP", "")
IMAGE = "auditlab:local"
CACHE = os.environ.get("AUDITLAB_CACHE", "")
KEY_DIR = Path(__file__).parent / ".keys"
KEY = KEY_DIR / "id_ed25519"
KNOWN_HOSTS = KEY_DIR / "known_hosts"
READY_TIMEOUT = 300


@dataclass(frozen=True)
class Distro:
    """A cloud image and where to verify it."""

    url: str
    sums_url: str
    algo: str
    port: int


DISTROS: dict[str, Distro] = {
    "debian-13": Distro(
        "https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2",
        "https://cloud.debian.org/images/cloud/trixie/latest/SHA512SUMS",
        "sha512sum",
        2201,
    ),
    "ubuntu-24.04": Distro(
        "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
        "https://cloud-images.ubuntu.com/noble/current/SHA256SUMS",
        "sha256sum",
        2202,
    ),
    "rocky-9": Distro(
        "https://dl.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2",
        "https://dl.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2.CHECKSUM",
        "sha256sum",
        2203,
    ),
    "esh": Distro(
        "https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2",
        "https://cloud.debian.org/images/cloud/trixie/latest/SHA512SUMS",
        "sha512sum",
        2204,
    ),
}

FETCH = r"""
set -eu
f=$(basename "$URL")
mkdir -p /cache/base
cd /cache/base
if [ ! -f "$f" ]; then
  curl -fsSL -o "$f.part" "$URL"
  curl -fsSL -o "$f.sums" "$SUMS_URL"
  want=$(grep -F "$f" "$f.sums" | grep -v '^#' | head -n1 \
    | sed -E 's/.*= *//; s/^([0-9a-f]+).*/\1/')
  [ -n "$want" ]
  echo "$want  $f.part" | "$ALGO" -c -
  mv "$f.part" "$f"
fi
mkdir -p "/cache/vm/$NAME"
rm -f "/cache/vm/$NAME/disk.qcow2" "/cache/vm/$NAME/seed.img"
qemu-img create -q -f qcow2 -F qcow2 -b "/cache/base/$f" \
  "/cache/vm/$NAME/disk.qcow2" "${DISK_GB}G"
printf '%s\n' "$USER_DATA" > /tmp/user-data
printf 'instance-id: %s-%s\nlocal-hostname: %s\n' "$NAME" "$STAMP" "$NAME" \
  > /tmp/meta-data
cloud-localds "/cache/vm/$NAME/seed.img" /tmp/user-data /tmp/meta-data
"""


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a docker command against the remote context."""
    return subprocess.run(
        ["docker", "--context", CONTEXT, *args],
        check=check,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def container(name: str) -> str:
    """Return the container name for a VM."""
    return f"auditlab-{name}"


def ssh_opts(port: int) -> list[str]:
    """Return the ssh options that reach a VM through the jump host."""
    return [
        "-i", str(KEY),
        "-J", JUMP,
        "-p", str(port),
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={KNOWN_HOSTS}",
        "-o", "LogLevel=ERROR",
    ]  # fmt: skip


def forget_host_key(port: int) -> None:
    """Drop a VM's host key: every `up` boots a fresh VM on the same port."""
    if KNOWN_HOSTS.exists():
        subprocess.run(
            ["ssh-keygen", "-q", "-R", f"[127.0.0.1]:{port}", "-f", str(KNOWN_HOSTS)],
            check=False,
            capture_output=True,
        )


def ensure_key() -> str:
    """Create the lab keypair if missing and return the public key."""
    if not KEY.exists():
        KEY_DIR.mkdir(mode=0o700, exist_ok=True)
        subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                "auditlab",
                "-f",
                str(KEY),
            ],
            check=True,
        )
    return KEY.with_suffix(".pub").read_text(encoding="utf-8").strip()


def user_data(pubkey: str) -> str:
    """Return cloud-init user-data for the `lab` user."""
    return (
        "#cloud-config\n"
        "users:\n"
        "  - name: lab\n"
        "    sudo: ALL=(ALL) NOPASSWD:ALL\n"
        "    shell: /bin/bash\n"
        "    lock_passwd: true\n"
        f"    ssh_authorized_keys: [{pubkey}]\n"
        "ssh_pwauth: false\n"
    )


def lookup(name: str) -> Distro:
    """Return the distro entry or exit with the valid names."""
    if name not in DISTROS:
        sys.exit(f"unknown distro {name!r}, choose from {', '.join(DISTROS)}")
    return DISTROS[name]


def build_image() -> None:
    """Build the qemu container image on the remote daemon."""
    docker("build", "-t", IMAGE, str(Path(__file__).parent))


def run_ssh(
    name: str, cmd: list[str], *, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a command in the VM over ssh."""
    d = lookup(name)
    return subprocess.run(
        ["ssh", *ssh_opts(d.port), "-o", "ConnectTimeout=10", "lab@127.0.0.1", *cmd],
        check=False,
        capture_output=capture,
        encoding="utf-8",
        errors="replace",
    )


def cmd_up(args: argparse.Namespace) -> int:
    """Boot a VM and wait for ssh."""
    d = lookup(args.distro)
    name, cname = args.distro, container(args.distro)
    pub = ensure_key()
    docker("rm", "-f", cname, check=False)
    build_and_tag()
    fetch_env = {
        "URL": d.url, "SUMS_URL": d.sums_url, "ALGO": d.algo, "NAME": name,
        "USER_DATA": user_data(pub), "STAMP": str(int(time.time())),
        "DISK_GB": str(args.disk),
    }  # fmt: skip
    env_args = [a for k, v in fetch_env.items() for a in ("-e", f"{k}={v}")]
    r = docker(
        "run",
        "--rm",
        "-v",
        f"{CACHE}:/cache",
        *env_args,
        "--entrypoint",
        "/bin/sh",
        IMAGE,
        "-c",
        FETCH,
        check=False,
    )
    if r.returncode:
        sys.exit(f"image prep failed:\n{r.stdout}{r.stderr}")
    vm = f"/cache/vm/{name}"
    forget_host_key(d.port)
    docker(
        "run", "-d", "--name", cname, "--label", "auditlab=1",
        "--device", "/dev/kvm", "-v", f"{CACHE}:/cache",
        "-p", f"127.0.0.1:{d.port}:2222",
        IMAGE,
        "qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-machine", "q35",
        "-smp", str(args.cpus), "-m", str(args.mem), "-nographic",
        "-drive", f"file={vm}/disk.qcow2,if=virtio,format=qcow2",
        "-drive", f"file={vm}/seed.img,if=virtio,format=raw,media=cdrom,readonly=on",
        "-netdev", "user,id=n0,hostfwd=tcp::2222-:22" + "".join(
            f",hostfwd=tcp::{p}-:{p}" for p in args.forward
        ),
        "-device", "virtio-net-pci,netdev=n0",
        "-serial", f"file:{vm}/console.log",
    )  # fmt: skip
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        if run_ssh(name, ["true"], capture=True).returncode == 0:
            print(f"{name} up: ssh -F <(test/lab/lab.py ssh-config {name}) {name}")
            print(f"or: lab.py run {name} -- <cmd>")
            return 0
        time.sleep(5)
    log = docker("logs", "--tail", "30", cname, check=False)
    sys.exit(f"{name} not reachable in {READY_TIMEOUT}s\n{log.stdout}{log.stderr}")


def build_and_tag() -> str:
    """Return the image tag, building it first when absent."""
    if docker("image", "inspect", IMAGE, check=False).returncode:
        build_image()
    return IMAGE


def cmd_run(args: argparse.Namespace) -> int:
    """Run a command in the VM."""
    return run_ssh(args.distro, args.cmd).returncode


def cmd_ssh_config(args: argparse.Namespace) -> int:
    """Print an ssh config Host block for the VM."""
    d = lookup(args.distro)
    print(
        f"Host {args.distro}\n"
        "  HostName 127.0.0.1\n"
        f"  Port {d.port}\n"
        "  User lab\n"
        f"  IdentityFile {KEY.resolve()}\n"
        "  IdentitiesOnly yes\n"
        f"  ProxyJump {JUMP}\n"
        "  StrictHostKeyChecking accept-new\n"
        f"  UserKnownHostsFile {KNOWN_HOSTS.resolve()}\n"
        "  LogLevel ERROR"
    )
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    """Remove a VM or all of them, with their overlays."""
    names = list(DISTROS) if args.all else [args.distro]
    for n in names:
        forget_host_key(DISTROS[n].port)
        docker("rm", "-f", container(n), check=False)
        docker(
            "run", "--rm", "-v", f"{CACHE}:/cache", "--entrypoint", "/bin/rm", IMAGE,
            "-rf", f"/cache/vm/{n}",
            check=False,
        )  # fmt: skip
    return 0


def main() -> int:
    """Parse arguments and dispatch."""
    for name in ("AUDITLAB_DOCKER_CONTEXT", "AUDITLAB_JUMP", "AUDITLAB_CACHE"):
        _setting(name)
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="sub", required=True)
    up = sub.add_parser("up", help="boot a VM")
    up.add_argument("distro")
    up.add_argument("--cpus", type=int, default=2)
    up.add_argument("--mem", type=int, default=2048, help="MB")
    up.add_argument("--disk", type=int, default=20, help="GB")
    up.add_argument(
        "--forward", type=int, action="append", default=[],
        help="guest TCP port to expose on the VM container (repeatable)",
    )  # fmt: skip
    up.set_defaults(fn=cmd_up)
    rn = sub.add_parser("run", help="run a command in a VM")
    rn.add_argument("distro")
    rn.add_argument("cmd", nargs=argparse.REMAINDER)
    rn.set_defaults(fn=cmd_run)
    sc = sub.add_parser("ssh-config", help="print an ssh Host block")
    sc.add_argument("distro")
    sc.set_defaults(fn=cmd_ssh_config)
    dn = sub.add_parser("down", help="destroy a VM")
    dn.add_argument("distro", nargs="?")
    dn.add_argument("--all", action="store_true")
    dn.set_defaults(fn=cmd_down)
    args = p.parse_args()
    if args.sub == "run" and args.cmd[:1] == ["--"]:
        args.cmd = args.cmd[1:]
    if args.sub == "down" and not (args.all or args.distro):
        p.error("give a distro or --all")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
