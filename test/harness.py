"""
Helpers for the HyperI Linux audit collector docker test harness.

Ports the old VM snapshot/reset regime to disposable containers. One persistent
syslog receiver (see conftest.py) spans the whole run; each distro+version is
baked, started, converged (role in config-only mode), fed a unique marker via a
seeded audit.log, checked for that marker at the receiver, then torn down - one
at a time. Host-adaptive: amd64-only images (el6) skip on an arm64 host.
"""

import os
import platform
import subprocess
import time
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROLE_FILES = HERE.parent / "roles" / "hyperi_audit" / "files"
_MATRIX = yaml.safe_load((HERE / "matrix.yml").read_text())
RECEIVER_IMAGE = _MATRIX["receiver_image"]
NETWORK = _MATRIX["network"]
DISTROS = _MATRIX["distros"]

RECEIVER_NAME = "hyperi-audit-receiver"
RECEIVER_LOG = "/var/log/hyperi-received/received.log"
COLLECTOR_ADDRESS = RECEIVER_NAME  # resolvable container name on NETWORK
AUDIT_LOG = "/var/log/audit/audit.log"

HOST_ARCH = platform.machine().lower()  # aarch64/arm64 vs x86_64/amd64
HOST_IS_ARM = HOST_ARCH in ("arm64", "aarch64")


def run(cmd, check=True, timeout=900, cwd=None, env=None):
    """Run a command list, capturing output; raise a readable error on failure."""
    # encoding/errors are pinned explicitly: text=True alone decodes with the
    # locale's codec, so a stray non-UTF8 byte in a container's output (an EOL
    # distro's package manager is a fine source of those) raises
    # UnicodeDecodeError and takes the whole run down instead of failing a test.
    p = subprocess.run(
        cmd,
        timeout=timeout,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            f"command failed ({p.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}"
        )
    return p


def image_exists(tag):
    return run(["docker", "image", "inspect", tag], check=False).returncode == 0


def _platform_args(distro):
    p = distro.get("platform")
    return ["--platform", p] if p else []


def harness_image(distro):
    return f"hyperi-harness-{distro['id']}"


def uut_name(distro):
    return f"hyperi-uut-{distro['id']}"


def bake(distro):
    """Build the per-distro image (python3 + rsyslog + audit pre-installed)."""
    # Modern EL uses dnf (Dockerfile.el); EOL EL (el6/el7) ships yum, so route it
    # to the yum bake. An explicit `dockerfile` in the matrix overrides both.
    if distro.get("dockerfile"):
        df_name = distro["dockerfile"]
    elif distro["family"] == "el" and distro.get("eol"):
        df_name = "Dockerfile.el-yum"
    else:
        df_name = f"Dockerfile.{distro['family']}"
    dockerfile = HERE / "images" / df_name
    run(
        [
            "docker",
            "build",
            "-t",
            harness_image(distro),
            "--build-arg",
            f"BASE={distro['base']}",
            *_platform_args(distro),
            "-f",
            str(dockerfile),
            str(HERE / "images"),
        ]
    )


def start_uut(distro):
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


def _ansible_env():
    env = dict(os.environ)
    env["ANSIBLE_CONFIG"] = str(HERE / "ansible.cfg")
    env["ANSIBLE_COLLECTIONS_PATH"] = str(HERE / "collections")
    return env


def rules_source(level=None, profile_override=None):
    """The role file a given profile selection is expected to deploy verbatim."""
    stem = profile_override if profile_override else (level or "medium")
    return ROLE_FILES / f"hyperi-audit-{stem}.rules"


def converge(distro, level="medium", profile_override=None):
    """Apply the role in config-only mode over the community.docker connection."""
    name = uut_name(distro)
    cmd = [
        "ansible-playbook",
        "-i",
        f"{name},",
        "converge.yml",
        "-e",
        f"collector_address={COLLECTOR_ADDRESS}",
        "-e",
        f"hyperi_audit_level={level}",
        "-e",
        "ansible_connection=community.docker.docker",
        "-e",
        "ansible_user=root",
        "-e",
        f"ansible_host={name}",
    ]
    # The profile override REPLACES the level's rules file when set; the role
    # treats an empty/undefined value as "no override", so only pass it when asked.
    if profile_override:
        cmd += ["-e", f"hyperi_audit_profile_override={profile_override}"]
    # Some distros ship a too-old default python3 for modern ansible-core
    # (e.g. openSUSE Leap 15.6 -> 3.6); pin a newer interpreter when set.
    if distro.get("python"):
        cmd += ["-e", f"ansible_python_interpreter={distro['python']}"]
    run(cmd, cwd=str(HERE), env=_ansible_env())


def exec_in(name, script):
    return run(["docker", "exec", name, "sh", "-c", script], check=False)


def rsyslog_config_check(name):
    """Validate the UUT's rsyslog config without starting the daemon.

    `rsyslogd -N1` parses rsyslog.conf plus our drop-in and reports config
    errors on stderr, exiting non-zero on a fatal problem, WITHOUT launching the
    daemon. Returns (rc, combined stdout+stderr) so the caller can assert both
    the exit code and scan the text for "error" - a broken include (e.g. a
    duplicated drop-in include on a modern EL host) surfaces here, where the
    marker substring check alone would not.
    """
    r = run(["docker", "exec", name, "rsyslogd", "-N1"], check=False)
    return r.returncode, r.stdout + r.stderr


def ensure_audit_log(name):
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


def start_rsyslog(name):
    # The role wrote /etc/rsyslog.d/99-hyperi-rsyslog.conf and made rsyslog.conf
    # include it; start rsyslogd manually (services are gated off in test mode).
    run(["docker", "exec", "-d", name, "rsyslogd"])
    time.sleep(2)


def seed_marker(name, marker):
    line = (
        "type=SYSCALL msg=audit(1600000000.000:1): arch=c000003e syscall=2 "
        'success=yes exit=0 comm="hyperi-test" key="%s"' % marker
    )
    run(
        [
            "docker",
            "exec",
            name,
            "sh",
            "-c",
            "printf '%%s\\n' '%s' >> %s" % (line, AUDIT_LOG),
        ]
    )


def receiver_log():
    r = run(["docker", "exec", RECEIVER_NAME, "cat", RECEIVER_LOG], check=False)
    return r.stdout if r.returncode == 0 else ""


def wait_for_marker(marker, timeout=60, interval=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if marker in receiver_log():
            return True
        time.sleep(interval)
    return False


def teardown_uut(distro):
    run(["docker", "rm", "-f", uut_name(distro)], check=False)
