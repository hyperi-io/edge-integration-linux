# Contributing

Issues and pull requests are welcome at https://github.com/hyperi-io/edge-integration-linux. The last section of this file, [Context](#context), is how to work in the repo without breaking it, so read it before your first change.

## Reporting a problem

Open an issue with the distro and release of the host, the `rsyslogd -v` and `auditctl -v` versions, the variables you set, and the failing task's output. For a ruleset problem, add the key involved and what you ran to trigger it.

## Sending a change

1. Branch from `main`.
2. Run the lint and the harness ([commands](#commands-that-test-a-change)). For a ruleset change, run the kernel tests in a disposable VM too.
3. Write the commit subject as a Conventional Commit: `fix: ...` for a fix, `feat: ...` for a capability a user could not use before, `docs: ...` for docs.
4. Open a pull request against `main`. CI runs the lint, kernel and harness jobs on it.

A change to role behaviour updates the docs in the same pull request, and an entry under `[Unreleased]` in `CHANGELOG.md`.

## Context

### What this is

One Ansible role, `roles/hyperi_audit`, and the tests around it. It installs and configures auditd and rsyslog on Linux hosts, renders an audit ruleset per host from a Jinja template, and points rsyslog at a syslog receiver. It is not a receiver, not an audisp plugin and not an agent: nothing of it runs on the host once the play ends, and the receiver is someone else's software.

### Where things live

| Path | Holds |
|---|---|
| `site.yml` | The play: every host in the inventory gets the role. |
| `roles/hyperi_audit/defaults/main.yml` | Every public variable and its default. |
| `roles/hyperi_audit/vars/main.yml` | The directories the ruleset watches. |
| `roles/hyperi_audit/tasks/main.yml` | Task order: `validate`, `install`, `rsyslog`, `auditd`, `selinux`, `services`, which includes `restart`. |
| `roles/hyperi_audit/templates/hyperi-audit.rules.j2` | The ruleset. Its header explains lineage, layers, cost and order. |
| `roles/hyperi_audit/templates/99-hyperi-rsyslog.j2`, `99-hyperi-rsyslog-legacy.j2` | The forwarder, for rsyslog 7 and later and for older rsyslog. |
| `roles/hyperi_audit/files/rsyslog_read_audit_logs.te` | The SELinux policy that lets rsyslog read the audit log. |
| `environments/example` | The inventory template. |
| `test/` | The Docker harness, the kernel tests and `render.yml` ([test/README.md](test/README.md)). |
| `test/lab/` | Throwaway VMs with a kernel of their own, the syscall benchmark and the rule-order probes. |
| `build-tarball.sh` | Builds `edge-integration-linux-<git describe>.tar.gz` from `HEAD`. `.gitattributes` keeps development files out of it. |
| `.github/workflows/test-harness.yml` | CI: the lint, kernel and harness jobs. |

### Commands that test a change

Lint, the same tools as CI's lint job, from the repo root:

```sh
(cd test && uv sync --locked --group lint)
test/.venv/bin/ansible-lint
(cd test && .venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/ty check)
test/.venv/bin/shellcheck build-tarball.sh test/run.sh
test/.venv/bin/hadolint test/images/Dockerfile.* test/receiver/Dockerfile
test/.venv/bin/actionlint
```

The harness needs Docker and `uv`. It converges the role into a container per distro and checks a seeded audit line reaches a test receiver once:

```sh
test/run.sh -m 'not eol'
```

A passing harness says the config is written and forwards. It never loads a rule, because containers share the host's kernel audit, so it cannot tell you a rule loads or fires. The kernel tests do that, and they load and flush rules in the kernel they run on, so run them in a disposable VM only:

```sh
cd test && env HYPERI_AUDIT_KERNEL_TESTS=1 uv run --locked pytest -m kernel test_kernel.py
```

CI runs them on a GitHub-hosted runner. To read the ruleset a level renders on your machine, `cd test && ansible-playbook -i localhost, render.yml -K -e '{"out": "/tmp/medium.rules", "level": "medium"}'`.

### What tends to bite

| Don't | Do | Why |
|---|---|---|
| Add a syscall to an existing `-S` list | Give it a line to itself | An unknown syscall makes `auditctl` drop the whole rule, and `-i` hides it. |
| Rename or remove a key | Add a key and keep the old one | Keys are the output contract. Searches, alerts and SigmaHQ rules match them literally. |
| Put a `never` rule below the `always` rule it should silence | Put it above | The first matching rule in load order decides, file watches included. |
| Move the execution rules below the excludes | Keep them at the top | An exclude above them hides a root exec. |
| Scope a session exclude with `auid>=1000` alone | Add `auid!=unset` | Unset is 4294967295, which is over 1000, so the exclude would match every daemon. |
| Write a directory watch as `-w dir/` | Use the `wdir()` macro and add the path to `vars/main.yml` | `-w` costs every syscall, and the render fails on a path missing from that list. |
| Turn `-i` into an auditd version check | Leave `-i` first | It skips what the running kernel does not know, which a version check cannot see. |
| Add an `auditd.conf` value without a version gate | Gate it on `hyperi_audit_auditd_version` | An unknown value stops auditd starting. |
| Trust a passing harness for a ruleset change | Run `test_kernel.py` in a VM | No container loads a rule. |
| Run `test_kernel.py` on your workstation | Run it in a VM or let CI run it | It runs `auditctl -D` through `sudo` on the kernel under it. |

### Where this sits

- Outbound to EdgeStream Hub, HyperI's syslog receiver: the role sends to its syslog listeners, UDP, TCP and TLS, so a transport change here has to match what EdgeStream Hub accepts. RELP waits on EdgeStream Hub adding RELP ingest ([issue #2](https://github.com/hyperi-io/edge-integration-linux/issues/2)).
- Outbound to `hyperi-io/renovate-config`: `renovate.json` extends its preset, so its rules decide how harness dependencies get updated.
- Outbound to hyperi-ci's runner variables: the workflow reads `GH_RUNNER_MODE` and `HYPERCI_DOCKERHUB_MIRROR`, and runs on GitHub-hosted runners when they are unset.
- Inbound: deployments take the role from a clone or the release tarball, and no repo builds on it in code.
