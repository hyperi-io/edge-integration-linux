"""Helpers for the Docker test harness.

One syslog receiver (conftest.py) spans the run. Each distro in matrix.yml is
baked, started, converged with the role in config-only mode, checked and torn
down, one at a time. amd64-only images skip on an arm64 host.
"""

import json
import os
import platform
import subprocess
import time
import uuid
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parent
_MATRIX = yaml.safe_load((HERE / "matrix.yml").read_text(encoding="utf-8"))
RECEIVER_IMAGE: str = _MATRIX["receiver_image"]
NETWORK: str = _MATRIX["network"]
DISTROS: list[dict] = _MATRIX["distros"]

RECEIVER_NAME = "hyperi-audit-receiver"
RECEIVER_LOG = "/var/log/hyperi-received/received.log"
RECEIVER_ADDRESS = RECEIVER_NAME  # resolvable container name on NETWORK
AUDIT_LOG = "/var/log/audit/audit.log"
RULES_PATH = "/etc/audit/rules.d/hyperi-audit.rules"
FORWARDER_PATH = "/etc/rsyslog.d/99-hyperi-rsyslog.conf"

HOST_ARCH = platform.machine().lower()
HOST_IS_ARM = HOST_ARCH in ("arm64", "aarch64")

# hyperi-ci's Docker Hub pull-through prefix, set only on runners that reach it.
DOCKERHUB_MIRROR = os.environ.get("HYPERCI_DOCKERHUB_MIRROR", "").rstrip("/")

# rsyslogd -N1 exits non-zero on benign warnings, so checks key on these instead.
CONFIG_PROBLEMS = (
    "error",
    "could not load",
    "not found",
    "more than once",
    "already in this config",
)


def run(
    cmd: list[str],
    check: bool = True,
    timeout: int = 900,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and capture its output.

    Args:
        cmd: The argv to run.
        check: Raise when the command exits non-zero.
        timeout: Seconds before the command is killed.
        cwd: Working directory.
        env: Full environment for the child.

    Returns:
        The completed process, stdout and stderr decoded as UTF-8.

    Raises:
        RuntimeError: ``check`` is set and the command failed. The message
            carries both output streams.
    """
    # errors="replace": EOL distros' package managers emit non-UTF-8 bytes.
    p = subprocess.run(
        cmd,
        timeout=timeout,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            f"command failed ({p.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}"
        )
    return p


def hub_image(ref: str) -> str:
    """Return a Docker Hub image reference routed through the mirror, if set."""
    if not DOCKERHUB_MIRROR:
        return ref
    repo = ref.split("@")[0].split(":")[0]
    name = ref if "/" in repo else f"library/{ref}"
    return f"{DOCKERHUB_MIRROR}/{name}"


def image_exists(tag: str) -> bool:
    """Return True when the local daemon has an image with this tag."""
    return run(["docker", "image", "inspect", tag], check=False).returncode == 0


def _platform_args(distro: Mapping) -> list[str]:
    p = distro.get("platform")
    return ["--platform", p] if p else []


def harness_image(distro: Mapping) -> str:
    """Return the baked image tag for a matrix entry."""
    return f"hyperi-harness-{distro['id']}"


def uut_name(distro: Mapping) -> str:
    """Return the container name for a matrix entry."""
    return f"hyperi-uut-{distro['id']}"


def skip_if_foreign_arch(distro: Mapping) -> None:
    """Skip an amd64-only distro on an arm64 host."""
    if distro.get("platform") == "linux/amd64" and HOST_IS_ARM:
        pytest.skip(f"{distro['id']} is amd64-only; host is {HOST_ARCH}")


def marker(distro: Mapping, kind: str = "MARKER") -> str:
    """Return a run-unique string to seed into audit.log."""
    slug = distro["id"].replace(".", "_").replace("-", "_")
    return f"HYPERI_HARNESS_{kind}_{slug}_{uuid.uuid4().hex[:8]}"


def _receiver_base() -> str:
    dockerfile = (HERE / "receiver" / "Dockerfile").read_text(encoding="utf-8")
    for line in dockerfile.splitlines():
        if line.startswith("ARG BASE="):
            return line.split("=", 1)[1]
    raise RuntimeError("test/receiver/Dockerfile has no ARG BASE= default")


def build_receiver() -> None:
    """Build the receiver image, through the mirror when one is set."""
    base_args = ["--build-arg", f"BASE={hub_image(_receiver_base())}"]
    run(
        [
            "docker",
            "build",
            "-t",
            RECEIVER_IMAGE,
            *(base_args if DOCKERHUB_MIRROR else []),
            str(HERE / "receiver"),
        ]
    )


def bake(distro: Mapping) -> None:
    """Build the per-distro image with python3, rsyslog and audit installed."""
    # An explicit matrix `dockerfile` wins. EOL EL ships yum rather than dnf.
    if distro.get("dockerfile"):
        df_name = distro["dockerfile"]
    elif distro["family"] == "el" and distro.get("eol"):
        df_name = "Dockerfile.el-yum"
    else:
        df_name = f"Dockerfile.{distro['family']}"
    run(
        [
            "docker",
            "build",
            "-t",
            harness_image(distro),
            "--build-arg",
            f"BASE={hub_image(distro['base'])}",
            *_platform_args(distro),
            "-f",
            str(HERE / "images" / df_name),
            str(HERE / "images"),
        ]
    )


def start_uut(distro: Mapping) -> str:
    """Start the baked image idle on the harness network.

    Returns:
        The container name.
    """
    name = uut_name(distro)
    run(["docker", "rm", "-f", name], check=False)
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--network",
            NETWORK,
            *_platform_args(distro),
            harness_image(distro),
            "tail",
            "-f",
            "/dev/null",
        ]
    )
    return name


def ansible_env() -> dict[str, str]:
    env = dict(os.environ)
    env["ANSIBLE_CONFIG"] = str(HERE / "ansible.cfg")
    env["ANSIBLE_COLLECTIONS_PATH"] = str(HERE / "collections")
    return env


def converge(
    distro: Mapping,
    extra_vars: Mapping[str, object] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Apply the role in config-only mode over the community.docker connection.

    Args:
        distro: The matrix entry to converge.
        extra_vars: Role variables, passed as one JSON document so lists keep
            their type. The receiver defaults to the harness receiver unless
            the caller names it, under either variable name.
        check: Raise when the play fails. Off for tests that expect a failure.

    Returns:
        The completed ansible-playbook process.
    """
    name = uut_name(distro)
    variables: dict[str, object] = {
        "ansible_connection": "community.docker.docker",
        "ansible_user": "root",
        "ansible_host": name,
    }
    caller = dict(extra_vars or {})
    if not {"hyperi_audit_receiver_address", "collector_address"} & caller.keys():
        variables["hyperi_audit_receiver_address"] = RECEIVER_ADDRESS
    if distro.get("python"):
        variables["ansible_python_interpreter"] = distro["python"]
    variables |= caller
    cmd = [
        "ansible-playbook",
        "-i",
        f"{name},",
        "converge.yml",
        "-e",
        json.dumps(variables),
    ]
    return run(cmd, check=check, cwd=HERE, env=ansible_env())


def exec_in(name: str, script: str) -> subprocess.CompletedProcess[str]:
    """Run a shell script in the container, without raising on failure."""
    return run(["docker", "exec", name, "sh", "-c", script], check=False)


def read_file(name: str, path: str) -> str:
    """Return a file from the container, asserting it exists."""
    got = run(["docker", "exec", name, "cat", path], check=False)
    assert got.returncode == 0, f"{path} not deployed:\n{got.stderr}"
    return got.stdout


def assert_rsyslog_config_valid(name: str) -> None:
    """Parse the deployed rsyslog config with ``rsyslogd -N1``, without starting it.

    A missing output module, a malformed action or a drop-in included twice
    shows up here, where a substring check on the file would pass.
    """
    r = run(["docker", "exec", name, "rsyslogd", "-N1"], check=False)
    output = r.stdout + r.stderr
    assert not any(p in output.lower() for p in CONFIG_PROBLEMS), (
        f"rsyslogd -N1 reported a config problem (rc={r.returncode}):\n{output}"
    )


def ensure_audit_log(name: str) -> None:
    """Create an empty audit.log for imfile to follow."""
    run(
        [
            "docker",
            "exec",
            name,
            "sh",
            "-c",
            f"mkdir -p /var/log/audit && touch {AUDIT_LOG}",
        ]
    )


def start_rsyslog(name: str) -> None:
    """Start rsyslogd by hand: the role's service tasks are off in test mode."""
    run(["docker", "exec", "-d", name, "rsyslogd"])
    time.sleep(2)


def seed_marker(name: str, marker_text: str) -> None:
    """Append an audit record carrying the marker to the container's audit.log."""
    line = (
        "type=SYSCALL msg=audit(1600000000.000:1): arch=c000003e syscall=2 "
        f'success=yes exit=0 comm="hyperi-test" key="{marker_text}"'
    )
    run(["docker", "exec", name, "sh", "-c", f"printf '%s\\n' '{line}' >> {AUDIT_LOG}"])


def receiver_log() -> str:
    """Return everything the receiver has written so far."""
    r = run(["docker", "exec", RECEIVER_NAME, "cat", RECEIVER_LOG], check=False)
    return r.stdout if r.returncode == 0 else ""


def assert_delivered_once(
    marker_text: str,
    listener: str = "audit",
    timeout: int = 60,
    interval: int = 3,
    settle: int = 6,
) -> None:
    """Wait for the marker at the receiver, then require one copy on the listener.

    A second copy, or one on another listener, means the audit stream also
    reached the general catch-all, or rsyslog loaded the drop-in twice. The
    settle wait gives a late duplicate time to arrive.

    Args:
        marker_text: The run-unique marker seeded into audit.log.
        listener: The receiver input the marker must arrive on.
        timeout: Seconds to wait for the first copy.
        interval: Seconds between polls.
        settle: Seconds to wait after the first copy before counting.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and marker_text not in receiver_log():
        time.sleep(interval)
    time.sleep(settle)
    lines = [x for x in receiver_log().splitlines() if marker_text in x]
    assert len(lines) == 1, (
        f"marker {marker_text} arrived {len(lines)} times, expected exactly 1\n"
        + "\n".join(lines)
    )
    assert lines[0].startswith(f"{listener} "), (
        f"marker arrived on the wrong listener, expected {listener}: {lines[0]}"
    )
    assert " auditd" in lines[0], f"marker lost its auditd tag: {lines[0]}"


def assert_not_delivered(marker_text: str, wait: int = 20) -> None:
    """Require the marker never reaches the receiver within the wait."""
    time.sleep(wait)
    assert marker_text not in receiver_log(), f"marker {marker_text} was delivered"


def install_receiver_ca(name: str, dest_dir: str = "/etc/hyperi-test") -> str:
    """Copy the receiver's CA certificate into a container and return its path."""
    ca = run(["docker", "exec", RECEIVER_NAME, "cat", "/etc/hyperi-tls/ca.pem"]).stdout
    path = f"{dest_dir}/ca.pem"
    subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            name,
            "sh",
            "-c",
            f"mkdir -p {dest_dir} && cat > {path}",
        ],
        input=ca,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return path


def teardown_uut(distro: Mapping) -> None:
    """Remove the container under test."""
    run(["docker", "rm", "-f", uut_name(distro)], check=False)
