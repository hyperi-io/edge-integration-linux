# Supported distributions

## Why we support end-of-life distros

The most vulnerable systems are usually the ones that most need urgent auditing.
End-of-life (EOL) Linux boxes are exactly that - unpatched, long-lived, and
high-risk - so audit collection on them is a deliberate product feature, not
legacy debt. This integration intentionally reaches back to old releases for
that reason.

## The forwarding design (why it survives across distros)

The pipeline is deliberately `auditd -> syslog -> rsyslog forward`, NOT
`audisp-remote`. audisp was too fragmented across the distro range (separate
`audispd` daemon + `/etc/audisp/plugins.d` in audit 2.x on RHEL/CentOS 5/6/7,
merged into `auditd` + `/etc/audit/plugins.d` in audit 3.x). `rsyslog` is the
one constant present and stable across every target, so audit events are put
into a file (`/var/log/audit/audit.log`), read via rsyslog `imfile`, and
forwarded to the central collector - which is a **syslog receiver** and consumes
syslog-shaped lines, not native audisp records.

## Frozen packages rule

For any distro that is deliberately pinned to a known-old release, the pinned
packages are **frozen** - never upgrade, dedup, or "fix" them (e.g.
`rhel5-ansible-prep/` python2.6 RPMs, `ansible-versioned/` version pins, old
crypto). Newer versions do not exist / will not install / will not run on those
releases; upgrading breaks every collector on that distro. "The floor may move"
(below) is a separate, deliberate decision and does NOT license upgrading the
pins of a still-supported distro.

## Supported floor

**Automatable floor: CentOS/RHEL 6.** The floor is the oldest release that both
(i) has a usable, safe container image and (ii) can be driven hands-off.

This table is the prose view of [`../test/matrix.yml`](../test/matrix.yml), which
is the SSoT - if they disagree, matrix.yml is right and this table is stale.
Only OSS / non-licensed images are used: **no RHEL, SLES, Ubuntu Pro, ESM or
TuxCare** (matrix.yml states that policy directly).

| Release | Status | Image basis |
|---------|--------|-------------|
| RHEL/CentOS 5 | DROPPED from the automated regime (2026-07) | none safe/maintained; frozen vault only. Manual `rhel5-ansible-prep/` path only |
| RHEL/CentOS 6 | EOL bucket, best-effort. **amd64-only** | `oraclelinux:6` - skipped on an arm64 host, runs native on x64 |
| RHEL/CentOS 7 | EOL bucket, best-effort | `oraclelinux:7` |
| Ubuntu 18.04 / 20.04 | EOL bucket, best-effort | `ubuntu:18.04` / `ubuntu:20.04` |
| Ubuntu 24.04 / 26.04 | Supported (current) | `ubuntu:24.04` / `ubuntu:26.04` |
| Debian 12 / 13 | Supported (current) | `debian:12` / `debian:13` |
| Rocky 9 / 10 | Supported (current) | `rockylinux:9` / `rockylinux/rockylinux:10` |
| AlmaLinux 9 | Supported (current) | `almalinux:9` |
| Amazon Linux 2023 | Supported (current) | `amazonlinux:2023` |
| openSUSE Leap 15.6 | Supported (current) | `opensuse/leap:15.6` (needs `python3.11`; the stock `python3` is 3.6, too old for ansible-core) |

**Known gaps in the automated matrix** (not statements of product non-support):

- **el8 (Alma/Rocky 8) has no matrix entry.** An earlier version of this table
  claimed "AlmaLinux/Rocky 8/9"; nothing tests el8. Add it or say so plainly.
- **The EOL bucket is not green.** el7/ubuntu-18.04/ubuntu-20.04 do not converge
  (their `python3` predates ansible-core's floor - see the plan's P2), and EOL
  Ubuntu bakes need apt pointed at `old-releases.ubuntu.com`, which
  [`../test/images/Dockerfile.deb`](../test/images/Dockerfile.deb) claims is
  "handled by the build helper" -- **no such helper exists in this repo.** CI
  runs that bucket with `continue-on-error: true`, so it can fail silently.

### RHEL/CentOS 5 dropped (2026-07)

Dropped from the automated test regime for two independent reasons:

1. **Never reliably automatable** - even on VMs it needed heavy manual
   remediation (hand-built python2.6 RPMs, `ansible==2.3` venv, per-host SSH
   `KexAlgorithms=diffie-hellman-group1-sha1`). An automated regime cannot
   include a target that needs bespoke manual prep to become driveable.
2. **No safe or maintained container image** (EOL 2017-03-31) - TuxCare's floor
   is CentOS 6, there is no `ubi5` or maintained `oraclelinux:5`; only frozen,
   unpatched `centos:5.11` vault images remain.

Dropping el5 from the *automated regime* is not the same as dropping el5
*product support*: if a customer still runs el5, the existing manual
`rhel5-ansible-prep/` path can remain as documented, out-of-band, best-effort
legacy support - a product-support call, kept explicitly outside the automated
test harness. The `rhel5-ansible-prep/` material stays in the repo for that.

## Test regime

The per-distro test regime has been ported from a fleet of VMs (one VM per
distro, snapshot/reset between runs) to a **Docker harness** in
[`../test/`](../test/) - a pytest orchestrator with one persistent syslog
receiver and disposable per-distro containers, run one at a time. It converges
the role config-only, seeds a marker into `audit.log`, and asserts it forwards
to the receiver on TCP 12201.

Kernel audit-event generation is host-global (`NETLINK_AUDIT` is not per-netns),
so a container cannot load rules or generate real events - the harness **seeds**
`audit.log`, which exercises the whole forwarding contract without a real kernel
event. No Proxmox/VM tail is required: to cover el6/el7 natively, run the same
harness on an **x64 host** (a plain Ubuntu box, or the CI runner); on an arm64
host the arm64-native subset runs and amd64-only targets (el6) skip - "make
Docker work where it can". Only OSS / non-licensed images are used (Rocky/Alma/
Oracle Linux, openSUSE Leap, Ubuntu, Debian, Amazon Linux). See
[`../test/README.md`](../test/README.md) for the full design.
