# Tests

Docker test harness for the hyperi_audit Ansible role.

Two suites test the role, because no single environment can. The Docker harness converges the role on every distro in the matrix and proves the forwarding path, but containers share the host's kernel audit and cannot load a rule. The kernel tests load every rendered ruleset into a disposable VM's kernel and fire the detections.

## The Docker harness

It needs Docker and [`uv`](https://docs.astral.sh/uv/). `run.sh` syncs the locked Python environment, installs the Ansible collections into `test/collections`, and passes its arguments to pytest:

```sh
./run.sh                      # every distro in matrix.yml
./run.sh -m 'not eol'         # current distros only
./run.sh -k rocky             # a subset
./run.sh 'test_forwarding.py::test_audit_forwarding[ubuntu-24.04]'
```

One rsyslog receiver container runs for the whole session and listens on TCP 12201 and 12205 and RELP 20514. Each distro is baked into an image with `python3`, rsyslog and audit installed, started idle, converged over `docker exec` with `hyperi_audit_start_services: false`, checked and removed. Distros run one at a time, so the receiver's log stays unambiguous.

| File | Checks |
|---|---|
| `test_forwarding.py` | On every distro: the `medium` ruleset lands and ends in `-e 2`, the forwarder names the receiver and port 12201, `rsyslogd -N1` is clean, and a seeded `audit.log` line reaches the receiver exactly once. |
| `test_profiles.py` | On one current distro: each level and overlay deploys the keys it should and none it should not, `collector_address` still names the receiver, and 16 bad inputs each fail with the right message. |
| `test_transports.py` | On Debian 13, Ubuntu 24.04 and Rocky 9: each of `relp`, `relp-tls` and `syslog-tls` installs its package and passes `rsyslogd -N1`. `relp` is also delivered through the receiver's `imrelp` listener. |

The harness does not cover four things, and a passing run says nothing about them:

- No rule is loaded, so nothing here shows a rule loads or fires. The kernel tests cover that.
- The service tasks never run, because the containers have no init. Restarts, the `RefuseManualStop` drop-in and the locked-kernel path go untested here.
- auditd never starts, so nothing here shows auditd accepts the `auditd.conf` the role wrote.
- The TLS transports stop at config validity. A handshake needs certificates on both ends, and `anon` needs ciphers current crypto policies turn off.

`matrix.yml` lists each distro: `family` (`el`, `deb` or `suse`) picks the bake Dockerfile in `images/`, `eol` marks the best-effort bucket, `platform: linux/amd64` skips an image on an arm64 host, and `python` points Ansible at another interpreter. Set `HYPERCI_DOCKERHUB_MIRROR` to pull Docker Hub images through a mirror.

## The kernel tests

`test_kernel.py` loads audit rules into the kernel it runs on, through `sudo`, and flushes them after. It skips unless `HYPERI_AUDIT_KERNEL_TESTS=1`, and belongs in a disposable VM with auditd running:

```sh
env HYPERI_AUDIT_KERNEL_TESTS=1 uv run --locked pytest -m kernel test_kernel.py
```

It renders six level and overlay combinations with `render.yml` and loads each rule on its own. A rejection fails the test unless the host lacks what the rule names: a missing path, no SELinux, or a syscall newer than its `auditctl`. It then fires ten detections at each level, as the login user with a login uid set, and checks each key logs where it should and stays silent where it should not. Last, it runs `lab/semantics.sh` and checks the kernel decides rule order the way the template assumes.

## CI

`.github/workflows/test-harness.yml` runs on every pull request and every push to `main`:

| Job | Runs |
|---|---|
| `lint` | `ansible-lint` (production profile), `ruff`, `ty`, `shellcheck`, `hadolint`, `actionlint` |
| `kernel` | `test_kernel.py` on a GitHub-hosted Ubuntu runner, which is a disposable VM |
| `harness (current)` | `./run.sh -m 'not eol'`, required |
| `harness (eol)` | `./run.sh -m eol`, best-effort and allowed to fail |

The jobs run on GitHub-hosted runners. Setting the repository variable `GH_RUNNER_MODE` to `self-hosted` moves `lint` and `harness` to self-hosted runners, except on pull requests from forks.

## The lab

`lab/` boots throwaway VMs for work the kernel job cannot do: other kernels, syscall benchmarks and rule-order probes. [lab/README.md](lab/README.md) has the commands.
