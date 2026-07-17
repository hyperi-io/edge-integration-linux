"""
End-to-end: for every distro+version, the role's rsyslog config forwards a seeded
audit.log marker to the central receiver.

One distro at a time (the kernel audit subsystem is host-global and it keeps the
shared receiver's log unambiguous). amd64-only images (el6) SKIP on an arm64 host
and run natively on an x64 host - "make Docker work where it can". The version-
gating logic is userspace-binary behaviour, so the arm64 subset still exercises it.
"""

import uuid

import pytest

import harness


def _marker(distro):
    slug = distro["id"].replace(".", "_").replace("-", "_")
    return f"HYPERI_HARNESS_MARKER_{slug}_{uuid.uuid4().hex[:8]}"


@pytest.mark.parametrize("distro", harness.DISTROS, ids=lambda d: d["id"])
def test_audit_forwarding(distro, receiver):
    if distro.get("platform") == "linux/amd64" and harness.HOST_IS_ARM:
        pytest.skip(
            f"{distro['id']} is amd64-only; host is arm64 ({harness.HOST_ARCH}) "
            f"- runs natively on an x64 host"
        )

    marker = _marker(distro)
    try:
        harness.bake(distro)
        name = harness.start_uut(distro)
        harness.converge(distro)

        # config landed: rules file + rsyslog forwarder pointing at the collector
        rules = harness.exec_in(name, "cat /etc/audit/rules.d/hyperi-audit.rules")
        assert rules.returncode == 0 and rules.stdout.strip(), (
            "audit rules file was not deployed"
        )
        fwd = harness.exec_in(name, "cat /etc/rsyslog.d/99-hyperi-rsyslog.conf")
        assert harness.COLLECTOR_ADDRESS in fwd.stdout and "12201" in fwd.stdout, (
            f"rsyslog forwarder not configured for the collector:\n{fwd.stdout}"
        )

        # forwarding works: seed a unique marker, assert it reaches the receiver
        harness.ensure_audit_log(name)
        harness.start_rsyslog(name)
        harness.seed_marker(name, marker)
        assert harness.wait_for_marker(marker), (
            f"marker {marker} did not reach the receiver in time\n"
            f"--- last receiver log ---\n{harness.receiver_log()[-2000:]}"
        )
    finally:
        harness.teardown_uut(distro)
