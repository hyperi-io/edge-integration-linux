"""The committed reference rulesets in rules/: current, and each level a superset.

Each heavier level must hold every rule of the lighter one, so a rule added to
low reaches medium and high mechanically. SUPERSEDED names the few lower-level
rules a heavier level replaces with a broader one.
"""

from pathlib import Path

import pytest

import harness

RULES = harness.HERE.parent / "rules"
PROFILES = ("low", "medium", "high", "internet")


def _systemd_dir(path: str) -> str:
    return f"-a always,exit -F arch=b64 -F perm=wa -F dir={path} -k T1543.002_systemd"


def _ptrace(a0: str = "") -> str:
    request = f" -F a0={a0}" if a0 else ""
    return f"-a always,exit -F arch=b64 -S ptrace{request} -k T1055.008_ptrace"


# lighter-level rule -> the heavier-level rule that covers it (None: dropped).
SUPERSEDED = {
    # low drops CWD records to save volume. medium and up keep them.
    "-a always,exclude -F msgtype=CWD": None,
    # low watches the unit and generator dirs, medium their parents.
    _systemd_dir("/etc/systemd/system"): _systemd_dir("/etc/systemd"),
    _systemd_dir("/etc/systemd/system-generators"): _systemd_dir("/etc/systemd"),
    _systemd_dir("/usr/lib/systemd/system"): _systemd_dir("/usr/lib/systemd"),
    _systemd_dir("/usr/local/lib/systemd/system-generators"): _systemd_dir(
        "/usr/local/lib/systemd"
    ),
    # low logs the three ptrace write requests, medium every ptrace.
    _ptrace("0x4"): _ptrace(),
    _ptrace("0x5"): _ptrace(),
    _ptrace("0x6"): _ptrace(),
}


def rule_lines(text: str) -> list[str]:
    """Return the rule and control lines, comments and blanks dropped."""
    return [x for x in text.splitlines() if x and not x.startswith("#")]


def committed(profile: str) -> str:
    """Return the committed reference ruleset for a profile."""
    return (RULES / f"hyperi-audit-{profile}.rules").read_text(encoding="utf-8")


def test_reference_files_are_current(tmp_path: Path) -> None:
    harness.run(
        [
            "ansible-playbook",
            "render_reference.yml",
            "-e",
            f"out_dir={tmp_path}",
        ],
        cwd=harness.HERE,
        env=harness.ansible_env(),
    )
    stale = [
        p
        for p in PROFILES
        if (tmp_path / f"hyperi-audit-{p}.rules").read_text(encoding="utf-8")
        != committed(p)
    ]
    assert not stale, (
        f"rules/ is stale for {stale}: run "
        "`cd test && uv run ansible-playbook render_reference.yml` and commit"
    )


@pytest.mark.parametrize(
    ("lighter", "heavier"), [("low", "medium"), ("medium", "high")]
)
def test_heavier_level_holds_the_lighter_one(lighter: str, heavier: str) -> None:
    heavy = set(rule_lines(committed(heavier)))
    missing = []
    for line in rule_lines(committed(lighter)):
        if line in heavy or not line.startswith(("-a ", "-w ")):
            continue
        if line in SUPERSEDED and (
            SUPERSEDED[line] is None or SUPERSEDED[line] in heavy
        ):
            continue
        missing.append(line)
    assert not missing, f"{heavier} lacks these {lighter} rules:\n" + "\n".join(missing)


def test_internet_is_medium_with_its_overlays() -> None:
    internet = set(rule_lines(committed("internet")))
    dropped = [
        x
        for x in rule_lines(committed("medium"))
        if x not in internet and "-S connect" not in x
    ]
    assert not dropped, "internet lacks medium rules:\n" + "\n".join(dropped)


def test_every_rule_is_keyed() -> None:
    for profile in PROFILES:
        for line in rule_lines(committed(profile)):
            if line.startswith("-a always,exclude"):
                assert " -k " not in line, f"{profile}: exclude with a key: {line}"
            elif line.startswith(("-a ", "-w ")):
                assert " -k " in line or "key=" in line, f"{profile}: no key: {line}"


def test_files_end_locked() -> None:
    for profile in PROFILES:
        assert rule_lines(committed(profile))[-1] == "-e 2", profile
