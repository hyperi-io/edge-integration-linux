# Kernel lab

Throwaway VMs, each booting a distro kernel, for audit rules, detections and syscall benchmarks. The kernel audit subsystem is shared by every container on a host, so this work needs VMs.

`lab.py` runs QEMU with KVM inside a container on a remote Docker host, and reaches each VM over SSH through a jump host. Point it at your KVM host with three variables: `AUDITLAB_DOCKER_CONTEXT` (the Docker context), `AUDITLAB_JUMP` (`user@host` for the jump) and `AUDITLAB_CACHE` (an absolute path on that host for cloud images). The VM user is `lab` with passwordless `sudo`, and its key pair is generated into `.keys/`, which git ignores.

The `esh` entry boots Debian 13 for an EdgeStream Hub install: `up esh --mem 6144 --disk 30 --forward 12201`. Each ESH config change runs a full playbook, so ESH suits a long-lived lab receiver and the harness keeps rsyslog for per-test assertions.

```sh
python3 test/lab/lab.py up <distro>             # fetch and verify the cloud image, boot, wait for SSH
python3 test/lab/lab.py run <distro> -- <cmd>   # run a command in the VM
python3 test/lab/lab.py ssh-config <distro>     # print an SSH Host block, for ssh -F or ansible-playbook
python3 test/lab/lab.py down <distro>           # destroy the VM and its disk; --all for every VM
```

The distros it can boot are the keys of `DISTROS` in `lab.py`.

| Script | Run in the VM as root | Prints |
|---|---|---|
| `bench.sh [rules dir] [yes or no]` | With `bench.c` and the rendered rulesets in `/tmp` | For each ruleset: rules loaded, events and lost events for a fixed workload, and median ns per `getppid`, `open`, `stat`, `write`, `exec` and `connect` |
| `dirform.sh` | With `/tmp/bench` built | The cost of 40 directory watches as `-w` against the same watches as `-a ... perm= dir=` |
| `semantics.sh` | From an SSH session, so the shell has a login uid | One line per rule-order case, E1 to E7. `test_kernel.py` checks the expected answers. |

`bench.sh` loads each ruleset without its final `-e 2`, so the VM stays unlocked between runs. Render the rulesets with `test/render.yml` ([test/README.md](../README.md)).
