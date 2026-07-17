"""
pytest fixtures for the HyperI audit collector docker harness.

The receiver is a SESSION fixture: one syslog sink comes up once, persists across
every distro test in the run, and stops at the end - each OS-under-test forwards
into it. This mirrors the long-lived collector of the old VM regime.
"""

import time

import pytest

import harness


@pytest.fixture(scope="session")
def network():
    harness.run(["docker", "network", "create", harness.NETWORK], check=False)
    yield harness.NETWORK
    harness.run(["docker", "network", "rm", harness.NETWORK], check=False)


@pytest.fixture(scope="session")
def receiver(network):
    if not harness.image_exists(harness.RECEIVER_IMAGE):
        harness.run(
            [
                "docker",
                "build",
                "-t",
                harness.RECEIVER_IMAGE,
                str(harness.HERE / "receiver"),
            ]
        )
    harness.run(["docker", "rm", "-f", harness.RECEIVER_NAME], check=False)
    harness.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            harness.RECEIVER_NAME,
            "--network",
            harness.NETWORK,
            harness.RECEIVER_IMAGE,
        ]
    )
    time.sleep(2)
    yield harness.RECEIVER_NAME
    # Dump the receiver's own rsyslogd log on the way out - handy when a test
    # failed. harness.run captures output, so this MUST print it explicitly or
    # the dump is silently discarded and the aid is worthless.
    logs = harness.run(["docker", "logs", harness.RECEIVER_NAME], check=False)
    print(f"--- receiver rsyslogd stdout ---\n{logs.stdout}")
    print(f"--- receiver rsyslogd stderr ---\n{logs.stderr}")
    harness.run(["docker", "rm", "-f", harness.RECEIVER_NAME], check=False)


def pytest_collection_modifyitems(config, items):
    """Tag EOL-distro cases with the `eol` marker so CI can run them as a
    best-effort job (`-m eol`) separate from the required current matrix
    (`-m "not eol"`)."""
    eol_ids = {d["id"] for d in harness.DISTROS if d.get("eol")}
    for item in items:
        if any(f"[{eid}]" in item.nodeid for eid in eol_ids):
            item.add_marker(pytest.mark.eol)
