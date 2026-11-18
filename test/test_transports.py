"""The opt-in transports on one distro per packaging family.

Every case checks the role installs the driver package and emits an action
`rsyslogd -N1` accepts. Plain RELP also delivers end to end through the
receiver's stock imrelp listener. The TLS cases stop at config validity: a
handshake needs certificates on both ends, and anon-DH ciphers that current
crypto policies disable.
"""

from collections.abc import Mapping

import pytest

import harness

_FAMILY_IDS = ("debian-13", "ubuntu-24.04", "rocky-9")
_DISTROS = [d for d in harness.DISTROS if d["id"] in _FAMILY_IDS]

# transport, port, strings the forwarder must contain, strings it must not,
# and whether a marker is delivered end to end.
_CASES = [
    ("relp", "20514", ['type="omrelp"', 'port="20514"'], ['tls="on"'], True),
    ("relp-tls", "20514", ['type="omrelp"', 'tls="on"'], [], False),
    (
        "syslog-tls",
        "6514",
        ['StreamDriver="gtls"', 'port="6514"', 'StreamDriverAuthMode="anon"'],
        [":6514"],
        False,
    ),
]


@pytest.mark.parametrize(
    ("distro", "transport", "port", "present", "absent", "deliver"),
    [(d, *case) for d in _DISTROS for case in _CASES],
    ids=[f"{d['id']}-{case[0]}" for d in _DISTROS for case in _CASES],
)
def test_transport(
    distro: Mapping,
    transport: str,
    port: str,
    present: list[str],
    absent: list[str],
    deliver: bool,
    receiver: str,
) -> None:
    harness.skip_if_foreign_arch(distro)
    try:
        harness.bake(distro)
        name = harness.start_uut(distro)
        harness.converge(
            distro,
            extra_vars={
                "hyperi_audit_transport": transport,
                "hyperi_audit_tls_mode": "anon",
                "hyperi_audit_port_audit": port,
                "hyperi_audit_port_syslog": port,
            },
        )

        forwarder = harness.read_file(name, harness.FORWARDER_PATH)
        for text in present:
            assert text in forwarder, f"{transport}: missing {text}:\n{forwarder}"
        for text in absent:
            assert text not in forwarder, f"{transport}: has {text}:\n{forwarder}"

        harness.ensure_audit_log(name)
        harness.assert_rsyslog_config_valid(name)
        if deliver:
            marker = harness.marker(distro, kind=transport.upper().replace("-", "_"))
            harness.start_rsyslog(name)
            harness.seed_marker(name, marker)
            harness.assert_delivered_once(marker)
    finally:
        harness.teardown_uut(distro)
