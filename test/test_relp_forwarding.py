"""
Plain RELP end-to-end: the role's omrelp forwarder delivers a seeded audit.log
marker to a standard rsyslog imrelp receiver.

This is the RELP analogue of test_forwarding.py's plaintext-TCP proof, and it goes
further than test_tls_forwarding.py's config-validity check. Plain RELP needs no
certificates and no anon ciphers, and it forwards to ANY RELP receiver - so the
harness receiver runs a stock imrelp listener and this exercises the full RELP
path end to end: the omrelp handshake, the transfer, and delivery into the shared
received.log. (The TLS transports stop at config validity because their wire
handshake is a real-host item; plain RELP does not have that limitation.)

One representative distro per packaging family where rsyslog-relp is in the
standard repositories.
"""

import uuid

import pytest

import harness

_RELP_DISTRO_IDS = {"debian-13", "ubuntu-24.04", "rocky-9"}
_RELP_DISTROS = [d for d in harness.DISTROS if d["id"] in _RELP_DISTRO_IDS]

RELP_PORT = "20514"


def _marker(distro):
    slug = distro["id"].replace(".", "_").replace("-", "_")
    return f"HYPERI_HARNESS_RELP_{slug}_{uuid.uuid4().hex[:8]}"


@pytest.mark.parametrize("distro", _RELP_DISTROS, ids=lambda d: d["id"])
def test_relp_forwarding(distro, receiver):
    if distro.get("platform") == "linux/amd64" and harness.HOST_IS_ARM:
        pytest.skip(
            f"{distro['id']} is amd64-only; host is arm64 ({harness.HOST_ARCH})"
        )

    marker = _marker(distro)
    try:
        harness.bake(distro)
        name = harness.start_uut(distro)
        harness.converge(
            distro,
            extra_vars={
                "hyperi_audit_transport": "relp",
                "hyperi_audit_port_audit": RELP_PORT,
                "hyperi_audit_port_syslog": RELP_PORT,
            },
        )

        # config landed: an omrelp action to the RELP port, and NOT a TLS one
        cfg = harness.exec_in(name, "cat /etc/rsyslog.d/99-hyperi-rsyslog.conf")
        assert 'type="omrelp"' in cfg.stdout, (
            f"relp transport did not emit an omrelp action:\n{cfg.stdout}"
        )
        assert 'tls="on"' not in cfg.stdout, (
            f"plain relp must not enable TLS:\n{cfg.stdout}"
        )
        assert f'port="{RELP_PORT}"' in cfg.stdout, (
            f"omrelp not targeting the RELP port:\n{cfg.stdout}"
        )

        # forwarding works: seed a marker and assert it reaches the receiver over
        # RELP. rsyslog-relp installed during converge, so omrelp loads here.
        harness.ensure_audit_log(name)
        harness.start_rsyslog(name)

        rc, cfg_check = harness.rsyslog_config_check(name)
        lowered = cfg_check.lower()
        problems = ["error", "could not load", "not found"]
        assert not any(p in lowered for p in problems), (
            f"rsyslogd -N1 rejected the relp config (rc={rc}):\n{cfg_check}"
        )

        harness.seed_marker(name, marker)
        assert harness.wait_for_marker(marker), (
            f"marker {marker} did not reach the receiver over RELP in time\n"
            f"--- last receiver log ---\n{harness.receiver_log()[-2000:]}"
        )

        # exactly once: the audit stream is bound to its own ruleset, so it must
        # not also arrive via the general catch-all.
        received = harness.receiver_log()
        count = received.count(marker)
        assert count == 1, (
            f"marker {marker} arrived {count} times over RELP, expected exactly 1\n"
            f"--- last receiver log ---\n{received[-2000:]}"
        )
    finally:
        harness.teardown_uut(distro)
