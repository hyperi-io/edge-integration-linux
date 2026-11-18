# Ruleset design notes

Why some rules in `roles/hyperi_audit/templates/hyperi-audit.rules.j2` look the way they do. The template's own comments carry the one-line version. The changelog is in [ruleset history](ruleset-history.md).

## Loading on old kernels and arm64

`-i` comes first. It skips any directive, syscall or field the running kernel does not know (el6's 2.6.32, say) instead of aborting the load. auditctl's `fileopt()` checks the ignore flag AFTER a line fails, so even a getopt "unrecognized option" (`--backlog_wait_time` on an auditctl too old to know it) is swallowed.

The skip is right per host because it reacts to the real kernel. Ubuntu 16.04 (auditd 2.4.5 but kernel 4.x) KEEPS `--backlog_wait_time`, while el6 drops it, so a static auditd-version gate would strip the CPU fix from Ubuntu 16.04. `auditd.conf` is the opposite: an unknown keyword or value is fatal at daemon start, so `tasks/auditd.yml` gates those on the auditd version.

`-i` does not rescue a rule with one unknown syscall name: auditctl drops the WHOLE rule (in `auditctl.c` the parse returns -1 and the rule never reaches the kernel). Appending a newer syscall to a working `-S` list therefore deleted that rule on el6 and el7, and `-i` hid it, so until v4.0 every new syscall went on its own line. From v4.0 the role reads the host's table with `ausyscall --dump` and drops the names it lacks. That covers arm64 too, which has no `open`, `unlink`, `rename` or `chmod`, only their `*at` forms. A rendered file copied to another host is not refitted.

## Keys, order and scoping

The exit filter is first-match-wins, and the excludes match on auid plus a path with no euid scoping. Below them, `sudo cat /tmp/x` goes unlogged: auid stays the login uid, so the exclude wins. Scoping the excludes by euid fails the other way: auid=unset (4294967295) is >=1000, so every daemon would be un-excluded and flood the backlog. The webserver overlay's rules sit above the excludes for the same reason, because www-data runs with auid=unset and a webshell's first moves are cat, ls and whoami.

`T1548.001_priv_ctx_exec` MUST keep `-F auid!=unset`. Daemons have auid=unset and uid=0, so `auid!=uid` is true for every daemon execve.

A rule may carry more than one `-k` (auditctl.8): one rule and one record, at no extra cost, searchable by either key. SigmaHQ's `network_service_scanning` matches `key='network_connect_4'` literally and `susp_c2_commands` matches `key='susp_activity'`, so those rules keep both keys. The tool watches (wget, curl, nmap and the rest) each log an EXECVE record with argv, which Sigma's `type: EXECVE` rules match, at a fraction of the cost of a general `-S execve`. None of this assumes SigmaHQ is in the pipeline: every rule earns its place on its own MITRE key.

## Why individual rules exist

The socket rules are rare, not per-connection telemetry, so they are in low and survive the edge overlay. AF_ALG (`a0=38`) is the kernel crypto API: ransomware that encrypts there instead of in a userspace library leaves no library trace. `a2=88` is the SOCKADDR_ALG bind, and `a1=279` is SOL_ALG on setsockopt. We deliberately drop upstream's `-F auid>=1000 -F auid!=unset` scoping, because ransomware usually runs from a compromised service (auid=unset), at the cost of a few boot-time events from cryptsetup. Raw sockets (`AF_PACKET=17`, `SOCK_RAW=3`) mean sniffers and covert channels, and `SO_ATTACH_FILTER` (`a1=1`, `a2=26`) is packet capture.

The dmesg, ASLR and logging-config rules each close a documented bypass of the Neo23x0 config we forked: the repo CheraghiMilad/bypass-Neo23x0-auditd-config exists to defeat it. syslog(2) action 4 is SYSLOG_ACTION_READ_CLEAR, 5 CLEAR and 6 CONSOLE_OFF. `setenforce 0` writes `/sys/fs/selinux/enforce`, which `-w /etc/selinux/` cannot see, so the binary itself is watched. systemd-run reparents a payload to PID 1, away from the caller's auid. Upstream STIG and OSPP both single it out: "It is not audit aware, specifically watch it".

- User crontabs live in `/var/spool/cron/crontabs/` on Debian and Ubuntu, and in `/var/spool/cron/` on EL. The spool file is the artefact and crontab(1) the actor, so medium and up watch the binary too.
- gpasswd and chage are the account changes the useradd, usermod and group* watches miss.
- `nsswitch.conf` selects the passwd, group and shadow backend. Repointing it is an auth bypass (T1556).
- fchmodat2 (kernel 6.6+) is where chmod routes on current kernels.
- AppArmor is the Ubuntu and Debian MAC. Without its watches, editing or unloading a profile was a whole-distro T1562.001 blind spot.
- SELinux AVC denials stay logged, because they flag exploit attempts.
- Not added: SigmaHQ's 19 BPFDoor lock and pid file names. Each watch costs every syscall about 2 ns, so the list would add about 34 ns to every syscall at `high` for one malware family's file names.
