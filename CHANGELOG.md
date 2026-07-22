# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The upstream lineage and per-profile merge history live under `# HISTORY.` in the
headers of `roles/hyperi_audit/files/hyperi-audit-*.rules`. This file tracks the
project; those track the rules. Entries between 2.5.1 and 3.0.0 were rebuilt from
the merge order when the pre-git tracking was retired.

## [Unreleased]

### Added

- Optional transport (`hyperi_audit_transport`, default `tcp`): plain TCP stays
  the default and works with every receiver. `relp` adds reliable, acknowledged
  delivery (`omrelp`) to any RELP receiver; `syslog-tls` wraps the forwards in TLS
  (`omfwd` + the gtls driver); `relp-tls` does both. TLS trust is
  `hyperi_audit_tls_mode` (`anon`/`server`/`mutual`) plus CA/cert/key and
  overridable ports. Plain RELP is tested end to end against a stock `imrelp`
  receiver; the TLS transports are config-validity tested per packaging family.
  HyperI's own receivers gain RELP ingest in a future release (#2; dfe-receiver
  #44) - RELP reaches any standard RELP receiver today. See `docs/transport.md`.
- Docker test harness (`test/`): one persistent rsyslog receiver plus disposable
  per-distro containers. Converges the role config-only, seeds a marker into
  `audit.log`, asserts it forwards to the collector on TCP 12201. Nine current
  distros green; the EOL bucket is best-effort. Replaces the VM fleet.
- Profile-selection tests: the role must deploy the ruleset it was asked for
  (low/medium/high + the internet profile), byte-compared against the source.
- GitHub Actions workflow for the harness.

### Changed

- Role renamed `hsaudit` -> `hyperi_audit`; rules, templates, variables and
  deployed paths follow (`hyperi_audit_*`, `/etc/audit/rules.d/hyperi-audit.rules`,
  `/etc/rsyslog.d/99-hyperi-rsyslog.conf`). Pre-GA interface change.
- `hyperi_audit_start_services` gates the service tail so the harness can
  converge in a container with no init.
- Deploy tarball is built with `git archive` (tracked files only) instead of
  tar-from-".". Internal material can no longer reach a customer by omission.

### Fixed

- **Escalated execution was not being logged.** The high-frequency excludes match
  `auid>=1000` + path with no euid scoping and ran BEFORE the `euid=0` root-exec
  rules; auditd's exit filter is first-match-wins, so `sudo cat /tmp/x` hit the
  exclude and was never recorded. The 2.9.0 perf pass had been silently masking
  the detections it sat above. The detections now precede the excludes.
- **The auditd restart was skipped on every deploy after the first.** The
  immutable check grepped `/etc/audit/rules.d` for `-e 2` before writing our own
  ruleset there - and every ruleset we ship ends with `-e 2`, so it detected
  itself. auditd.conf tuning (priority_boost/flush/freq) therefore never reached
  any host that had already run the role. The restart is no longer gated on
  immutability: it only blocks the kernel-side rules, not daemon config.
- `RefuseManualStop` was left disabled when `hyperi_audit_start_services=false`.
- `environments/example` did not parse (a value ended in a colon; five host keys
  were identical), so the shipped inventory template was unusable.
- Deploy tarball build always exited 1 (tar archived "." while writing into it).
- `ansible_passowrd` typo in the README's deploy instructions.
- `docs/SUPPORTED-DISTROS.md` claimed el8 support that nothing tests, and an
  Ubuntu Pro ESM path that does not exist.

### Removed

- `deploy/` - the per-distro VM deploy scripts, superseded by the harness.
- The per-distro inventories; `environments/example` is the template.
- RHEL/CentOS 5 support and `rhel5-ansible-prep/`.

## [3.0.0] - 2026-07-16

Host-CPU fix and auditd modernisation. `--backlog_wait_time 0` so the kernel
drops on backlog overflow instead of throttling syscalls and stalling the host;
`-i` moved first so directives an older kernel does not know are skipped rather
than aborting the load; new kernel TTPs (eBPF, namespace escape, io_uring,
fileless); multi-profile ruleset restored (low/medium/high + internet profile).

## [2.9.0] - 2025-01-02

MITRE technique IDs on detection keys; non-root high-frequency execve excludes
added during a customer-site performance review.

## [2.7.0] - 2024-11-07

Tiered auditd profiles (low/medium/high) migrated from the PaaS collector line.

## [2.6.0] - 2023-11-08

MITRE merge; virtualisation coverage.

## [2.5.5] - 2023-06-14

US DoD merge.

## [2.5.4] - 2023-03-21

GCHQ merge.

## [2.5.1] - 2022-11-22

Moved ansible module use for SELinix for rsyslog port to shell execution to reduce ansible/python/lib interdepencencies or older/unsupported distro releases  
Rsyslog fixes for RHEL4-6

## [2.5.0] - 2022-11-21

Initial merged release