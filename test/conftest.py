"""pytest fixtures for the Docker test harness."""

import time
from collections.abc import Iterator, Mapping

import pytest

import harness


@pytest.fixture(scope="session")
def network() -> Iterator[str]:
    """Create the harness network for the whole run."""
    harness.run(["docker", "network", "create", harness.NETWORK], check=False)
    yield harness.NETWORK
    harness.run(["docker", "network", "rm", harness.NETWORK], check=False)


@pytest.fixture(scope="session")
def receiver(network: str) -> Iterator[str]:
    """Run one syslog receiver that every distro under test forwards into."""
    if not harness.image_exists(harness.RECEIVER_IMAGE):
        harness.build_receiver()
    harness.run(["docker", "rm", "-f", harness.RECEIVER_NAME], check=False)
    harness.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            harness.RECEIVER_NAME,
            "--network",
            network,
            harness.RECEIVER_IMAGE,
        ]
    )
    time.sleep(2)
    yield harness.RECEIVER_NAME
    # harness.run captures output, so print the receiver's log or it is lost.
    logs = harness.run(["docker", "logs", harness.RECEIVER_NAME], check=False)
    print(f"--- receiver rsyslogd stdout ---\n{logs.stdout}")
    print(f"--- receiver rsyslogd stderr ---\n{logs.stderr}")
    harness.run(["docker", "rm", "-f", harness.RECEIVER_NAME], check=False)


def _representative_distro() -> Mapping:
    """Return the first current distro that runs natively on this host."""
    for d in harness.DISTROS:
        if d.get("eol"):
            continue
        if d.get("platform") == "linux/amd64" and harness.HOST_IS_ARM:
            continue
        return d
    pytest.skip("no current distro in the matrix runs natively on this host")


@pytest.fixture(scope="module")
def representative(network: str) -> Iterator[tuple[Mapping, str]]:
    """One running current distro, shared by the tests in a module.

    Role-side logic (profile selection, input validation) is the same on every
    target, so one distro covers it. Cross-distro coverage is test_forwarding.py.
    """
    distro = _representative_distro()
    harness.bake(distro)
    name = harness.start_uut(distro)
    yield distro, name
    harness.teardown_uut(distro)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark EOL-distro cases `eol`, so CI can run them as a separate job."""
    eol_ids = {d["id"] for d in harness.DISTROS if d.get("eol")}
    for item in items:
        if any(f"[{eid}" in item.nodeid for eid in eol_ids):
            item.add_marker(pytest.mark.eol)
