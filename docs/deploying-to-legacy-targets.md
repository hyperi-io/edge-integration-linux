# Deploying to legacy targets

Current `ansible-core` cannot drive the Python that el6-era hosts ship, so you pin an older Ansible on the control node, the machine you deploy from. `uvx` runs the pinned Ansible, and the Python it needs, in a throwaway environment:

```sh
# el6-era targets
uvx --python 3.10 --from ansible==5.10 ansible-playbook -i environments/<your-inventory> site.yml

# current targets: no pin
ansible-playbook -i environments/<your-inventory> site.yml
```

This needs [`uv`](https://docs.astral.sh/uv/) on the control node and nothing else. Keep legacy hosts in an inventory of their own, so each run uses one Ansible.

`ansible==5.10` bundles `ansible-core` 2.12, the last line that reaches those hosts and the floor the role declares in `roles/hyperi_audit/meta/main.yml`. A newer Ansible does not fix an old target, it stops reaching it.

`--python 3.10` matters as much. `ansible-core` 2.12 predates the import-hook change in CPython 3.12, so on a newer interpreter it installs and then fails at run time with `'_AnsiblePathHookFinder' object has no attribute 'find_spec'`.

## Old SSH key exchange

Current OpenSSH turns off the key-exchange algorithms old hosts offer, so the connection fails with `no matching key exchange method found`, naming what the host offered. Turn on that one algorithm for the run rather than weakening the control node's SSH config:

```sh
ansible-playbook -i environments/<your-inventory> site.yml \
    --ssh-common-args='-o KexAlgorithms=+<algorithm from the error>'
```

On rsyslog below 7 the role writes the legacy forwarder template, and RELP is not available ([transport](transport.md)).
