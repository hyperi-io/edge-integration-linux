# 2. One layered ruleset template, cheap directory watches, added beside the distro's rules

Status: accepted.

The role shipped four static rules files, one per profile: `low`, `medium`, `high` and `internet`. Most rules sat in all four, so a fix meant four edits, and `internet` was a copy of `medium` with no `high` equivalent. Deploying one renamed the distro's rules aside and flushed the kernel, so a host lost any compliance or local rules it had.

The files watched directories with `-w dir/`. A `-w` watch has every syscall in its mask, so each one costs the host on every syscall it makes, about 15 ns a watch in lab VMs. Dozens of them added up on every host.

## Decision

1. One Jinja template, `roles/hyperi_audit/templates/hyperi-audit.rules.j2`, renders the ruleset on each host. `hyperi_audit_level` picks `low`, `medium` or `high`, each holding the one below it. `hyperi_audit_use_cases` adds any of the `webserver`, `edge` and `container-host` overlays. `internet` becomes `medium` with `edge` and `webserver`.
2. A directory that exists at deploy time is watched as `-a always,exit -F arch=b64 -F perm=<perm> -F dir=<dir>`, whose mask holds only the syscalls `perm=` covers. A missing directory keeps the `-w` form, because `dir=` needs the directory to exist.
3. The role writes `/etc/audit/rules.d/hyperi-audit.rules` and leaves every other file in `rules.d` in place. `augenrules` merges them, and keeps the last `-b`, `-f`, `--backlog_wait_time` and `-e` it reads, which are ours because `hyperi-audit.rules` sorts after `audit.rules` and every `NN-*.rules`.

Consequences, good:

- A rule changes in one place, and any level combines with any overlay, `high` with `edge` included.
- The host keeps the rules it had. Compliance rules sit beside ours.
- The `dir=` form costs about a quarter of a `-w` watch. Cost per `getppid` call fell from 737 to 551 ns at `medium` on Debian 13 (kernel 6.12), and from 745 to 596 ns on Rocky 9 (kernel 5.14), by `test/lab/bench.sh`.

Bad, and we accept it:

- Two hosts on the same level can carry different rules, because the render follows each host's directories and web server accounts. Reviewing a ruleset means rendering it (`test/render.yml`).
- The first matching rule in load order decides an event, and the distro's files load first. A broad `never` rule in one of them silences ours.
- A local file that sorts after `hyperi-audit.rules` can override our backlog, failure mode and lock lines.
- A directory created after deploy stays a `-w` watch until the role runs again.

Related:

- [`../rulesets.md`](../rulesets.md) -- the layers, rule order and cost.
- [`../configuration.md`](../configuration.md) -- what each level and overlay holds.
- [`0001-auditd-to-file-to-rsyslog-not-audisp.md`](0001-auditd-to-file-to-rsyslog-not-audisp.md) -- the transport these rules feed.
