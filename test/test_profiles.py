"""Role inputs: which ruleset layers deploy, and which inputs fail the run.

Each case names keys the deployed ruleset must and must not carry. A key belongs
to one layer or overlay, so a wrong selection shows up as a missing or extra key.
"""

from collections.abc import Mapping

import pytest

import harness

# (extra vars, keys that must appear, keys that must not)
SELECTIONS = [
    (
        {"hyperi_audit_level": "low"},
        ["T1059_root_tmp", "T1611_shocker", "T1548.001_setuid_set", "T1556_pam"],
        ["T1071_connect4", "T1068_chroot", "T1548.001_priv_ctx_exec"],
    ),
    (
        {"hyperi_audit_level": "medium"},
        ["T1071_connect4", "T1222_perm_mod", "T1068_chroot", "T1542.003_boot"],
        ["T1011_socket", "T1059_session_exec", "T1505.003_webshell"],
    ),
    (
        {"hyperi_audit_level": "high"},
        ["T1011_socket", "T1059_exclude", "T1059_session_exec"],
        ["T1505.003_webshell", "T1611_runtime_ignore"],
    ),
    (
        {"hyperi_audit_level": "medium", "hyperi_audit_use_cases": ["edge"]},
        ["T1556_pam"],
        ["T1071_connect4", "T1011_socket"],
    ),
    (
        {"hyperi_audit_level": "medium", "hyperi_audit_use_cases": ["webserver"]},
        ["T1505.003_webshell", "T1071_webserver_ignore", "T1071_connect4"],
        [],
    ),
    (
        {"hyperi_audit_level": "low", "hyperi_audit_use_cases": ["container-host"]},
        ["T1611_runtime_ignore"],
        ["T1611_namespace"],
    ),
    (
        {"hyperi_audit_profile_override": "internet"},
        ["Level medium, overlays: edge, webserver", "T1505.003_webshell"],
        ["T1071_connect4"],
    ),
]

# (extra vars, a fragment of the message the run must fail with)
INVALID = [
    ({"hyperi_audit_level": "extreme"}, "hyperi_audit_level must be one of"),
    ({"hyperi_audit_level": ""}, "hyperi_audit_level must be one of"),
    (
        {"hyperi_audit_profile_override": "lowest"},
        "hyperi_audit_profile_override must be one of",
    ),
    (
        {"hyperi_audit_use_cases": ["database"]},
        "hyperi_audit_use_cases must be a list of",
    ),
    ({"hyperi_audit_transport": "udp"}, "hyperi_audit_transport must be one of"),
    (
        {"hyperi_audit_transport": "syslog-tls", "hyperi_audit_tls_mode": "none"},
        "hyperi_audit_tls_mode must be one of",
    ),
    (
        {"hyperi_audit_transport": "relp-tls", "hyperi_audit_tls_mode": "server"},
        "relp-tls does not support tls_mode=server",
    ),
    (
        {"hyperi_audit_transport": "syslog-tls", "hyperi_audit_tls_mode": "server"},
        "hyperi_audit_tls_ca_file must be set",
    ),
    (
        {
            "hyperi_audit_transport": "syslog-tls",
            "hyperi_audit_tls_mode": "mutual",
            "hyperi_audit_tls_ca_file": "/etc/pki/ca.pem",
            "hyperi_audit_tls_client_cert": "/etc/pki/client.pem",
        },
        "must both be set for tls_mode=mutual",
    ),
    (
        {
            "hyperi_audit_transport": "syslog-tls",
            "hyperi_audit_tls_mode": "server",
            "hyperi_audit_tls_ca_file": "relative/ca.pem",
        },
        "must be an absolute path",
    ),
    (
        {
            "hyperi_audit_transport": "syslog-tls",
            "hyperi_audit_tls_mode": "server",
            "hyperi_audit_tls_ca_file": "/etc/pki/ca.pem",
            "hyperi_audit_receiver_address": "203.0.113.9",
        },
        "hyperi_audit_tls_permitted_peer must be set",
    ),
    ({"hyperi_audit_port_audit": "0"}, "must be a TCP port"),
    ({"hyperi_audit_port_syslog": "70000"}, "must be a TCP port"),
    ({"hyperi_audit_port_syslog": "12205x"}, "must be a TCP port"),
    ({"hyperi_audit_receiver_address": "a,b"}, "must be a host name or IP address"),
    (
        {"hyperi_audit_receiver_address": "collector.example:6514"},
        "must be a host name or IP address",
    ),
    ({"hyperi_audit_receiver_address": "-r.example"}, "must be a host name or IP"),
    ({"hyperi_audit_user_watch_max": "-1"}, "must be a whole number"),
    ({"hyperi_audit_receiver_address": ""}, "receiver address is not set"),
]


def _id(extra_vars: Mapping[str, object]) -> str:
    return "-".join(
        f"{k.removeprefix('hyperi_audit_')}={v}" for k, v in extra_vars.items()
    )


@pytest.mark.parametrize(
    ("extra_vars", "present", "absent"),
    SELECTIONS,
    ids=[_id(ev) for ev, _, _ in SELECTIONS],
)
def test_selected_layers_are_deployed(
    extra_vars: dict[str, object],
    present: list[str],
    absent: list[str],
    representative: tuple[Mapping, str],
) -> None:
    distro, name = representative
    harness.converge(distro, extra_vars=extra_vars)
    rules = harness.read_file(name, harness.RULES_PATH)
    missing = [k for k in present if k not in rules]
    extra = [k for k in absent if f"-k {k}" in rules]
    assert not missing, f"{extra_vars}: missing {missing}"
    assert not extra, f"{extra_vars}: unexpected {extra}"


def test_legacy_variable_still_names_the_receiver(
    representative: tuple[Mapping, str],
) -> None:
    distro, name = representative
    harness.converge(distro, extra_vars={"collector_address": "legacy-receiver"})
    assert "legacy-receiver" in harness.read_file(name, harness.FORWARDER_PATH)


@pytest.mark.parametrize(
    ("extra_vars", "message"), INVALID, ids=[_id(ev) for ev, _ in INVALID]
)
def test_invalid_input_fails_the_run(
    extra_vars: dict[str, object],
    message: str,
    representative: tuple[Mapping, str],
) -> None:
    distro, _ = representative
    result = harness.converge(distro, extra_vars=extra_vars, check=False)
    assert result.returncode != 0, f"run with {extra_vars} succeeded"
    assert message in result.stdout, result.stdout[-3000:]
