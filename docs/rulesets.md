# Rulesets

The role renders one audit ruleset per host from `roles/hyperi_audit/templates/hyperi-audit.rules.j2`. The level sets how deep it goes, the overlays tune it for what the host does, and the order of the lines decides what the kernel logs.

Each level holds every rule of the level below it, and the overlays add or remove rules on top of whichever level you pick.

```mermaid
flowchart LR
    accTitle: L4 Detail -- Ruleset layers
    accDescr: The low, medium and high levels are cumulative. One level and any of the webserver, edge and container-host overlays render into one rules file.

    subgraph levels["Levels"]
        direction LR
        low["low"] --> medium["medium"] --> high["high"]
    end

    subgraph overlays["Overlays"]
        direction LR
        web["webserver"] ~~~ edge["edge"] ~~~ ctr["container-host"]
    end

    rules[("Rules file")]

    overlays -->|any overlay| rules
    levels -->|one level| rules

    classDef default fill:#F8FAFC,stroke:#64748B,stroke-width:1px,color:#0F172A
    classDef store fill:#DDF3EC,stroke:#00785A,stroke-width:1px,color:#0B3327
    classDef group fill:none,stroke:#64748B,stroke-width:1px,stroke-dasharray:2 4
    class rules store
    class levels,overlays group
```

*Figure 1. L4 Detail -- Ruleset layers. Each arrow inside Levels means "adds to".* Up: [L3 Components -- edge-integration-linux endpoint](architecture.md).

The template renders on the host, so the rules match what is there. The webserver overlay resolves account names to that host's uids, and every directory watch takes the cheaper form where the directory exists ([the cost of a rule](#the-cost-of-a-rule)). What each level and overlay holds is in [configuration](configuration.md#levels).

The role writes `/etc/audit/rules.d/hyperi-audit.rules` and leaves every other file in `rules.d` alone. `augenrules` merges the directory in `ls -1v` order and keeps the last `-b`, `-f`, `--backlog_wait_time` and `-e` it reads. `hyperi-audit.rules` sorts after `audit.rules` and every `NN-*.rules`, so its control lines win, and a local file that sorts after it can override them.

The kernel checks rules in load order and the first one that matches an event decides it, file watches included. `test/lab/semantics.sh` checks this on a live kernel, and it holds on kernels 6.12, 6.8 and 5.14. The template is laid out around three consequences:

- A `never` rule silences the `always` rules loaded after it, never those before. Every exclude sits above the rules it is meant to quiet.
- The execution rules sit above the excludes, so no exclude can hide a root exec from `/tmp`.
- Distro files in `rules.d` load before `hyperi-audit.rules`. A broad `never` rule in one of them silences the matching HyperI rules.

The ruleset is forked from Florian Roth's (Neo23x0) "Best Practice Auditd Configuration" (https://github.com/Neo23x0/auditd, Apache-2.0), then merged in turn with the public baselines:

Neo23x0 (Florian Roth) -> ACSC (ASD) OpenSCAP -> NIST -> DISA STIG -> alphagov/GDS -> US DoD -> SigmaHQ

Rules marked `sigma:` in the template exist so a SigmaHQ auditd rule can fire. Their detection logic comes from SigmaHQ (https://github.com/SigmaHQ/sigma) under the Detection Rule License 1.1. Keys carry MITRE ATT&CK technique ids where one maps.

## The cost of a rule

Every syscall walks each rule whose syscall mask includes it, so a rule with a wide mask costs the host on every syscall it makes. A `-w dir/` watch has every syscall in its mask and costs about 15 ns on each one. The same watch written as `-a always,exit -F arch=b64 -F perm=wa -F dir=` gets a mask of just the syscalls `perm=` covers, at about a quarter of that.

The role stats each watched directory at deploy time and writes the cheaper form where it exists. A missing directory cannot take a `dir=` rule, so it keeps the `-w` form.

The table gives the median cost of one `getppid` call, the cheapest syscall there is, so the figure is the rule walk alone. `test/lab/bench.sh` produced it in lab VMs, and re-running it there gives the figure for your kernel.

| Ruleset | Debian 13, kernel 6.12 | Rocky 9, kernel 5.14 |
|---|---|---|
| Audit on, no rules | about 150 to 220 ns | about 150 to 220 ns |
| `low` | 352 ns | 391 ns |
| `medium` | 551 ns | 596 ns |
| `high` | 626 ns | 734 ns |

Event volume matters more than the walk. Per-connection logging (`medium` and `high`, key `T1071_connect4`) is the largest source: at about 30K connects a second the backlog overflowed and over 100K events were lost, and with the `edge` overlay none were. `--backlog_wait_time 0` makes an overflow drop events rather than stall every process on the host.

## Adding a rule

Most mistakes here leave the ruleset loading cleanly while a detection goes quiet, so the kernel test is the check that counts.

1. Give every new syscall a line to itself. An unknown syscall name makes `auditctl` drop the whole rule, and the `-i` at the top hides the error, so appending to a working `-S` list deletes that rule on older kernels.
2. Key it `T<MITRE technique>_<what>`, such as `T1059_root_tmp`. Use a plain name, such as `audittools`, where no technique fits.
3. Keep every existing key. Keys are the output contract: rename one and every search and alert on it goes blind.
4. Where a SigmaHQ rule matches on a key name, put both keys on the rule (`-k T1071_connect4 -k network_connect_4`). Two keys cost nothing extra.
5. Put a `never` rule above every `always` rule it is meant to silence.
6. Watch a directory with the `wdir()` macro and add the path to `roles/hyperi_audit/vars/main.yml`. The render fails on a path missing from that list.
7. Most selective field first. The kernel stops at the first field that fails.
8. Add a row to `DETECTIONS` in `test/test_kernel.py` with a trigger, then run it in a lab VM or let the CI kernel job run it ([test/README.md](../test/README.md)).
