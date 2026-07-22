"""
Encrypted-transport config validity on real distros - syslog-tls and relp-tls.

Proves the transport machinery the role adds: with hyperi_audit_transport set to
syslog-tls or relp-tls the role installs the matching driver package
(rsyslog-gnutls / rsyslog-relp), and the generated action is a config the rsyslog
daemon accepts - `rsyslogd -N1` loads the stream driver (gtls) or the omrelp
module and parses the action without error. If the package were missing or the
action malformed, -N1 would fail here.

What these do NOT do is complete a TLS session over the wire:

- syslog-tls: a real handshake needs certificate infrastructure on both ends
  and, for the anonymous path, anon-DH ciphers that modern crypto policies
  disable - so a green container result would prove less than it appears.
- relp-tls: there is no RELP receiver to forward to yet (the Edge Stream Hub and
  dfe-receiver RELP listeners are a future release), so end-to-end RELP is not
  runnable here at all.

Both wire paths are real-host / future-receiver items, in the same bucket as
loading real audit rules (see README.md). Here we prove the config the role
emits is valid and the driver is present.
"""

import pytest

import harness

# One representative distro per packaging family where rsyslog-gnutls is in the
# standard repositories. The anon config path itself is family-agnostic; what
# varies is that the driver package installs cleanly.
_TLS_DISTRO_IDS = {"debian-13", "ubuntu-24.04", "rocky-9"}
_TLS_DISTROS = [d for d in harness.DISTROS if d["id"] in _TLS_DISTRO_IDS]


@pytest.mark.parametrize("distro", _TLS_DISTROS, ids=lambda d: d["id"])
def test_syslog_tls_config_valid(distro, receiver):
    if distro.get("platform") == "linux/amd64" and harness.HOST_IS_ARM:
        pytest.skip(
            f"{distro['id']} is amd64-only; host is arm64 ({harness.HOST_ARCH})"
        )

    try:
        harness.bake(distro)
        name = harness.start_uut(distro)
        harness.converge(
            distro,
            extra_vars={
                "hyperi_audit_transport": "syslog-tls",
                "hyperi_audit_tls_mode": "anon",
                "hyperi_audit_port_audit": "6514",
                "hyperi_audit_port_syslog": "6514",
            },
        )

        # the TLS transport is actually in the emitted config
        cfg = harness.exec_in(name, "cat /etc/rsyslog.d/99-hyperi-rsyslog.conf")
        assert 'StreamDriver="gtls"' in cfg.stdout, (
            f"syslog-tls did not emit the gtls driver:\n{cfg.stdout}"
        )
        assert ':6514' not in cfg.stdout  # port is an attribute, not host:port
        assert 'port="6514"' in cfg.stdout, (
            f"forward port not set to the TLS port:\n{cfg.stdout}"
        )

        # the daemon accepts it: rsyslogd -N1 loads the gtls stream driver (proving
        # rsyslog-gnutls installed) and parses the action. A missing driver or a
        # malformed action surfaces as an error here, where the string check above
        # would pass straight over it.
        harness.ensure_audit_log(name)
        rc, cfg_check = harness.rsyslog_config_check(name)
        lowered = cfg_check.lower()
        problems = ["error", "could not load", "not found"]
        assert not any(p in lowered for p in problems), (
            f"rsyslogd -N1 rejected the syslog-tls config (rc={rc}):\n{cfg_check}"
        )
    finally:
        harness.teardown_uut(distro)


@pytest.mark.parametrize("distro", _TLS_DISTROS, ids=lambda d: d["id"])
def test_relp_tls_config_valid(distro, receiver):
    if distro.get("platform") == "linux/amd64" and harness.HOST_IS_ARM:
        pytest.skip(
            f"{distro['id']} is amd64-only; host is arm64 ({harness.HOST_ARCH})"
        )

    try:
        harness.bake(distro)
        name = harness.start_uut(distro)
        harness.converge(
            distro,
            extra_vars={
                "hyperi_audit_transport": "relp-tls",
                "hyperi_audit_tls_mode": "anon",
                "hyperi_audit_port_audit": "20514",
                "hyperi_audit_port_syslog": "20514",
            },
        )

        # the RELP transport is actually in the emitted config
        cfg = harness.exec_in(name, "cat /etc/rsyslog.d/99-hyperi-rsyslog.conf")
        assert 'type="omrelp"' in cfg.stdout, (
            f"relp-tls did not emit an omrelp action:\n{cfg.stdout}"
        )
        assert 'tls="on"' in cfg.stdout, (
            f"relp-tls did not enable tls:\n{cfg.stdout}"
        )

        # the daemon accepts it: rsyslogd -N1 loads the omrelp module (proving
        # rsyslog-relp installed) and parses the action. There is no receiver to
        # forward to yet, but -N1 does not connect - it validates the config.
        harness.ensure_audit_log(name)
        rc, cfg_check = harness.rsyslog_config_check(name)
        lowered = cfg_check.lower()
        problems = ["error", "could not load", "not found"]
        assert not any(p in lowered for p in problems), (
            f"rsyslogd -N1 rejected the relp-tls config (rc={rc}):\n{cfg_check}"
        )
    finally:
        harness.teardown_uut(distro)
