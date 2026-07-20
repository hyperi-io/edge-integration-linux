<!--
Project:      HyperI Linux audit collector
File:         docs/uninstall.md
Purpose:      How-to -- remove the role's changes from a host by hand, because
              there is no built-in undo.
License:      Apache-2.0
Copyright:    (c) 2026 HYPERI PTY LIMITED
-->

# Uninstall

**There is no built-in uninstall.** No task reverses a deploy. Re-running the
role is idempotent and is the *forward* fix -- correct the variables and
re-apply. This page is the *reverse*: a manual runbook to take a host back to its
pre-deploy audit configuration, grounded in exactly what the role changed.

> **Warning:** Removing this configuration removes the host's forwarded audit
> telemetry. On a monitored host that is a detection gap. Restore the host's
> prior audit posture as part of the same change -- do not leave it with nothing.

## What the role changed, and how to reverse each part

| The role did this | Reverse it by |
|---|---|
| Flushed and replaced the audit rules; backed up the distro rules to `<path>.default` | Move the `.default` backup back over the installed ruleset |
| Rewrote `auditd.conf` in place -- **no backup** | Restore stock `auditd.conf` from config management or by reinstalling the audit package |
| Wrote `/etc/rsyslog.d/99-hyperi-rsyslog.conf` | Delete that file |
| Appended `$IncludeConfig /etc/rsyslog.d/*.conf` to `/etc/rsyslog.conf` **only if** the stock config did not already include the drop-in directory | Remove that line **only if the role added it** |
| Installed the `rsyslog_read_audit_logs` SELinux module (SELinux hosts) | `semodule -r rsyslog_read_audit_logs` |
| Added `syslogd_port_t` bindings for TCP 12201/12205 (SELinux hosts) | Optional: `semanage port -d` for each (harmless to leave) |
| May have left `RefuseManualStop=no` in the auditd unit if a run failed mid-swap | Restore `RefuseManualStop=yes` |

## The runbook

Run these as root on the endpoint. Adjust paths for auditd v1 (which uses
`/etc/audit/audit.rules` rather than `/etc/audit/rules.d/`).

**1. Restore the distro's default audit rules.** The role saved them aside with a
`.default` suffix. Move the backup back over the installed HyperI ruleset:

```sh
# auditd v2+ (rules.d)
mv /etc/audit/rules.d/audit.rules.default /etc/audit/rules.d/audit.rules
rm -f /etc/audit/rules.d/hyperi-audit.rules

# auditd v1 (single file)
mv /etc/audit/audit.rules.default /etc/audit/audit.rules
```

If no `.default` exists, the host had no distro ruleset to displace; just remove
the HyperI file and let the package default apply.

**2. Restore `auditd.conf`.** The role edited it **in place and did not back it
up**, so there is no local copy to fall back on. Restore it from your config
management, or by reinstalling the audit package's stock config:

```sh
# RHEL family
yum reinstall -y audit        # or: dnf reinstall -y audit

# Debian/Ubuntu
apt-get install --reinstall -y auditd
```

Reinstalling replaces the package's shipped `auditd.conf` only if the package
manager treats it as replaceable; verify the values afterwards and hand-edit any
site setting the package default does not carry.

**3. Remove the rsyslog forwarder:**

```sh
rm -f /etc/rsyslog.d/99-hyperi-rsyslog.conf
```

Remove the `$IncludeConfig /etc/rsyslog.d/*.conf` line from
`/etc/rsyslog.conf` **only if the role added it**. Modern rsyslog (EL8+, Amazon
Linux) already includes the drop-in directory via `include(...)`, and the role
skips the append in that case -- so on those hosts the line is the distro's, not
the role's. Leave it. Remove it only where `/etc/rsyslog.conf` has no other
reference to `rsyslog.d`.

**4. Remove the SELinux policy module (SELinux hosts only):**

```sh
semodule -r rsyslog_read_audit_logs
```

The `syslogd_port_t` bindings the role added for 12201/12205 are harmless to
leave -- they only permit an outbound connection that nothing will now make. To
remove them anyway:

```sh
semanage port -d -t syslogd_port_t -p tcp 12201
semanage port -d -t syslogd_port_t -p tcp 12205
```

**5. Restore the systemd protection if a run left it relaxed.** A completed
deploy already puts this back; only a run that failed between the stop and the
end of the service block would leave it at `no`:

```sh
grep -q '^RefuseManualStop=no' /usr/lib/systemd/system/auditd.service \
  && echo "relaxed -- restore to yes"
```

Set it back to `RefuseManualStop=yes` and `systemctl daemon-reload` if so.

**6. Reboot, or restart the services.** Restarting reloads `auditd` and
`rsyslog` with the restored config:

```sh
systemctl restart auditd
systemctl restart rsyslog
```

> **Note:** If the host is currently immutable (`auditctl -s` reports
> `enabled 2` -- the role sets `-e 2`), the **kernel will not drop the HyperI
> rules on a restart**; it needs a **reboot** to clear them and load the restored
> ruleset. A plain `systemctl restart auditd` re-reads `auditd.conf` but cannot
> replace immutable kernel rules. Reboot to be certain.

## Verify the host is back

```sh
auditctl -s                                   # expect enabled 0 or 1, not 2
auditctl -l                                   # expect the restored/stock rules
cat /etc/rsyslog.d/99-hyperi-rsyslog.conf     # expect: No such file
systemctl is-active auditd rsyslog            # expect: active
```

Confirm at the collector that the host's records **stop** arriving on TCP 12201.

## See also

- [Security considerations](security-considerations.md) -- why removing the
  telemetry is itself a security decision, and what the role took over.
- [Configuration](configuration.md) -- every role variable and what it set.
- [Deploying to a fleet](deploying-to-a-fleet.md) -- the forward re-apply path
  and the "no undo" note in context.
- [ARCHITECTURE.md](../ARCHITECTURE.md) -- what the role deploys and where it
  lands.
