# Uninstall

No task reverses a deploy, so removal is by hand, as root on each host. Removing the role stops the host's audit stream reaching the receiver, so put whatever replaces it in place in the same change.

| The role | Reverse it by |
|---|---|
| Wrote `/etc/audit/rules.d/hyperi-audit.rules` | Deleting it. The other files in `rules.d` were never touched. |
| Set nine values in `/etc/audit/auditd.conf` | Restoring the file from config management or a backup ([the values](configuration.md#auditdconf)). Reinstalling the audit package keeps a changed config file. |
| Wrote `/etc/rsyslog.d/99-hyperi-rsyslog.conf` | Deleting it, then its queue files in rsyslog's work directory. |
| Appended `$IncludeConfig /etc/rsyslog.d/*.conf` to `/etc/rsyslog.conf`, where nothing included `rsyslog.d` | Deleting that line, where it is the file's only mention of `rsyslog.d`. |
| Set `USE_AUGENRULES="yes"` in `/etc/sysconfig/auditd` (el6) | Setting it back to `"no"`. |
| Loaded the SELinux module `rsyslog_read_audit_logs` and labelled the receiver ports | `semodule -r` and `semanage port -d`. The port labels are harmless to leave. |
| Installed `rsyslog-gnutls` or `rsyslog-relp` for a TLS or RELP transport | Removing the package, if nothing else uses it. |

To remove it:

1. Delete the rules file and the forwarder:

   ```sh
   rm -f /etc/audit/rules.d/hyperi-audit.rules /etc/rsyslog.d/99-hyperi-rsyslog.conf
   rm -rf /var/lib/hyperi_audit
   ```

2. Restore `/etc/audit/auditd.conf` from your config management or backup.
3. In `/etc/rsyslog.conf`, delete `$IncludeConfig /etc/rsyslog.d/*.conf` if nothing else in the file mentions `rsyslog.d`. EL 8 and later, Amazon Linux and current Debian include it themselves, and the role left those files alone.
4. On SELinux hosts, remove the policy module:

   ```sh
   semodule -r rsyslog_read_audit_logs
   ```

5. Check `auditctl -s`. If it shows `enabled 2`, the kernel is locked: reboot, and skip the next step.
6. Otherwise load the remaining rules and restart the services. EL's auditd unit sets `RefuseManualStop=yes`, so restart auditd there with `service auditd restart` in place of `systemctl`:

   ```sh
   augenrules --load
   systemctl restart auditd rsyslog
   ```

7. Delete the queue files the forwarder left in rsyslog's work directory, named `hyperi_audit*` and `hyperi_syslog*`. The `WorkDirectory` or `workDirectory` setting in `/etc/rsyslog.conf` names the directory.
8. Check the host:

   ```sh
   auditctl -l | grep -c 'key=T1059_root_tmp'   # 0
   test -e /etc/rsyslog.d/99-hyperi-rsyslog.conf || echo removed
   systemctl is-active auditd rsyslog            # active, twice
   ```

Then confirm at the receiver that records from the host have stopped arriving on the audit port.

A run that stopped part way through a restart can leave `/run/systemd/system/auditd.service.d/10-hyperi-allow-stop.conf` behind until the next reboot. Delete it and run `systemctl daemon-reload` if it is there.
