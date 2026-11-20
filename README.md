# edge-integration-linux

Linux endpoint audit for EdgeStream Hub and Syslog destinations.

> **Agents are a last resort.** Nobody running IT infrastructure wants yet another agent on every host. So we collect in this order, and drop to the next only where the one before cannot reach:
>
> 1. Agentless: what the platform already sends, set up centrally. Windows Event Forwarding, syslog.
> 2. Platform-native, opinionated and automated: the platform's own logging, configured and deployed by us. Sysmon and the Windows audit policy (edge-integration-windows), auditd and rsyslog (edge-integration-linux), Endpoint Security and the unified log (edge-integration-macos).
> 3. An agent, for what neither reaches: hosts outside a domain, log files, and channels WEF cannot carry, such as DNS server analytic logging. Ours is hyperi-agent. Third-party agents a site already runs, such as Elastic Beats, are taken natively too.

[![CI](https://github.com/hyperi-io/edge-integration-linux/actions/workflows/test-harness.yml/badge.svg)](https://github.com/hyperi-io/edge-integration-linux/actions/workflows/test-harness.yml) [![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue?style=flat)](LICENSE)

## What it does

The `hyperi_audit` role installs and tunes auditd and rsyslog from the host's distro packages, renders an audit ruleset for that host, and forwards two streams to your receiver: audit records on TCP 12201 and everything else rsyslog sees on TCP 12205. It adds its rules beside whatever the host already has, and reaches back to RHEL 6 because the oldest hosts are the ones that most need watching.

- Three cumulative ruleset levels, `low`, `medium` and `high`, keyed by MITRE ATT&CK technique, with SigmaHQ's keys added where its auditd rules match on them.
- Overlays for web servers, internet-facing hosts and container hosts.
- Plain TCP by default, with syslog over TLS, RELP, and RELP over TLS as options.
- A disk-assisted queue per stream, so a receiver outage spools up to 1 GB of records rather than dropping them.
- Nothing installed beyond distro packages, and no agent on the host.
- Each level as a plain auditd rules file in [rules/](rules/), for hosts you manage some other way ([how](docs/rulesets.md#using-a-rules-file-on-its-own)).

EdgeStream Hub is HyperI's syslog receiver (https://hyperi-io.github.io/edgestream-hub/). Any receiver that takes syslog over TCP works.

## Quick start

You need Ansible on the machine you deploy from, and SSH access to each host as an account that can `sudo`. From a clone of this repo:

```sh
cp environments/example environments/mysite
# edit environments/mysite: your hosts and hyperi_audit_receiver_address
ansible-playbook --syntax-check -i environments/mysite site.yml
```

The check prints `playbook: site.yml`. Then deploy:

```sh
ansible-playbook -i environments/mysite site.yml -K
```

[Getting started](docs/getting-started.md) walks one host through it and shows how to check records reach the receiver.

## Configuration

Most deployments set two or three of these. Every variable is in [docs/configuration.md](docs/configuration.md).

| Variable | Default | Sets |
|---|---|---|
| `hyperi_audit_receiver_address` | none, required | The receiver's host name or IP. |
| `hyperi_audit_level` | `medium` | `low`, `medium` or `high`. |
| `hyperi_audit_use_cases` | `[]` | Overlays: `webserver`, `edge`, `container-host`. |
| `hyperi_audit_transport` | `tcp` | `tcp`, `syslog-tls`, `relp` or `relp-tls`. |
| `hyperi_audit_port_audit`, `hyperi_audit_port_syslog` | `12201`, `12205` | The receiver's ports for each stream. |

Read [security considerations](docs/security-considerations.md) before production: the default transport is cleartext, and the role locks the host's audit rules until reboot.

## Documentation

- [docs/README.md](docs/README.md) maps every page.
- [Architecture](docs/architecture.md) and [rulesets](docs/rulesets.md) explain how it works.
- [Deploying to a fleet](docs/deploying-to-a-fleet.md) and [legacy targets](docs/deploying-to-legacy-targets.md) cover rollout.
- [Supported distributions](docs/supported-distros.md) lists what is tested.
- [CHANGELOG.md](CHANGELOG.md) records each release.

## Getting help

Open an issue at https://github.com/hyperi-io/edge-integration-linux/issues.

## Contributing

Changes are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) has the lint and test commands, and what to watch for in the ruleset.

## Licence

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
