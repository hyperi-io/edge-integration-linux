# Deploying to a fleet

Roll the role out in batches, one distro family at a time, and stop at the first host whose audit stream does not reach the receiver. Get one host working first with [getting started](getting-started.md).

The batch is the unit of risk. The role restarts auditd and rsyslog on every host it changes, and the tasks branch on the rsyslog and audit versions they find, so a batch that mixes el7 and Debian 13 runs two code paths at once and hides which one broke.

Stage the rollout:

1. A non-production canary: one host per distro and version you run. Deploy, reboot, and check the receiver gets records after the reboot, when the rules from the run are live.
2. A production canary: one low-criticality host per family.
3. A small ring of about 5% of each family.
4. Wider rings of 20%, then the rest, ordered by criticality with the most critical hosts last.

Move to the next stage once every batch in the current one gets through the gate below. Re-runs are safe: the role changes what differs, and restarts services when their config changed. When a batch fails, fix the cause and re-run the same `--limit`. Nothing reverses a deploy, so a host you need back as it was goes through [uninstall](uninstall.md) by hand.

## One play with a ramp and a hard stop

Copy `site.yml` to `fleet.yml` and add the ramp, the hard stop and the gate:

```yaml
- name: Deploy the audit ruleset and forwarder in batches
  hosts: all
  become: true
  serial: [1, 5, "20%"]
  max_fail_percentage: 0
  roles:
    - role: hyperi_audit
  post_tasks:
    - name: Read the service states
      ansible.builtin.service_facts:

    - name: Check auditd and rsyslog are running
      ansible.builtin.assert:
        that:
          - ansible_facts['services']['auditd.service']['state'] == 'running'
          - ansible_facts['services']['rsyslog.service']['state'] == 'running'

    - name: Check the receiver's audit port is reachable
      ansible.builtin.wait_for:
        host: "{{ hyperi_audit_receiver_address }}"
        port: "{{ hyperi_audit_port_audit }}"
        timeout: 15

    - name: Make an audited change, key T1053.003_cron
      ansible.builtin.shell: touch /etc/cron.d/hyperi-probe && rm /etc/cron.d/hyperi-probe
      changed_when: false
```

`serial` runs the play in batches of 1, then 5, then 20% of the hosts. `max_fail_percentage: 0` aborts the play when any host in a batch fails, a failed `post_tasks` step included, so a red gate stops the next batch.

The last step makes an event, and the gate is complete once you check it arrived. How depends on your receiver. For an rsyslog receiver that writes remote audit lines to a file, add a step like this to the `post_tasks`:

```yaml
    - name: Check the event reached the receiver
      ansible.builtin.command: grep -q "{{ ansible_facts['hostname'] }}.*T1053.003_cron" /var/log/remote/audit.log
      delegate_to: receiver.example.com
      register: seen
      until: seen.rc == 0
      retries: 6
      delay: 5
      changed_when: false
```

el6 runs SysV init, where `service_facts` names the services `auditd` and `rsyslog`, without `.service`.

Put each host in three kinds of group: environment, criticality and distro family. Then pick each run's hosts by intersecting them with `--limit`, where `:` is union, `:&` intersection and `:!` exclusion.

```yaml
all:
  vars:
    hyperi_audit_receiver_address: "receiver.example.com"
  children:
    staging:
      hosts:
        canary-el9.stg.example.net:
    prod:
      hosts:
        app01.example.net:
        app42.example.net:
    el9:
      hosts:
        canary-el9.stg.example.net:
        app01.example.net:
        app42.example.net:
    tier_low:
      hosts:
        app01.example.net:
    tier_high:
      hosts:
        app42.example.net:
```

```sh
ansible-playbook -i environments/prod fleet.yml --limit 'staging:&el9'
ansible-playbook -i environments/prod fleet.yml --limit 'prod:&el9:&tier_low'
ansible-playbook -i environments/prod fleet.yml --limit 'prod:&el9:!tier_high'
ansible-playbook -i environments/prod fleet.yml --limit 'prod:&el9:&tier_high'
```

Per-group settings, such as `hyperi_audit_level: low` for constrained hosts or `hyperi_audit_use_cases: [edge, webserver]` for internet-facing ones, go in `group_vars/<group>.yml` ([configuration](configuration.md)). el6-era hosts need a pinned Ansible on the control node, so run them separately ([deploying to legacy targets](deploying-to-legacy-targets.md)).
