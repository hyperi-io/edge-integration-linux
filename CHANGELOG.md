# Changelog

All notable changes to this project are recorded in this file. semantic-release writes each entry from the Conventional Commits merged since the release before it, and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.1](https://github.com/hyperi-io/edge-integration-linux/compare/v4.0.0...v4.0.1) (2026-11-19)

### Bug Fixes

* **test:** wait for auditd before counting kernel events ([27b51e3](https://github.com/hyperi-io/edge-integration-linux/commit/27b51e31fe3462809c7c5d946e879d2c097a5ed3))

## 4.0.0 (2026-11-19)

### Added

- `hyperi_audit_receiver_address` names the receiver for both streams.
- Ruleset levels `low`, `medium` and `high`, each holding the one below it, rendered on each host from one template, `roles/hyperi_audit/templates/hyperi-audit.rules.j2`.
- Overlays in `hyperi_audit_use_cases`: `webserver` logs every command a web server account runs, `edge` drops per-connection logging, `container-host` drops the container runtime's own namespace and mount calls. `hyperi_audit_webserver_users` names the web server accounts.
- Detections for `process_vm_readv` and `process_vm_writev`, `pidfd_getfd`, `userfaultfd`, any exec from `/dev/shm`, any exec from `/tmp` at `high`, `/etc/rc.local`, writes to `/etc/shadow`, `/etc/environment` and `setcap`.
- Optional transports in `hyperi_audit_transport`: `syslog-tls`, `relp` and `relp-tls`, with TLS trust in `hyperi_audit_tls_mode` (`anon`, `server`, `mutual`), certificate paths, a permitted peer name, and configurable ports.
- The run fails before changing the host on a malformed receiver address, port or TLS file path, and after loading rules it logs how many of the merged rules the kernel holds.
- Tests: a Docker harness over every distro in `test/matrix.yml`, a CI kernel job that loads every rendered ruleset and fires the detections, a lint job, and a VM lab with a syscall benchmark and rule-order probes.
- Role defaults and Galaxy metadata, and a Renovate config.
- `rules/hyperi-audit-<profile>.rules`: each profile as a plain rules file for any x64 or arm64 host. A syscall some supported host lacks gets a line of its own, so only that line fails there. CI fails if they drift from the template or a heavier level stops holding the lighter one.
- Detections at `low`: a setuid or setgid bit being set, the new mount API, `reboot(2)`, systemd generator directories, syslog-ng config. At `medium`: `chroot` and `pivot_root` from a session, polkit rules, Kerberos and SSSD config, firewall config and tools, SELinux relabelling tools, `sysctl`, `/boot`, udev rules under `/usr/lib` and `/run`, and each login account's `authorized_keys` (`hyperi_audit_user_watch_max`). At `high`: every command a login session runs, and each login account's `.bashrc` and `.profile`. The `webserver` overlay adds exec from a web root.
- SigmaHQ's `susp_activity` key on the `scp`, `sftp`, `ftp`, `socat`, `rdesktop`, `tshark` and `wireshark` watches.

### Changed

- The role adds `/etc/audit/rules.d/hyperi-audit.rules` beside the host's rules and leaves the distro's rules in place.
- A watched directory that exists is written as `-a always,exit -F perm= -F dir=`, which costs about a quarter of a `-w` watch. With the added detections, the published files cost about the same per syscall as the rules they replace ([rulesets](docs/rulesets.md#the-cost-of-a-rule)).
- The role is renamed `hsaudit` to `hyperi_audit`, with its variables (`hyperi_audit_*`) and deployed paths (`/etc/audit/rules.d/hyperi-audit.rules`, `/etc/rsyslog.d/99-hyperi-rsyslog.conf`).
- Services restart only when their config differs from the last config applied, recorded in `/var/lib/hyperi_audit/applied.json` once a restart succeeds.
- Keys on ATT&CK ids revoked in 2026 move to the current ids, and keep the old key as a second key: `T1562*` to `T1685`, `T1562.012` to `T1685.004`, `T1070.002` to `T1685.006`, `T1099` to `T1070.006`. `auditconfig` and `audittools` gain `T1685.004` keys. `tcpdump`, `tshark` and `wireshark` gain `T1040_sniff`.
- The role fits each `-S` list to the host's syscall table and points exec watches at the real binary, so rules load on arm64 and a symlinked binary's watch fires.
- PAM config and module directories move from `medium` to `low`. `/boot` at `medium` replaces the `high` GRUB config watches.
- The release artefact is `edge-integration-linux-<git describe>.tar.gz`, built by `build-tarball.sh` from the committed tree with `git archive`.
- Licensed under Apache-2.0, with third-party attributions in `NOTICE`.

### Deprecated

- `collector_address`. Use `hyperi_audit_receiver_address`.
- `hyperi_audit_profile_override`. Use `hyperi_audit_level` and `hyperi_audit_use_cases`. `internet` maps to `medium` with the `edge` and `webserver` overlays.

### Removed

- The per-profile rules files `roles/hyperi_audit/files/hyperi-audit-<profile>.rules`, replaced by the template.
- `deploy/`, the per-distro VM deploy scripts, and the per-distro inventories. `environments/example` is the template.
- RHEL and CentOS 5 support, and `rhel5-ansible-prep/`.

### Fixed

Forwarding:

- On Ubuntu the audit stream never forwarded: `log_group = root` left `audit.log` at `0600`, and rsyslog runs as `syslog` in `adm`. Debian and Ubuntu use `adm`.
- A long receiver outage dropped audit records. Each stream has a disk-assisted queue.
- With `server` or `mutual` TLS and no permitted peer, the endpoint accepted any certificate the CA signed. It checks the name, which defaults to the receiver address.
- On el6 the audit stream also went out on the syslog port.
- On EL 8 and later and Amazon Linux, rsyslog parsed the drop-in twice.

Rules:

- el6 never loaded `rules.d`. The role sets `USE_AUGENRULES="yes"`.
- On audit 4 (Debian 13) a restart never reloaded the rules. The role runs `augenrules --load`.
- The message-type excludes never loaded in any release, because an exclude rule takes no key.
- The setuid-exec rule missed most setuid runs, and `fexecve` and `execveat` got past the exec-location rules.
- Escalated execution was not logged: the session excludes sat above the `euid=0` exec rules, and the first match won.

Services:

- `RefuseManualStop` toggling edited the packaged auditd unit and left systemd's loaded state at `no`. A drop-in under `/run` lifts it for the restart.
- Debian and Ubuntu auditd units got `RefuseManualStop` appended under `[Install]`. The role removes it.
- The auditd restart was skipped on every deploy after the first, and a failed run lost its pending restart. The restart is decided from the host's state.
- The role restarted services on every run.

Packaging:

- `environments/example` did not parse.
- `build-tarball.sh` always exited 1.

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
