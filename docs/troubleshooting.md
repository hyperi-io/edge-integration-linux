# Troubleshooting

Most failures name themselves: the role checks its inputs and the host before it changes anything, and fails with a message that says what to set. Find the message below. When a run succeeds and records still do not arrive, walk the path at the end of this page.

| Message contains | Cause | Fix |
|---|---|---|
| `receiver address is not set` | Neither `hyperi_audit_receiver_address` nor `collector_address` is set. | Set `hyperi_audit_receiver_address` in the inventory, or pass `-e hyperi_audit_receiver_address=<host>`. |
| `must be a host name or IP address` | The receiver address holds a character other than letters, digits, `.`, `:` or `-`. | Give one host name or IP, with no port, scheme or list. |
| `must be one of` | A level, overlay, transport or TLS mode the role does not know. | Use a value from [configuration](configuration.md#role-variables). |
| `must be a TCP port` | A port outside 1 to 65535, or not a number. | Fix `hyperi_audit_port_audit` or `hyperi_audit_port_syslog`. |
| `relp-tls does not support tls_mode=server` | librelp negotiates mutual authentication for any authenticated mode. | Use `anon` or `mutual` with `relp-tls`. |
| `hyperi_audit_tls_ca_file must be set` | `server` and `mutual` check the receiver against a CA. | Point it at the CA file on the endpoint. |
| `must both be set for tls_mode=mutual` | `mutual` needs the endpoint's certificate and key. | Set `hyperi_audit_tls_client_cert` and `hyperi_audit_tls_client_key`. |
| `must be an absolute path` | A TLS file path is relative, or holds quotes or whitespace. | Use an absolute path with neither. |
| `hyperi_audit_tls_permitted_peer must be set` | The receiver is addressed by IP, and the certificate check needs a name. | Set it to the name in the receiver's certificate. |
| `relp and relp-tls need rsyslog 7 or later` | The host runs rsyslog 5 or 6. | Use `syslog-tls` or `tcp` for that host. |
| `could not parse versions` | `rsyslogd -v` or `auditctl -v` printed something unexpected. | Run both by hand on the host and check the packages installed. |
| `SELinux policy build tooling is missing` | `/usr/share/selinux/devel/Makefile` is absent, so the policy module cannot build. | Install `policycoreutils-devel` or `selinux-policy-devel`, then re-run. |
| `Check the rsyslog config parses` fails | `rsyslogd -N1` found an error in the merged rsyslog config. | Run `rsyslogd -N1` on the host and fix the line it names. A second `$IncludeConfig /etc/rsyslog.d/*.conf` added by hand is the usual one. |
| `'_AnsiblePathHookFinder' object has no attribute 'find_spec'` | An `ansible-core` 2.12 run on Python 3.12 or later. | Run it with `uvx --python 3.10` ([legacy targets](deploying-to-legacy-targets.md)). |
| `no matching key exchange method found` | The host offers only key exchanges current OpenSSH turns off. | Add `--ssh-common-args='-o KexAlgorithms=+<algorithm>'` ([legacy targets](deploying-to-legacy-targets.md)). |

Warnings do not stop the run, and each one says something you may want to act on:

| Warning | Meaning | Do |
|---|---|---|
| `hyperi_audit_profile_override=... is deprecated` | The deprecated variable picked the level and overlays it names. | Move to `hyperi_audit_level` and `hyperi_audit_use_cases`. |
| `The kernel audit config is locked (enabled=2)` | An earlier run locked the rules. `auditd.conf` changes apply now, and the rules at the next reboot. | Reboot when it suits, then check `auditctl -l`. |
| `webserver overlay: none of [...] exists here` | No account in `hyperi_audit_webserver_users` exists on the host, so no webshell rules were added. | Add the account your web server runs as. |
| `WARNING: Kernel holds N of the M rules` | The kernel loaded fewer rules than `augenrules` merged. On el6 and el7 the kernel does not know some syscalls, and that is expected. On a current kernel a rule failed to parse. | Load the rules one at a time with `auditctl` to find the line it rejects. |
| `the merged ruleset does not end in -e 2` | A file in `rules.d` sorts after `hyperi-audit.rules` and sets `-e` itself. | Rename that file to sort first, or drop its `-e` line. |

When records are not arriving, walk the path from the host outward, as root on the host, and stop at the first check that fails:

1. `systemctl is-active auditd rsyslog` prints `active` twice. On el6, `service auditd status` and `service rsyslog status`.
2. `tail -n 3 /var/log/audit/audit.log` shows recent records. If not, auditd is not writing, or the kernel holds no rules (`auditctl -l`).
3. `ls -l /var/log/audit/audit.log` shows a group rsyslog runs in, mode `0640` or wider. On Debian and Ubuntu that is `adm`.
4. `grep -E '(IncludeConfig|include).*rsyslog.d' /etc/rsyslog.conf` finds an include, so rsyslog reads `/etc/rsyslog.d/99-hyperi-rsyslog.conf`.
5. `rsyslogd -N1` reports no errors.
6. The receiver port answers from the host: `timeout 5 bash -c '</dev/tcp/<receiver>/12201' && echo open`. If not, check firewalls on the path, and on SELinux hosts `semanage port -l | grep 12201`.
7. With a TLS transport, rsyslog's log names any handshake failure. `No supported cipher suites have been found` under `anon` means the host's crypto policy turns off anonymous ciphers: use `server` or `mutual` ([transport](transport.md)).

If all seven pass, records are leaving the host. Look at the receiver's ingest next.
