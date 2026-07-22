# edge-integration-linux

Ansible deployment that turns a Linux endpoint into an audit source for a central
syslog receiver. It installs and configures `auditd` and `rsyslog`, applies a
chosen audit ruleset, and forwards audit and system events to the receiver over
TCP - across current distros and end-of-life ones alike.

The receiver is any syslog daemon that accepts forwarded TCP syslog - HyperI's is
the [Edge Stream Hub](https://hyperi.io), but rsyslog, syslog-ng or any
equivalent works. The role assumes nothing about it beyond a reachable
`collector_address`.

Two names are in play and they genuinely differ: this repository is
`edge-integration-linux`, and the deployment artefact it builds is
`hyperi-collector-endpoint-linux-<version>.tar.gz`.

## Quick start

You need `ansible` on a control node. Nothing is installed on the endpoints
beyond their own distro's `rsyslog` and `audit` packages.

From a clone, or from an extracted deployment tarball, in the directory that
holds `site.yml`:

```sh
ansible-playbook --syntax-check -i environments/example site.yml
```

Expected output:

```
playbook: site.yml
```

That confirms ansible, the playbook and the inventory template all parse. Copy
`environments/example`, fill in your hosts and collector, and you are ready to
deploy - see [Deploying](#deploying).

## What it does, and why

The role installs `rsyslog` and `audit`, tunes `auditd.conf`, deploys an audit
ruleset, and writes an rsyslog drop-in that forwards to your collector. On
SELinux hosts it also permits the collector ports and installs a policy module
so rsyslog may read the audit log. The deployed footprint is deliberately small:
fewer moving parts means fewer inter-distro incompatibilities, fewer version
dependency breakages, and less local disk consumed.

Audit events travel `auditd -> file -> rsyslog`, not `audisp-remote`. audisp is
fragmented across the supported range - a separate daemon and plugin directory
in audit 2.x, merged into `auditd` in audit 3.x - whereas `rsyslog` is present
and stable on every target, and the collector is a syslog receiver that consumes
syslog-shaped lines. Full reasoning:
[ADR 0001](./docs/decisions/0001-auditd-to-file-to-rsyslog-not-audisp.md).

```text
  auditd
    |  writes
    v
  /var/log/audit/audit.log
    |  rsyslog imfile tails
    v
  rsyslog  <--- local system log sources
    |
    +-- omfwd TCP 12201 (audit)  --> Syslog receiver (HyperI Edge Stream Hub)
    +-- omfwd TCP 12205 (syslog) --> Syslog receiver (HyperI Edge Stream Hub)
```

Audit records go to TCP 12201, everything else to TCP 12205.

## Audit profiles

Three levels plus a use-case profile. Breadth costs host CPU and forwarding
bandwidth, so pick for the host rather than defaulting to the widest.

| Profile | Selected with | For | Trade-off |
|---|---|---|---|
| low | `hyperi_audit_level: low` | Constrained hosts, slow links | High-signal file and exec watches plus the cheapest kernel TTPs. The high-volume syscall auditing (per-connection network, DAC permission changes, user file deletion, IPC) is removed. |
| medium | `hyperi_audit_level: medium` (default) | The general fleet | Balanced host telemetry. The starting point unless you have a reason. |
| high | `hyperi_audit_level: high` | High-value hosts that can carry it | medium plus interpreter exec, the full setuid/DAC syscall family, IPC, recon tooling, data staging, session/PAM and third-party agents. Not for constrained or slow-link endpoints. |
| internet | `hyperi_audit_profile_override: internet` | Internet-facing edge hosts - web servers, reverse proxies, bastions | medium with per-connection network logging removed, on the assumption an edge NIPS and firewall already carry that telemetry. Everything else is retained. |

`hyperi_audit_profile_override` *replaces* the level's ruleset rather than
layering on it, so setting it makes `hyperi_audit_level` moot. The role warns
when you set both.

The rulesets themselves carry their lineage, their MITRE ATT&CK mappings and
their traps in the `# HISTORY.` header of each
`roles/hyperi_audit/files/hyperi-audit-*.rules` file. See
[ARCHITECTURE.md](./ARCHITECTURE.md) for how the profiles are put together.

## Configuration

Role variables, set in your inventory's `vars:` block or via `--extra-vars`.

| Variable | Default | Meaning |
|---|---|---|
| `collector_address` | none - **required** | IP or DNS name of the collector receiving forwarded events. The run fails immediately if unset. |
| `hyperi_audit_level` | `medium` | Audit profile: `low`, `medium` or `high`. Any other value fails the run. |
| `hyperi_audit_profile_override` | unset | Replaces the level's ruleset with a named use-case profile; `internet` is the one shipped. An unknown value fails the run. Formerly `hyperi_audit_use_case`. |
| `hyperi_audit_transport` | `tcp` | Transport: `tcp` (plain syslog, the default, works everywhere), `relp` (reliable), `syslog-tls` (encrypted) or `relp-tls` (both). The opt-ins and their trust models are in [docs/transport.md](./docs/transport.md). |
| `hyperi_audit_start_services` | `true` | `false` writes the configuration but does not enable, stop or start `auditd` and `rsyslog`. Used by the test harness to converge inside a container that has no init. |

The transport is **plaintext by default**. Two opt-ins sit on top: `relp` adds
reliable, acknowledged delivery (to any RELP receiver) and `syslog-tls` adds
encryption; `relp-tls` does both - see [docs/transport.md](./docs/transport.md).
HyperI's own receivers gain RELP ingest in a future release
([#2](https://github.com/hyperi-io/edge-integration-linux/issues/2)); RELP
reaches any standard RELP receiver today.

## Deploying

Copy the inventory template, name the copy for your site, and fill in the hosts
and `collector_address`:

```sh
cp environments/example environments/mysite
```

`environments/example` is YAML and documents its own placeholders. A filled-in
inventory with a profile and credentials looks like:

```yaml
all:
  hosts:
    "10.0.0.11":
    "10.0.0.12":
  vars:
    collector_address: "10.0.0.9"
    hyperi_audit_level: "high"
    ansible_user: "user"
    ansible_password: "password"
```

Then deploy:

```sh
ansible-playbook -i environments/mysite site.yml
```

Useful variations:

- Credentials outside the inventory file:
  `--extra-vars "ansible_user=user ansible_password=password"`
- Prompt for the privilege escalation password: `-K` (the role escalates to root)
- Skip SSH host key checking:
  `--ssh-common-args='-o StrictHostKeyChecking=no'`

### Building the deploy tarball (maintainers)

`./build-tarball.sh` produces the customer artefact from committed state using
`git archive`. The script is `export-ignore`d, so it is not present in the
tarball itself - this section is for people working in the repository.

## Supported distributions

The automatable floor is CentOS/RHEL 6, and current mainstream distros are
supported alongside an end-of-life bucket. [`test/matrix.yml`](test/matrix.yml)
is the source of truth for what is actually tested; the prose view, the
supported floor and the known gaps are in
[docs/SUPPORTED-DISTROS.md](./docs/SUPPORTED-DISTROS.md).

The oldest targets constrain the *control node*, not just the endpoint: their
Python predates what current `ansible-core` will drive, so deploying to them
needs a pinned, older ansible on the machine you deploy from. A python or
library version error on an old target is almost always this, and an old
endpoint may also refuse a modern SSH key exchange. Both have one-line answers
in [docs/deploying-to-legacy-targets.md](./docs/deploying-to-legacy-targets.md).

## Testing

[`test/`](test/) is a Docker harness: a persistent rsyslog receiver plus
disposable per-distro containers, driven by pytest. It converges the role
config-only, seeds a marker into `audit.log`, and asserts it reaches the
receiver. It needs only `docker` and `uv`; run it with `test/run.sh`.

Read [test/README.md](./test/README.md) before trusting a green run - it is
explicit about what the harness does not cover.

## Versioning

Semantic Versioning and Changelog applied as per:
https://semver.org/
https://www.gitkraken.com/gitkon/semantic-versioning-git-tags
https://keepachangelog.com

## Links

- [ARCHITECTURE.md](./ARCHITECTURE.md) - how the pieces fit together
- [ADR 0001](./docs/decisions/0001-auditd-to-file-to-rsyslog-not-audisp.md) - why `auditd -> file -> rsyslog`, not audisp
- [docs/SUPPORTED-DISTROS.md](./docs/SUPPORTED-DISTROS.md) - the distro range and why EOL releases are in it
- [docs/deploying-to-legacy-targets.md](./docs/deploying-to-legacy-targets.md) - deploying to old targets from a modern control node
- [test/README.md](./test/README.md) - the test harness
- [CHANGELOG.md](./CHANGELOG.md)
- [LICENSE](./LICENSE) - Apache License 2.0
