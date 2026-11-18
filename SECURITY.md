# Security Policy

## Reporting a vulnerability

Report privately through
[GitHub Security Advisories](https://github.com/hyperi-io/edge-integration-linux/security/advisories/new).
Please don't open a public issue for a vulnerability.

Tell us what you can: what the problem is, how to reproduce it, which distro and version you saw it on, and what an attacker could do with it. A partial report is still worth sending.

We aim to acknowledge within a few working days. Once there's a fix we'll credit you in the advisory unless you'd rather stay anonymous.

This is an Ansible role that runs as root on every endpoint in a fleet. It installs auditd and rsyslog, deploys an audit ruleset, and forwards audit and syslog to a receiver. The things worth reporting are:

- A way for a process on the endpoint to act without the ruleset logging it, where the docs say it would be logged.
- A deployment that leaves auditing off, rules unloaded, or the forwarder dropping records, without failing the run or saying so.
- A forwarder TLS setting that accepts a receiver it should reject.
- An inventory value that can break out of the rsyslog config or the ruleset.
- A file, temp path or permission the role creates that's broader than it needs.
- Anything in the tree that ships a credential, an internal hostname or a private registry URL. This repo is public.

Gaps in auditd, rsyslog or the kernel belong upstream with those projects. If our configuration makes one worse, that part is ours.

Fixes land on `main` and ship in the next release. There are no maintained release branches, so please check a problem still exists on `main` before reporting it.
