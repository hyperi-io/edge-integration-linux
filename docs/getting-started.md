<!--
Project:      HyperI Linux audit collector
File:         docs/getting-started.md
Purpose:      Tutorial -- deploy the role to a single host and confirm it is
              auditing and forwarding to the collector.
License:      Apache-2.0
Copyright:    (c) 2026 HYPERI PTY LIMITED
-->

# Getting started

By the end of this page one Linux host is running `auditd` with a HyperI ruleset
and forwarding its audit stream to your collector. It is the on-rails happy path
for a single host; once it works, [deploying to a fleet](deploying-to-a-fleet.md)
scales it out.

Every step below produces a visible result. If a result does not match, stop and
resolve it before moving on.

## 1. Prerequisites

You drive the deploy from a **control node** -- your workstation or a jump host,
not the endpoint. On the control node you need `ansible`:

```sh
python3 -m pip install --user ansible
```

You also need, from the control node to the endpoint:

- SSH access to the endpoint, and an account there that can escalate to root
  (the role installs packages and edits `/etc`).
- The **address of your collector** -- an IP or DNS name the endpoint can reach.
  The role forwards audit records to it on TCP 12201 and general syslog on TCP
  12205; make sure both are open. `collector_address` is required and the run
  fails immediately without it.

Nothing is installed on the endpoint beyond its own distro's `rsyslog` and
`audit` packages.

> **Note:** the oldest supported endpoints constrain the control node too --
> their Python can be too old for current `ansible-core`. If you are targeting an
> end-of-life release, read [supported distributions](SUPPORTED-DISTROS.md) and
> [deploying to legacy targets](deploying-to-legacy-targets.md) first.

## 2. Write a one-host inventory

Copy the shipped template and name the copy for your host:

```sh
cp environments/example environments/myhost
```

Edit `environments/myhost` down to a single endpoint and your collector. It is
YAML:

```yaml
all:
  hosts:
    "203.0.113.10":
  vars:
    collector_address: "203.0.113.9"
    ansible_user: "deploy"
```

That is the minimum: one host, one `collector_address`, and the SSH user. The
role defaults to the `medium` audit profile, so you do not need to choose one
yet -- [configuration](configuration.md) covers the profiles when you want to.

## 3. Check the playbook and inventory parse

Before touching the host, confirm ansible, the playbook and your inventory all
load:

```sh
ansible-playbook --syntax-check -i environments/myhost site.yml
```

Expected output:

```
playbook: site.yml
```

Any other output is a parse error in your inventory -- fix it here, where it
costs nothing.

## 4. Deploy

Run the playbook against your host. `-K` prompts for the privilege-escalation
(sudo) password:

```sh
ansible-playbook -i environments/myhost site.yml -K
```

Ansible walks the tasks -- gather facts, install packages, probe versions, write
the ruleset and the rsyslog forwarder, tune `auditd.conf`, then restart the
services. The run ends with a recap:

```
PLAY RECAP *********************************************************************
203.0.113.10               : ok=NN   changed=NN   unreachable=0    failed=0
```

`unreachable=0` and `failed=0` is a clean deploy. If a package step fails on a
first run, it is usually a transient mirror -- the role already retries, so
re-run the command.

## 5. Verify

Three checks, each from the control node against your inventory. `-b` escalates
to root on the endpoint.

**auditd is running:**

```sh
ansible all -i environments/myhost -b -m command -a "systemctl is-active auditd"
```

Expected: `active`.

**The kernel accepted the ruleset:**

```sh
ansible all -i environments/myhost -b -m command -a "auditctl -s"
```

Expected: a status block reporting `enabled 1` or `enabled 2` (the role sets the
config immutable, so re-deployed hosts read `enabled 2`).

**The forwarder points at your collector:**

```sh
ansible all -i environments/myhost -b -m command -a "cat /etc/rsyslog.d/99-hyperi-rsyslog.conf"
```

Expected: an `omfwd` action targeting your `collector_address` on TCP 12201, and
another on 12205.

**An event reaches the collector.** The deploy itself escalated to root over
SSH, which `auditd` records as authentication and command events -- so records
are already flowing. The role sets `name_format=hostname`, so each record
carries the endpoint's hostname. On your collector, confirm audit records tagged
with that hostname are arriving on TCP 12201. To generate a fresh one on demand:

```sh
ansible all -i environments/myhost -b -m command -a "id"
```

The `sudo` escalation for that command produces an audit event that forwards
within a second or two.

## Next

One host is auditing and forwarding. To roll the same role out across many hosts
in controlled batches, continue to [deploying to a fleet](deploying-to-a-fleet.md).
To choose a heavier or lighter audit profile, or to see every role variable, see
[configuration](configuration.md).
