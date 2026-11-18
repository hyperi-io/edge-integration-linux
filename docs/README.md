# Documentation

The `hyperi_audit` role audits Linux hosts with auditd and forwards audit records and syslog to a syslog receiver. Start with getting started, then go where your question is.

Deploy it:

- [Getting started](getting-started.md): one host, deployed and checked.
- [Deploying to a fleet](deploying-to-a-fleet.md): batched rollout with a forwarding gate.
- [Deploying to legacy targets](deploying-to-legacy-targets.md): el6-era hosts from a current control node.
- [Uninstall](uninstall.md): removing the role's changes by hand.
- [Troubleshooting](troubleshooting.md): every failure and warning message, and the path to walk when records do not arrive.

Look it up:

- [Configuration](configuration.md): every variable, what each level and overlay holds, and the `auditd.conf` values.
- [Transport](transport.md): TLS, RELP, trust modes, certificates and ports.
- [Supported distributions](supported-distros.md): the tested range and its gaps.

Understand it:

- [Architecture](architecture.md): the parts on the host, how records flow, and why it is built this way.
- [Rulesets](rulesets.md): levels and overlays, rule order, the cost of a rule, and how to add one.
- [Security considerations](security-considerations.md): what the role changes on a host and what to protect.
- [Decisions](decisions/README.md): the architecture decision records.

To work on the role itself, read [CONTRIBUTING.md](../CONTRIBUTING.md).
