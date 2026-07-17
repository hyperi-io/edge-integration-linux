# Running an older ansible for older targets

Modern ansible-core cannot talk to an el6-era target: it needs a Python on the
endpoint that those releases do not ship. Pin an older ansible **on the control
node** instead - the machine you deploy FROM - and point it at the old hosts.

Nothing needs installing. `uvx` fetches the pinned ansible, and the Python that
ansible itself needs, into a throwaway environment:

```sh
# el6-era targets
uvx --python 3.10 --from ansible==5.10 ansible-playbook \
    -i environments/<your-inventory> site.yml

# current targets - the default, no pin needed
ansible-playbook -i environments/<your-inventory> site.yml
```

Requires [`uv`](https://docs.astral.sh/uv/) on the control node. Nothing else.

## Why the pins are what they are

| Target | ansible | Why |
|---|---|---|
| el6-era | `5.10` (ansible-core 2.12) | The last line that still speaks to those endpoints |
| current | whatever is installed | No pin needed |

`--python 3.10` is not optional for the pinned line. ansible-core 2.12 predates
the CPython import-hook change in 3.12, so it installs cleanly against a newer
interpreter and then fails at run time with
`'_AnsiblePathHookFinder' object has no attribute 'find_spec'`. Pinning the
interpreter avoids it; `uv` downloads that interpreter itself.

These pins are **frozen**. See
[../docs/SUPPORTED-DISTROS.md](../docs/SUPPORTED-DISTROS.md) - a newer ansible
does not fix an old target, it just stops reaching it.

## Old-cipher targets

An old endpoint may refuse a modern SSH handshake: current OpenSSH disables the
key-exchange algorithms those releases offer. The symptom is
`no matching key exchange method found`, and the error names the algorithms the
target actually offered.

Re-enable the one it asks for on the command line rather than weakening the
control node's global SSH config:

```sh
ansible-playbook -i environments/<your-inventory> site.yml \
    --ssh-common-args='-o KexAlgorithms=+<algorithm from the error>'
```
