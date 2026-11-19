# Security considerations

Read this before you deploy to hosts you care about. The role runs as root, changes how the host audits, and by default sends what it collects in cleartext.

The default transport is plain TCP to ports 12201 and 12205. Audit records hold the commands people ran, the files they touched and every privilege change, so anyone on the path can read them and anyone in the path can alter them. On any link you do not control, set `hyperi_audit_transport: syslog-tls` with `hyperi_audit_tls_mode: server` or `mutual` ([transport](transport.md)). `anon` encrypts but authenticates nobody, so it stops a passive listener and not an active one.

The endpoint opens no listening port. It connects out to the receiver, and on SELinux hosts the role labels the receiver ports `syslogd_port_t` so rsyslog may do that.

## The role adds rules, and its control lines govern the host

The role writes one file, `/etc/audit/rules.d/hyperi-audit.rules`, and leaves the distro's files and yours in `rules.d` alone. `augenrules` merges them all and keeps the last `-b`, `-f`, `--backlog_wait_time` and `-e` it reads, which are the role's, because its file sorts after `audit.rules` and every `NN-*.rules`. Those settings then apply to the whole merged ruleset:

- `-e 2` locks every rule on the host until reboot, the distro's included. Any tool that changes audit rules at run time fails from then on.
- `--backlog_wait_time 0` drops records when the kernel backlog is full, rather than stalling every syscall. A flood of events can push records out, and `auditctl -s` counts them under `lost`.
- `-f 1` logs an audit failure to the kernel log and carries on. The host never panics over audit.
- Loading the merged set flushes the kernel first, so rules added by hand with `auditctl` and never written to `rules.d` are gone.

The first matching rule in load order decides an event, and the distro's files load before the role's. A broad `never` rule in one of them silences the matching HyperI rules ([rulesets](rulesets.md)).

From the second run on, the kernel is locked by the first run's `-e 2`. The role sees the lock, restarts auditd so the `auditd.conf` changes apply, and leaves the changed rules for the next reboot. A clean run on a locked host therefore does not mean the changed rules are live. Check after the reboot with `auditctl -l` and a known audited action reaching the receiver.

While auditd restarts, the kernel holds records in its backlog, and a busy host can overflow it and lose some. The role restarts only when the config changed or the host is out of step with it, so a repeat run with nothing to change leaves the services running.

## What else the role changes, and what it needs from you

| Change | What to know |
|---|---|
| Upgrades `rsyslog` and the audit package to the distro's latest release on every run | A run is a package upgrade for those two. |
| Edits nine values in `/etc/audit/auditd.conf` in place | No backup is kept. Capture the stock file first if you may want it back. |
| Sets `log_group = adm` on Debian and Ubuntu | Every member of `adm` can read `audit.log`. Elsewhere it stays `root`. |
| Writes the rules file `0640` and the rsyslog drop-in `0644`, both owned by root | The drop-in names the receiver and the certificate paths, never key material. |
| Loads the SELinux module `rsyslog_read_audit_logs` | It grants `syslogd_t` read access to the audit log, and nothing more. |
| Lifts `RefuseManualStop` for the auditd restart | Through a drop-in under `/run`, removed when the restart ends and gone at reboot. The packaged unit file is not edited. |

[Uninstall](uninstall.md) reverses each of these by hand. There is no task that undoes a deploy.

Use SSH keys for the connection, and keep any `become` password in an `ansible-vault` file or type it at `-K`. Never write `ansible_password` in plain text in an inventory, and keep SSH host key checking on.

Client private keys for `mutual` TLS belong on the endpoint as `0600` root, or `0640` root and the rsyslog group where rsyslog drops privileges (`syslog` on Ubuntu). The role reads the paths and never copies keys.
