"""Plain TCP forwarding on every distro in the matrix.

The role converges, the rsyslog config parses, and a seeded audit.log marker
reaches the receiver exactly once. Distros run one at a time, so the shared
receiver log stays unambiguous.
"""

from collections.abc import Mapping

import pytest

import harness


@pytest.mark.parametrize("distro", harness.DISTROS, ids=lambda d: d["id"])
def test_audit_forwarding(distro: Mapping, receiver: str) -> None:
    harness.skip_if_foreign_arch(distro)
    marker = harness.marker(distro)
    try:
        harness.bake(distro)
        name = harness.start_uut(distro)
        harness.converge(distro)

        rules = harness.read_file(name, harness.RULES_PATH)
        assert "Level medium, overlays: none." in rules
        assert rules.rstrip().endswith("-e 2")
        forwarder = harness.read_file(name, harness.FORWARDER_PATH)
        assert harness.RECEIVER_ADDRESS in forwarder
        assert 'port="12201"' in forwarder or ":12201" in forwarder

        harness.ensure_audit_log(name)
        harness.start_rsyslog(name)
        harness.assert_rsyslog_config_valid(name)
        harness.seed_marker(name, marker)
        harness.assert_delivered_once(marker)
    finally:
        harness.teardown_uut(distro)
