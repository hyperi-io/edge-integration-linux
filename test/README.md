# HyperI Linux audit collector - Docker test harness

This is the container-based test regime for the audit collector role. It is a
**port of the old VM regime**: where that stood up one VM per distro and
snapshot/reset it between runs, this stands up a disposable **container** per
distro and throws it away. The one long-lived piece - the central syslog
collector - is a container that persists for the whole run, exactly like the
old collector VM.

## Test regime history

The test regime is versioned in its own right, because "which regime tested this
release" is a question you will be asked and the answer changed at 3.1.

| Regime | Releases tested | How it worked |
|---|---|---|
| **VM fleet** | up to 3.0 (2026-07-16) | One long-lived VM per distro (`<distro>-audit.test.hyperi.io`), snapshot and reset between runs, driven by hand from `deploy/ansible-deploy-test-*.sh` against per-distro `environments/hs-<distro>` inventories, forwarding to a collector VM. Retired 2026-07-17: the VMs, the deploy scripts and the per-distro inventories all went with it. |
| **Docker harness v1.0** | 3.1 (2026-07-17) | This directory. Same shape - disposable per-distro target, one persistent collector - with containers instead of VMs, driven by pytest, and no hosts to maintain. |

Why it was worth migrating: the VM fleet needed nine machines kept alive and
reset by hand, so in practice it ran rarely and drifted. The container regime
runs the whole current matrix in ~5 minutes on a laptop and in CI on every push.

What it cost: the VM regime *could* have generated real kernel audit events on a
real kernel. The container regime cannot (see below) - that capability was not
actually exercised, but the ceiling is lower now. Real-event testing needs a
privileged disposable VM, tracked separately.

### Harness changelog

    v1.3  2026-07-22  Plain RELP end to end (test_relp_forwarding.py): the
                      receiver gained an imrelp listener (20514), so
                      hyperi_audit_transport=relp is proven wire-to-wire - the
                      omrelp handshake, transfer and delivery - against a stock
                      RELP receiver, one distro per family.
    v1.2  2026-07-22  Encrypted-transport config validity (test_tls_forwarding.py):
                      with hyperi_audit_transport=syslog-tls / relp-tls the role
                      installs the matching driver (rsyslog-gnutls / rsyslog-relp)
                      and rsyslogd -N1 accepts the generated omfwd+gtls / omrelp
                      action, proven on one distro per family. The TLS handshake
                      over the wire is NOT exercised (see below).
    v1.1  2026-07-17  Profile-selection tests (test_profiles.py): the role must
                      deploy the ruleset it was ASKED for (low/medium/high +
                      the internet profile), byte-compared against the role's
                      own source file. Until this, only `medium` was ever
                      converged and the deployed file was only checked for
                      being non-empty.
                      pyproject testpaths widened from a single named file to
                      "." - a hardcoded testpaths silently never collects any
                      test added later.
    v1.0  2026-07-17  Initial port from the VM regime. Nine current distros
                      green; EOL bucket best-effort; el6 amd64-only and
                      host-adaptive.

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

Separately, [`test_profiles.py`](test_profiles.py) asserts the role deploys the
ruleset it was **asked** for - low/medium/high plus the `internet` profile - by
byte-comparing the deployed file against the role's own source. One
representative distro: profile selection is ansible-side variable logic and is
identical on every target.

Also separately, [`test_tls_forwarding.py`](test_tls_forwarding.py) proves the
TLS-transport machinery for both TLS transports: with
`hyperi_audit_transport: syslog-tls` the role installs `rsyslog-gnutls` and
`rsyslogd -N1` loads the gtls driver and accepts the `omfwd` + `gtls` action;
with `relp-tls` it installs `rsyslog-relp` and -N1 loads the omrelp module and
accepts the `omrelp` action. Run on one distro per packaging family (deb + el)
where the drivers are in the standard repos. It proves the config is valid and
the driver present, not the wire handshake - see below.

[`test_relp_forwarding.py`](test_relp_forwarding.py) goes the whole way for
**plain RELP**: the receiver runs a stock `imrelp` listener, so
`hyperi_audit_transport: relp` is proven wire-to-wire - the omrelp handshake, the
transfer and delivery into the shared `received.log`. Plain RELP needs no certs
and no anon ciphers, and it forwards to any RELP receiver, so unlike the TLS
transports there is nothing blocking a real end-to-end run.

## What it deliberately does NOT test

Read this before trusting a green run. The gaps are real, and one of them hid a
production bug until a 2026-07 review.

**Real kernel audit-event generation.** The kernel audit subsystem is
host-global (`NETLINK_AUDIT` is not per-netns), so a container cannot truly load
rules or generate real syscall events. We **seed** `audit.log` instead, which
exercises the entire forwarding contract (the valuable part) without needing a
real kernel event. Consequences worth naming:

- **The rules are never loaded, so no rule is ever proven to FIRE.** A ruleset
  that auditctl would reject, or a detection masked by an exclude ordered above
  it, passes here. Exactly that bug existed from 2025-01 to 2026-07: the
  high-frequency excludes shadowed the `euid=0` root-exec detections and every
  run stayed green.
- **The service-management tail never runs** (the harness converges with
  `hyperi_audit_start_services: false`, because a plain container has no init to
  drive the service module). So the auditd enable/stop/start path - including the
  immutable-config handling - is untested here. That is where the 2026-07
  "restart skipped on every deploy after the first" bug lived.
- **auditd itself is never started**, so nothing proves `auditd.conf` is even
  parseable by the daemon, let alone that an unknown keyword is not fatal.

**The TLS wire handshake.** Plain RELP is proven end to end (above), but the
**TLS** transports (`syslog-tls`, `relp-tls`) stop at config validity. A real TLS
handshake needs certificate material on both ends (and, for the `anon` path,
anon-DH ciphers that modern crypto policies disable - so a green container result
would prove less than it looks). Like real rule loading, that is a real-host
verification item. What the harness proves for the TLS transports is: the driver
installs, and the daemon accepts the config.

**RELP to a HyperI receiver.** The plain-RELP e2e uses a stock `imrelp` receiver.
HyperI's own receivers do not ingest RELP yet (the Edge Stream Hub and
dfe-receiver RELP listeners are a future release, tracked by issue #2 and
dfe-receiver#44), so there is no e2e test against them until they land.

None of this is fixable in a container; it needs a privileged disposable VM.
Until that exists, a green run means "the config is written correctly and
forwards", not "the auditing works".

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
converge is fast config-only. Docker layer cache makes re-bakes near-instant.

**Not wired up:** pushing the bake images to Harbor
(`<your-registry>`) and fronting the upstream bases with a
pull-through cache is a possible future optimisation. CI does neither today -
there is no Harbor login or cache step in the workflow.

## Layout

```
test/
  matrix.yml            # distro+version cases
  receiver/             # central receiver image (rsyslog on debian trixie; imtcp + imrelp)
  images/               # per-family bake Dockerfiles (deb / el / suse)
  converge.yml          # applies the role in config-only mode
  ansible.cfg           # roles_path + community.docker connection
  harness.py            # docker/ansible helpers
  conftest.py           # session network + receiver fixtures; eol marker
  test_forwarding.py    # the parametrized e2e (config + forwarding, per distro)
  test_profiles.py      # the role deploys the profile it was asked for
  test_tls_forwarding.py # syslog-tls / relp-tls config validity (driver + rsyslogd -N1)
  test_relp_forwarding.py # plain RELP e2e (omrelp -> imrelp, marker delivered)
  run.sh                # portable entrypoint
```

CI runs the current matrix as a required job and the EOL bucket as a
best-effort job - see [`.github/workflows/test-harness.yml`](../.github/workflows/test-harness.yml).
