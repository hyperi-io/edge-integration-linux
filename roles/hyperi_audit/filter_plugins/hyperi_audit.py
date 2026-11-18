"""Fit a rendered audit ruleset to the host it will load on."""

import re
from collections.abc import Callable, Mapping, Sequence

_SYSCALL = re.compile(r" -S (\S+)")
_EXEC_PATH = re.compile(r"(-w |-F path=)(\S+)")


def _is_exec_rule(line: str) -> bool:
    return " -p x" in line or "-F perm=x" in line


def fit_syscalls(
    text: str,
    tables: Mapping[str, Sequence[str]],
    links: Mapping[str, str] | None = None,
) -> str:
    """Drop the ``-S`` names the host lacks and point exec rules at real files.

    auditctl rejects a whole rule over one unknown syscall name. arm64 has no
    unlink, open or rename, only their *at forms, and older audit releases
    lack newer names. A rule left with no syscall becomes a comment. An exec
    watch on a symlink never fires, so its path becomes the link's target.

    Args:
        text: The rendered ruleset.
        tables: Syscall names per arch, keyed ``b64`` and ``b32``, from
            ``ausyscall --dump``. An empty or missing table leaves its rules
            as written.
        links: Exec-watched paths that are symlinks, mapped to their targets.

    Returns:
        The ruleset as auditctl on this host will load it.
    """
    out = []
    seen: set[str] = set()
    for line in text.splitlines():
        if line.startswith("-a ") and " -S " in line:
            arch = "b32" if "-F arch=b32" in line else "b64"
            known = set(tables.get(arch) or ())
            if known:
                missing = [s for s in _SYSCALL.findall(line) if s not in known]
                for name in missing:
                    line = re.sub(rf" -S {re.escape(name)}(?=\s|$)", "", line)
                if " -S " not in line:
                    line = f"## no such syscall here: {' '.join(missing)}"
        if links and _is_exec_rule(line):
            line = _EXEC_PATH.sub(
                lambda m: m.group(1) + links.get(m.group(2), m.group(2)), line
            )
            # Two links to one binary (insmod and rmmod to kmod) make the same
            # rule, which auditctl rejects as already loaded.
            rule = " ".join(line.split())
            if rule in seen:
                continue
            seen.add(rule)
        out.append(line)
    trailer = "\n" if text.endswith("\n") else ""
    return "\n".join(out) + trailer


def exec_paths(text: str) -> list[str]:
    """Return the paths the exec rules in a rendered ruleset watch.

    Args:
        text: The rendered ruleset.

    Returns:
        Each watched executable path once, in the order it first appears.
    """
    paths: dict[str, None] = {}
    for line in text.splitlines():
        if line.startswith(("-a ", "-w ")) and _is_exec_rule(line):
            for _, path in _EXEC_PATH.findall(line):
                paths[path] = None
    return list(paths)


def split_syscalls(text: str, portable: Sequence[str]) -> str:
    """Give each syscall a host may lack a rule line of its own.

    For a ruleset that has to load on any host: under ``-i`` auditctl then
    skips only the line naming a syscall that host lacks. Every rule line
    costs each syscall a mask check, so names every host knows stay together.

    Args:
        text: The rendered ruleset.
        portable: Syscall names every supported auditctl knows on every arch.

    Returns:
        The ruleset with each non-portable syscall on its own line.
    """
    keep = set(portable)
    out = []
    for line in text.splitlines():
        names = _SYSCALL.findall(line) if line.startswith("-a ") else []
        if len(names) < 2:
            out.append(line)
            continue
        head = line[: line.index(" -S ")]
        tail = _SYSCALL.sub("", line[len(head) :])
        common = [n for n in names if n in keep]
        if common:
            out.append(f"{head}{''.join(f' -S {n}' for n in common)}{tail}")
        out.extend(f"{head} -S {n}{tail}" for n in names if n not in keep)
    trailer = "\n" if text.endswith("\n") else ""
    return "\n".join(out) + trailer


class FilterModule:
    """Ansible filter plugin entry point."""

    def filters(self) -> dict[str, Callable[..., object]]:
        """Return the filters this plugin provides."""
        return {
            "hyperi_audit_fit_syscalls": fit_syscalls,
            "hyperi_audit_exec_paths": exec_paths,
            "hyperi_audit_split_syscalls": split_syscalls,
        }
