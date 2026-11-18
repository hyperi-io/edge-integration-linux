# Configuration reference

Every variable the `hyperi_audit` role reads, what each ruleset level and overlay adds, and the `auditd.conf` values the role sets. Defaults live in `roles/hyperi_audit/defaults/main.yml`, and the ruleset in `roles/hyperi_audit/templates/hyperi-audit.rules.j2`. Set the variables in your inventory's `vars:` block, in `group_vars/`, or with `--extra-vars`.

## Role variables

The role checks every input before it touches the host, so a bad value fails the run in the first few tasks with a message naming the variable.

| Variable | Default | Accepts | Effect |
|---|---|---|---|
| `hyperi_audit_receiver_address` | the value of `collector_address`, else empty | host name or IP address | The receiver for both streams. Required. A value that is empty, or holds anything but letters, digits, `.`, `:` and `-`, fails the run. |
| `hyperi_audit_level` | `medium` | `low`, `medium`, `high` | Ruleset depth. Levels are cumulative: `medium` is `low` plus more, `high` is `medium` plus more. |
| `hyperi_audit_use_cases` | `[]` | a list of `webserver`, `edge`, `container-host` | Overlays applied on top of the level. See [Overlays](#overlays). |
| `hyperi_audit_webserver_users` | `www-data`, `apache`, `nginx`, `httpd`, `lighttpd`, `caddy` | account names | Accounts the `webserver` overlay treats as web servers. The role resolves the ones that exist on the host to uids at deploy time. When none exist it warns and adds no webshell rules. |
| `hyperi_audit_transport` | `tcp` | `tcp`, `syslog-tls`, `relp`, `relp-tls` | How both streams leave the host. See [transport](transport.md). |
| `hyperi_audit_tls_mode` | `anon` | `anon`, `server`, `mutual` | TLS trust for `syslog-tls` and `relp-tls`. `relp-tls` takes `anon` or `mutual`. Ignored for `tcp` and `relp`. |
| `hyperi_audit_tls_ca_file` | empty | absolute path on the endpoint | CA that signed the receiver's certificate. Required for `server` and `mutual`. |
| `hyperi_audit_tls_client_cert` | empty | absolute path on the endpoint | The endpoint's certificate. Required for `mutual`. |
| `hyperi_audit_tls_client_key` | empty | absolute path on the endpoint | The endpoint's private key. Required for `mutual`. |
| `hyperi_audit_tls_permitted_peer` | empty | a certificate name, no spaces or quotes | The name the receiver's certificate must carry under `server` and `mutual`. Empty means the receiver address. Required when the receiver address is an IP. |
| `hyperi_audit_port_audit` | `12201` | 1 to 65535 | Receiver port for the audit stream. |
| `hyperi_audit_port_syslog` | `12205` | 1 to 65535 | Receiver port for the syslog stream. |
| `hyperi_audit_start_services` | `true` | boolean | `false` writes the config and leaves services alone. The container harness uses it, because its containers run no init. |

TLS file paths must be absolute with no quotes or whitespace, because they land inside rsyslog config.

### Deprecated variables

Both still work, and both will go in a later major release.

| Variable | Use instead | Behaviour |
|---|---|---|
| `collector_address` | `hyperi_audit_receiver_address` | Read as the receiver when `hyperi_audit_receiver_address` is unset. |
| `hyperi_audit_profile_override` | `hyperi_audit_level` and `hyperi_audit_use_cases` | `low`, `medium` or `high` replaces the level. `internet` runs `medium` with the `edge` and `webserver` overlays, added to any overlays you set. The run logs a warning naming the level and overlays it chose. |

## Levels

Pick the lowest level that covers what you need to see. Every level shares the control block, the self-protection watches and the final `-e 2` lock. Each row lists what that level adds to the one before it.

### Settings that change with the level

| Setting | `low` | `medium` | `high` |
|---|---|---|---|
| Kernel backlog (`-b`) | 8192 | 8192 | 16384 |
| `priority_boost` in `auditd.conf` | 2 | 4 | 4 |
| `CWD` records | excluded | kept | kept |
| `ptrace` | `POKETEXT`, `POKEDATA`, `POKEUSER` only | every call | every call |
| systemd unit watches | `/etc/systemd/system`, `/usr/lib/systemd/system` | all of `/etc/systemd`, `/usr/lib/systemd`, `/run/systemd/system` | as `medium` |

### What each level adds

| Area | `low` (the base) | `medium` adds | `high` adds |
|---|---|---|---|
| Execution | Root exec from `/tmp`, `/var/tmp`, `/dev/shm`. Any exec from `/dev/shm`. setuid exec | Root exec from `/home`, `/usr/local/bin`, `/opt`. setgid exec | Any exec from `/tmp` and `/var/tmp`. `bash` as root, `python`, `python3`, `perl`. Exec in another user's privilege context. setuid and setgid calls |
| Audit self-protection | `/var/log/audit`, `/etc/audit`, `/etc/audisp`, the audit tools | `/etc/libaudit.conf`, `ausearch`, `aureport`, `aulast`, `aulastlogin`, `auvirt` | |
| Kernel | eBPF, `memfd_create`, `kexec`, `open_by_handle_at`, `process_vm_readv` and `_writev`, module load and unload, `/etc/modprobe.d` | `setns`, `unshare`, `io_uring_setup`, sysctl files, `/etc/modules-load.d`, PAM module directories | `pidfd_getfd`, `userfaultfd` |
| Time | `settimeofday`, `clock_settime`, `/etc/localtime` | `adjtimex`, file timestamp changes from a login session | |
| Persistence | cron directories and `crontab`, `/var/spool/cron`, init scripts, `rc.local`, `systemctl` | `anacrontab`, cron and at allow and deny lists, `at`, `/etc/init`, motd scripts, udev rules | XDG autostart |
| Accounts and credentials | `sudoers`, `passwd`, `group`, `shadow` reads and writes, `gshadow`, `useradd`, `usermod`, `userdel`, `su`, `sudo`, `pkexec` | group tools, `gpasswd`, `chage`, `setcap`, `opasswd`, `ldapsearch`, `dbus-send`, `gdbus`, `pam.d`, root touching another user's home | `limits.conf`, `limits.d`, `pam_env.conf` |
| Shell and SSH | `ld.so.preload`, `/etc/profile` and `profile.d`, root's `.bashrc`, `sshd_config`, `/root/.ssh` | `ld.so.conf`, shell rc files, root's other profiles | |
| File changes from a login session | | `chmod`, `chown` and xattr calls, file deletion and rename | |
| Defence evasion | dmesg clear, ASLR off, rsyslog config, `setenforce`, `systemd-run`, SELinux and AppArmor config, `shred`, `wipe`, root deleting files | `scrub`, `dd` | |
| Network | AF_ALG crypto sockets, raw packet sockets, socket filters | Every successful IPv4 and IPv6 `connect`. Network config files | Every IPv4 and IPv6 socket created, DNS lookups included |
| Mounts and host identity | `mknod`, `mount` from a session, `sethostname`, `/etc/hosts` | `swapon`, `swapoff`, `/etc/hostname`, `/etc/issue` | |
| Power | `shutdown`, `reboot` | `poweroff`, `halt` | |
| Tools | `wget`, `curl`, `ssh`, `socat`, `nc`, `ncat`, `stunnel` | `ftp`, `scp`, `sftp`, remote-desktop tools, `certutil`, `unzip`, `base64`, `openssl`, mail config | Recon tools (`whoami`, `id`, `uname`, `nmap`, `ss`, `tcpdump` and more), archive tools, `cp` and `mv` from a session |
| Containers and packages | `docker` and its socket | `dockerd`, `podman`, `containerd`, `runc`, `crictl`, `kubelet`, Docker config. Package managers | More package managers |
| High only | | | SysV IPC, denied opens under `/etc` and `/root`, login records (`utmp`, `wtmp`, `btmp`, `lastlog`), GRUB config, BigFix, Chef, Salt and Puppet config |

Every level also carries a 32-bit ABI tripwire: the rules are `arch=b64`, so a short list of `b32` rules flags a 32-bit process doing what they watch.

At `high`, `grep`, `ls`, `cat` and seven other common commands run from a login session are excluded, so `sudo` sessions do not flood the privilege-context rule.

## Overlays

An overlay adds or removes rules for what the host does. Combine them freely with any level.

| Overlay | Adds | Removes | Use it on |
|---|---|---|---|
| `webserver` | Every `execve` and `execveat` by a web server account, key `T1505.003_webshell` | `connect` logging for those accounts, which talk to their backends on every request | Hosts serving HTTP |
| `edge` | nothing | Per-connection `connect` logging (`medium`, `high`) and per-socket logging (`high`) | Internet-facing hosts with a firewall or NIDS that logs flows |
| `container-host` | nothing | The runtime's own `setns`, `unshare`, `mount`, `umount2` and `bpf` calls from `runc`, `crun`, `containerd`, `dockerd`, `conmon` and PID 1 | Docker, containerd or Podman hosts |

Per-connection logging is the largest event source the ruleset has. On a busy host it can overflow the kernel backlog, and `--backlog_wait_time 0` then drops events rather than stalling the host. Measured numbers are in [rulesets](rulesets.md#the-cost-of-a-rule).

## auditd.conf

The role edits `/etc/audit/auditd.conf` line by line and leaves every other line alone. An unknown key or value there stops `auditd` from starting, so the two version-dependent values are chosen from the `auditctl -v` the role reads on the host.

| Setting | Value | Why |
|---|---|---|
| `name_format` | `hostname` | Every record carries the host name, so the receiver can tell hosts apart. |
| `log_group` | `adm` on Debian and Ubuntu, `root` elsewhere | rsyslog runs as `syslog` in group `adm` on Ubuntu and must read `audit.log`. |
| `log_format` | `ENRICHED` on audit 2.8 and later, else `RAW` | ENRICHED resolves uids and syscall numbers to names at write time. |
| `flush` | `incremental_async` on audit 2.6 and later, else `incremental` | Async flush keeps durability without an fsync on every record. |
| `freq` | `200` | Records between flushes. |
| `priority_boost` | `2` at `low`, `4` otherwise | Lower on `low` hosts to leave CPU for the workload. |
| `max_log_file` | `100` | MB per log file. |
| `num_logs` | `5` | Rotated files kept. |
| `max_log_file_action` | `ROTATE` | Rotate rather than suspend or halt on a full log. |
