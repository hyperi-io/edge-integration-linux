"""The rendered rulesets on a real kernel: every rule loads, and the keys fire.

These load audit rules into the running kernel through sudo, so they run only
with HYPERI_AUDIT_KERNEL_TESTS=1: the kernel job in CI, or a lab VM.
"""

import json
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

import harness

pytestmark = [
    pytest.mark.kernel,
    pytest.mark.skipif(
        os.environ.get("HYPERI_AUDIT_KERNEL_TESTS") != "1",
        reason="loads audit rules into the host kernel (HYPERI_AUDIT_KERNEL_TESTS=1)",
    ),
]

COMBOS = [
    ("low", []),
    ("medium", []),
    ("high", []),
    ("medium", ["edge"]),
    ("medium", ["webserver"]),
    ("high", ["webserver", "edge", "container-host"]),
]

LOGIN_UID = os.getuid()
LOGIN_USER = os.environ.get("USER", "runner")

CONNECT = (
    "python3 -c 'import socket; s = socket.socket(); "
    's.bind(("127.0.0.1", 0)); s.listen(); '
    "socket.create_connection(s.getsockname())'"
)

# key, levels it fires at, levels it stays silent at, and the trigger run as
# the login user with a login uid set.
DETECTIONS = [
    (
        "T1543.002_systemd",
        "low medium high",
        "",
        "sudo touch /etc/systemd/system/hyperi-probe.service",
    ),
    ("T1053.003_cron", "low medium high", "", "sudo touch /etc/cron.d/hyperi-probe"),
    ("T1037.004_rclocal", "low medium high", "", "sudo touch /etc/rc.local"),
    ("T1087.001_shadow", "low medium high", "", "sudo head -c1 /etc/shadow"),
    (
        "T1059_devshm_exec",
        "low medium high",
        "",
        "cp /usr/bin/true /dev/shm/hp; /dev/shm/hp; rm -f /dev/shm/hp",
    ),
    (
        "T1070.006_time",
        "medium high",
        "low",
        "touch -d 2001-01-01 /tmp/hyperi-probe-time",
    ),
    (
        "T1055.008_ptrace",
        "medium high",
        "low",
        "python3 -c 'import ctypes; ctypes.CDLL(None).ptrace(0, 0, 0, 0)'",
    ),
    ("T1071_connect4", "medium high", "low", CONNECT),
    (
        "T1011_socket",
        "high",
        "low medium",
        "python3 -c 'import socket; socket.socket()'",
    ),
    ("T1548.001_priv_ctx_exec", "high", "low medium", "sudo /usr/bin/id"),
]

PATH_FIELD = re.compile(r"(?:^-w |-F (?:path|dir|exe)=)(\S+)")

# Syscalls the ruleset names that an older auditctl or kernel may not know.
NEWER_SYSCALLS = {
    "execveat",
    "fchmodat2",
    "kexec_file_load",
    "openat2",
    "pidfd_getfd",
    "process_vm_readv",
    "process_vm_writev",
    "renameat2",
    "userfaultfd",
    "io_uring_setup",
    "memfd_create",
    "bpf",
    "finit_module",
}


def sudo(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command as root through sudo."""
    return harness.run(["sudo", *args], check=check, timeout=120)


def render(level: str, use_cases: list[str], out: Path) -> None:
    """Render the ruleset for one level and overlay set."""
    variables = {"out": str(out), "level": level, "use_cases": use_cases}
    harness.run(
        [
            "ansible-playbook",
            "-i",
            "localhost,",
            "render.yml",
            "-e",
            json.dumps(variables),
        ],
        cwd=harness.HERE,
    )


def rules(path: Path) -> list[str]:
    """Return the rule lines of a rendered ruleset."""
    text = path.read_text(encoding="utf-8")
    return [x for x in text.splitlines() if x.startswith(("-a ", "-w "))]


def explained(rule: str, error: str) -> bool:
    """Return True when this host lacks what the rule refers to.

    Expected on some distros: a watch whose directory is missing here, an
    SELinux field without SELinux, or a syscall newer than this auditctl.
    """
    if "subj_type=" in rule and not Path("/sys/fs/selinux").exists():
        return True
    unknown = re.search(r"Syscall name unknown: (\S+)", error)
    if unknown:
        return unknown.group(1) in NEWER_SYSCALLS
    m = PATH_FIELD.search(rule)
    if not m:
        return False
    target = Path(m.group(1).rstrip("/"))
    return not (target if "-F dir=" in rule else target.parent).exists()


def load_unlocked(path: Path) -> None:
    """Load a ruleset without its final -e 2, so later tests can reload."""
    unlocked = path.with_suffix(".unlocked")
    lines = path.read_text(encoding="utf-8").splitlines()
    unlocked.write_text(
        "\n".join(x for x in lines if x != "-e 2") + "\n", encoding="utf-8"
    )
    sudo("auditctl", "-D")
    sudo("auditctl", "-R", str(unlocked), check=False)


@pytest.fixture(scope="module")
def workdir() -> Iterator[Path]:
    """A scratch directory, and a clean kernel ruleset afterwards."""
    with tempfile.TemporaryDirectory(prefix="hyperi-kernel-") as d:
        yield Path(d)
    sudo("auditctl", "-D", check=False)


@pytest.mark.parametrize(
    ("level", "use_cases"),
    COMBOS,
    ids=[f"{lv}-{'+'.join(uc) or 'none'}" for lv, uc in COMBOS],
)
def test_every_rule_loads(level: str, use_cases: list[str], workdir: Path) -> None:
    path = workdir / f"{level}-{'-'.join(use_cases)}.rules"
    render(level, use_cases, path)
    sudo("auditctl", "-D")
    unexplained = []
    for rule in rules(path):
        result = sudo("auditctl", *rule.split(), check=False)
        if result.returncode != 0 and not explained(rule, result.stderr):
            unexplained.append(f"{rule}\n    {result.stderr.strip()}")
    sudo("auditctl", "-D")
    assert not unexplained, "rules the kernel rejected:\n" + "\n".join(unexplained)


def events(key: str) -> int:
    """Return how many events the audit log holds for a key."""
    out = sudo("ausearch", "--input-logs", "-k", key, "--raw", check=False).stdout
    return sum(1 for line in out.splitlines() if line.startswith("type=SYSCALL"))


def fires(key: str, script: str) -> bool:
    """Run a trigger as the login user and report whether the key logged it."""
    before = events(key)
    # Setting /proc/self/loginuid gives the trigger an auid, as a login would.
    wrapped = (
        f"echo {LOGIN_UID} > /proc/self/loginuid 2>/dev/null; "
        f"exec sudo -u {LOGIN_USER} sh -c {json.dumps(script)}"
    )
    sudo("sh", "-c", wrapped, check=False)
    # auditd writes asynchronously, so the event can land after the trigger exits.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if events(key) > before:
            return True
        time.sleep(0.5)
    return False


@pytest.mark.parametrize("level", ["low", "medium", "high"])
@pytest.mark.parametrize(
    ("key", "on", "off", "script"), DETECTIONS, ids=[d[0] for d in DETECTIONS]
)
def test_detection(
    level: str, key: str, on: str, off: str, script: str, workdir: Path
) -> None:
    path = workdir / f"det-{level}.rules"
    if not path.exists():
        render(level, [], path)
    load_unlocked(path)
    result = fires(key, script)
    if level in on.split():
        assert result, f"{key} did not fire at {level}"
    if level in off.split():
        assert not result, f"{key} fired at {level}"


def test_semantics_probes() -> None:
    out = sudo("bash", str(harness.HERE / "lab" / "semantics.sh")).stdout
    expected = {
        "E1": "true=1 false=1",
        "E2": "true=0 false=1",
        "E3": "true=0 false=1",
        "E3b": "true=1",
        "E4": "true=0",
        "E5": "cat=0 head=1",
        "E6": "daemon_true=1",
        "E7": "read=0 touch=1",
    }
    for case, text in expected.items():
        line = next((x for x in out.splitlines() if x.startswith(case + " ")), "")
        assert text in line, f"{case}: {line or 'missing'}\n{out}"
