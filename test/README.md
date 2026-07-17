# HyperI Linux audit collector - Docker test harness

This is the container-based test regime for the audit collector role. It is a
**port of the old VM regime**: where that stood up one VM per distro and
snapshot/reset it between runs, this stands up a disposable **container** per
distro and throws it away. The one long-lived piece - the central syslog
collector - is a container that persists for the whole run, exactly like the
old collector VM.

## What it proves

For every distro+version in [`matrix.yml`](matrix.yml), one at a time:

1. **bake** a small image (base + `python3` + `rsyslog` + `audit` pre-installed);
2. **converge** the role against it in config-only mode
   (`hyperi_audit_start_services: false` - the role writes `auditd.conf`, the rules
   file and the rsyslog forwarder but does not touch services);
3. assert the **config landed** (rules file deployed; the rsyslog drop-in points
   at the collector on TCP 12201);
4. start `rsyslogd`, **seed a unique marker** into `/var/log/audit/audit.log`,
   and assert that marker **reaches the central receiver** - i.e. the real
   `imfile -> omfwd` forwarding path works end to end;
5. tear the container down and move to the next distro.

The receiver is a **session fixture**: it comes up once, every distro forwards
into its shared `received.log`, and it stops at the end. Each distro seeds a
distro-unique marker so its assertion greps only its own lines.

## What it deliberately does NOT test

**Real kernel audit-event generation.** The kernel audit subsystem is
host-global (`NETLINK_AUDIT` is not per-netns), so a container cannot truly load
rules or generate real syscall events. We **seed** `audit.log` instead, which
exercises the entire forwarding contract (the valuable part) without needing a
real kernel event. Real-event generation would need a dedicated host per distro;
it is out of scope for the container harness.

## Host-adaptive (arm64 vs x64)

A container runs the **host's** kernel and needs a **matching-arch image**. el6
is amd64-only (it predates aarch64 in the RHEL family), and el6/el7 in the real
world are x86_64 anyway.

- On an **x64 host** (e.g. a plain Ubuntu box, or the CI runner) the **whole
  matrix** runs, el6/el7 included, natively.
- On an **arm64 host** (e.g. an Apple-silicon Mac) the arm64-native subset runs
  and amd64-only targets (el6) are **skipped** - "make Docker work where it can".
  The skip is logged; it also proves the host-adaptive path.

The role's version-gating is userspace-binary behaviour, so it is
arch-independent - the arm64 subset still exercises it.

## Quick start

Needs only `docker` and [`uv`](https://docs.astral.sh/uv/).

```sh
./run.sh                       # whole matrix
./run.sh -m 'not eol'          # current distros only (skip the EOL bucket)
./run.sh -k rocky              # a subset (pytest -k)
./run.sh 'test_forwarding.py::test_audit_forwarding[ubuntu-24.04]'   # one case
```

`run.sh` syncs the venv, installs the `community.docker` collection, and runs
pytest.

## The matrix

[`matrix.yml`](matrix.yml) lists each distro+version case (the pytest
parametrization unit). Only **OSS / non-licensed** images are used - Rocky /
Alma / Oracle Linux (not licensed RHEL), openSUSE Leap (not SLES), plain Ubuntu
and Debian, Amazon Linux. `family` (`el`/`deb`/`suse`) selects the bake
Dockerfile in [`images/`](images/); `platform` pins amd64-only targets so they
skip on arm64.

## Caching

The per-distro bake pre-installs the slow packages once, so the per-test
converge is fast config-only. Docker layer cache makes re-bakes near-instant. In
CI / on a shared host these bake images can be pushed to Harbor
(`harbor.devex.hyperi.io:8443`) and pulled, and Harbor can front the upstream
bases as a pull-through cache.

## Layout

```
test/
  matrix.yml            # distro+version cases
  receiver/             # central syslog receiver image (rsyslog on alpine)
  images/               # per-family bake Dockerfiles (deb / el / suse)
  converge.yml          # applies the role in config-only mode
  ansible.cfg           # roles_path + community.docker connection
  harness.py            # docker/ansible helpers
  conftest.py           # session network + receiver fixtures; eol marker
  test_forwarding.py    # the parametrized e2e
  run.sh                # portable entrypoint
```

CI runs the current matrix as a required job and the EOL bucket as a
best-effort job - see [`.github/workflows/test-harness.yml`](../.github/workflows/test-harness.yml).
