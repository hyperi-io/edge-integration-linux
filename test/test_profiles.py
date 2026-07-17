"""
The role deploys the ruleset the caller ASKED for.

test_forwarding.py only ever converges the default (medium) profile and only
asserts the deployed rules file is non-empty -- so the multi-profile selection
this release restored (low / medium / high + the internet use-case overlay) had
no test at all, and a regression that always shipped `medium` would keep the
whole matrix green.

The assertion here is a byte comparison against the role's own source file. The
role deploys it with `copy`, verbatim, so anything short of an exact match means
the wrong profile was selected. That tests the SELECTION logic rather than
pattern-matching for strings that happen to appear in one file.

One representative current distro: profile selection is pure ansible-side
variable logic, identical on every target, so re-running it per distro would buy
nothing but wall-clock. Cross-distro coverage is test_forwarding.py's job.
"""

import pytest

import harness


def _representative():
    """First current (non-EOL) distro that runs natively on this host."""
    for d in harness.DISTROS:
        if d.get("eol"):
            continue
        if d.get("platform") == "linux/amd64" and harness.HOST_IS_ARM:
            continue
        return d
    pytest.skip("no current distro in the matrix runs natively on this host")


def _deployed_rules(name):
    got = harness.exec_in(name, "cat /etc/audit/rules.d/hyperi-audit.rules")
    assert got.returncode == 0, f"rules file not deployed:\n{got.stderr}"
    return got.stdout


# (level, use_case) -> the file we expect on disk. A use_case REPLACES the level.
PROFILES = [
    ("low", None),
    ("medium", None),
    ("high", None),
    ("medium", "internet"),
]


@pytest.mark.parametrize(
    "level,use_case", PROFILES, ids=lambda v: str(v) if v else "none"
)
def test_selected_profile_is_deployed(level, use_case, network):
    distro = _representative()
    expected = harness.rules_source(level=level, use_case=use_case).read_text()

    try:
        harness.bake(distro)
        name = harness.start_uut(distro)
        harness.converge(distro, level=level, use_case=use_case)
        assert _deployed_rules(name) == expected, (
            f"level={level} use_case={use_case} deployed the WRONG ruleset "
            f"(expected {harness.rules_source(level=level, use_case=use_case).name})"
        )
    finally:
        harness.teardown_uut(distro)


def test_profiles_are_distinguishable():
    """Guard the guard: the comparison above only means something while the four
    rulesets actually differ. If two ever became identical, a selection bug
    between them would pass unnoticed."""
    contents = {
        p.name: harness.rules_source(level=lvl, use_case=uc).read_text()
        for lvl, uc in PROFILES
        for p in [harness.rules_source(level=lvl, use_case=uc)]
    }
    assert len(set(contents.values())) == len(contents), (
        f"two profiles have identical content, so the selection test cannot "
        f"tell them apart: {sorted(contents)}"
    )
