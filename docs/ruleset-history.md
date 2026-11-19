# Ruleset history

How the audit ruleset in `roles/hyperi_audit/templates/hyperi-audit.rules.j2` came to be. The template keeps a short changelog in its header, and [ruleset design notes](ruleset-design-notes.md) has the reasons behind individual rules.

The ruleset is forked from Florian Roth's (Neo23x0) "Best Practice Auditd Configuration" (https://github.com/Neo23x0/auditd, Apache-2.0), then merged in turn with the public baselines: Neo23x0 (Florian Roth) -> ACSC (ASD) OpenSCAP -> NIST -> DISA STIG -> alphagov/GDS -> US DoD -> SigmaHQ. Each merge took the DELTA the newer source had that we did not, and replaced our line where the newer source did it better. Roughly every second merge was followed by a performance review, because breadth accrues and CPU does not.

Don't merge from upstream linux-audit's `rules/` directory. Its `10-base-config.rules` still ships `--backlog_wait_time 60000`, the exact host-CPU bug v3.0 fixed, and `20-dont-audit.rules` ships its noise suppressors commented out.
## Changelog

Newest first. Before v4.0 each profile (LOW, MEDIUM, HIGH, INTERNET) was its own file, and a note marked with a profile came from that file. Entries before v3.0 were rebuilt from the merge order when the pre-git tracking was retired.

| Version | Date | Change |
|---|---|---|
| v4.0 | 2026-11-19 | One layered template replaces the four profile files: low is the base, medium adds to low, high adds to medium. INTERNET became the edge overlay, beside the webserver and container-host overlays. |
| | | Directory watches that exist on the host are `-F dir= -F perm=` rules, a quarter of the per-syscall cost of `-w dir/`. `-S` lists are fitted to each host's syscall table, so the rules load on arm64 and on older audit releases. |
| | | Fixed: the msgtype excludes had a key, so no release ever loaded them. The setuid-exec rule matched almost nothing, and is `euid=0` with `uid!=euid` now. execveat and fexecve bypassed the execution rules. |
| | | Fixed: docker.sock connects and `/etc/shadow` writes were unseen, and failed setid calls took the generic setid key. auid scoping hid Shocker and module loads by daemons, and the b32 tripwire was `-S all`. |
| v3.3 | 2026-07-20 | Baseline refresh from ACSC, NIST and DISA STIG: AppArmor MAC tamper (Ubuntu was a whole-distro blind spot), nsswitch, gpasswd and chage, fchmodat2 (modern-kernel chmod), open_by_handle_at (the Shocker container escape). HIGH: legacy `pam.conf`. The `hyperi_audit_use_case` role variable was renamed `hyperi_audit_profile_override` (it replaces the level). |
| v3.2 | 2026-07-17 | Sigma alignment and baseline refresh. Rules SigmaHQ matches by key got the upstream key name alongside ours. Added dmesg clear and off, ASLR-disable, rsyslog config, setenforce, systemd-run, and the Neo23x0 2026-05 socket delta (AF_ALG, raw socket, socket BPF). |
| | | Fixed: user crontabs were watched on the Debian path only, so cron persistence went unlogged on EL. HIGH, fixed: `T1548.001_priv_ctx_exec` fired on EVERY daemon execve (auid=unset is not != uid). |
| v3.1 | 2026-07-17 | Escalated-execution rules moved ABOVE the excludes. The excludes match auid>=1000 plus a path with no euid scoping, so below them `sudo cat /tmp/x` went unlogged. |
| v3.0 | 2026-07-16 | KERNEL CPU FIX: `--backlog_wait_time 0` (was 60000). A non-zero wait makes the kernel block syscalls when the backlog fills, which stalls the host. 0 drops on overflow instead (the Auditbeat default, and Steve Grubb's recommendation). Kernel 3.14+, and el6 skips it via `-i`. |
| | | `-i` moved first, so directives and syscalls a kernel does not know (backlog_wait_time, loginuid-immutable, the filesystem filter, execveat, memfd_create, bpf, setns, io_uring, finit_module) are skipped from el6 (audit 2.4.x, kernel 2.6.32) to audit 3.x. |
| | | New TTPs: eBPF (bpf), namespace and container escape (setns, unshare, container runtimes), io_uring, setuid and setgid root exec, fileless execution (memfd_create). Fixed the dangling `-F` syntax error on the shred, wipe, scrub and dd rules (now path watches). |
| | | Dropped the per-binary execute-watch sprawl (macOS, VirtualBox, Parallels, the full compressor list, generic config management) that duplicated telemetry and bloated the kernel filter. LOW: trimmed to the low-volume, high-signal subset. INTERNET: the per-connection connect4, connect6 and socket block dropped. |
| v2.9 | 2025-01-02 | MITRE technique ids. Non-root high-frequency execve excludes. Customer-site performance review. |
| v2.7 | 2024-11-07 | Tiered auditd (low, medium, high) migrated from PaaS. INTERNET: connection logging off. |
| v2.6 | 2023-11-08 | MITRE merge, virtualisation. |
| v2.5 | 2023-06-14 | US DoD merge. |
| v2.4 | 2023-03-21 | alphagov/GDS (UK Government Digital Service) merge, via Neo23x0. Recorded as "GCHQ" until 2026-07-17. |
| v2.3 | 2022-11-01 | Updates, merges and fixes. |
| v2.2.1 | 2022-03-08 | Customer-site performance review and merge. |
| v2.2 | 2022-01-10 | HyperI infra merge. |
| v1.7 | 2021-09-03 | DISA STIG merge. |
| v1.6 | 2021-06-23 | NIST merge. |
| v1.5 | 2021-06-01 | ACSC OpenSCAP merge. |
| v1.4 | 2021-01-11 | Initial fork from Neo23x0. |
