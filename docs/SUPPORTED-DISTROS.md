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

| Release | Status | Image basis |
|---------|--------|-------------|
| RHEL/CentOS 5 | DROPPED from the automated regime (2026-07) | none safe/maintained; frozen vault only |
| RHEL/CentOS 6 | Supported (floor) | `oraclelinux:6` (free, patched); TuxCare ELS optional; frozen `centos:6`+vault fallback |
| RHEL/CentOS 7 | Supported | `oraclelinux:7`; UBI7; frozen `centos:7`+vault |
| Ubuntu 16.04/18.04/20.04 | Supported | Ubuntu Pro ESM (build-time attach) |
| AlmaLinux/Rocky 8/9, current Ubuntu | Supported (current) | official images |

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

The per-distro test regime is being modernised from a fleet of VMs to a
Docker-based harness (Molecule + init-enabled per-distro containers -> a shared
rsyslog sidecar receiver; seed a synthetic `audit.log` and assert forwarding).
Kernel audit event generation is host-global (`NETLINK_AUDIT` is per-netns), so
live `auditd` start + SELinux policy build run as a thin, serialised job on one
privileged host; config + forwarding - the bulk of the value - run in
containers. See the design note for the full architecture and image sourcing.
