# Getting started

By the end of this page one Linux host runs the `medium` ruleset and forwards its audit records and syslog to your receiver. Each step shows what you should see, so stop at the first one that differs and look it up in [troubleshooting](troubleshooting.md).

You need three things:

- A control node with Ansible, the machine you deploy from. `pipx install --include-deps ansible` installs it, with the `community.general` collection the role needs on SUSE.
- SSH key access from the control node to the host, as an account that can `sudo` to root.
- A syslog receiver the host can reach on TCP 12201 (audit) and 12205 (syslog). EdgeStream Hub works, and so does any rsyslog or syslog-ng listening on those ports.

For an el6 or el7 host, read [deploying to legacy targets](deploying-to-legacy-targets.md) first, because current Ansible cannot drive their Python.

Then deploy and check:

1. From a clone of this repo, copy the inventory template:

   ```sh
   cp environments/example environments/myhost
   ```

2. Edit `environments/myhost` down to one host and your receiver:

   ```yaml
   all:
     hosts:
       "203.0.113.10":
     vars:
       hyperi_audit_receiver_address: "203.0.113.9"
       ansible_user: "deploy"
   ```

3. Check that Ansible, the playbook and the inventory parse:

   ```sh
   ansible-playbook --syntax-check -i environments/myhost site.yml
   ```

   Expect `playbook: site.yml` and nothing else.

4. Deploy. `-K` asks for the `sudo` password:

   ```sh
   ansible-playbook -i environments/myhost site.yml -K
   ```

   Near the start the role logs what it chose, for example `Debian 13: level medium, overlays [], transport tcp, audit -> 203.0.113.9:12201, syslog -> 203.0.113.9:12205`. Near the end it logs `Kernel holds N of the M rules in /etc/audit/audit.rules`. The recap should show `failed=0` and `unreachable=0`.

5. Check the kernel holds the rules and has locked them. `-b` runs the command as root on the host:

   ```sh
   ansible all -i environments/myhost -b -K -m command -a "auditctl -s"
   ```

   Expect `enabled 2` in the output.

6. Make an audited change. Writing to `/etc/cron.d` fires key `T1053.003_cron` at every level:

   ```sh
   ansible all -i environments/myhost -b -K -m shell -a "touch /etc/cron.d/hyperi-probe && rm /etc/cron.d/hyperi-probe"
   ```

7. On the receiver, look for a record from the host carrying `key="T1053.003_cron"`. It arrives within a few seconds on the audit port.

The host is auditing and forwarding. Pick a different level or add overlays in [configuration](configuration.md), turn on TLS in [transport](transport.md), and roll out to more hosts with [deploying to a fleet](deploying-to-a-fleet.md).
