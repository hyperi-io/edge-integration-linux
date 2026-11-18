# Supported distributions

The role supports current Linux releases and end-of-life ones back to RHEL and CentOS 6. Unpatched, long-lived hosts are the ones that most need auditing, so reaching them is deliberate.

[`test/matrix.yml`](../test/matrix.yml) is the source of truth, and this table is its prose view. The harness uses no licensed images: Rocky, Alma and Oracle Linux stand in for RHEL, and openSUSE Leap for SLES.

| Release | Bucket | Test image | Notes |
|---|---|---|---|
| Ubuntu 26.04, 24.04 | current | `ubuntu:26.04`, `ubuntu:24.04` | |
| Debian 13, 12 | current | `debian:13`, `debian:12` | Debian 13 ships audit 4, which loads rules from a separate unit. The role runs `augenrules --load` itself. |
| Rocky 9, 10 | current | `rockylinux/rockylinux:9`, `:10` | |
| AlmaLinux 9 | current | `almalinux:9` | |
| Amazon Linux 2023 | current | `amazonlinux:2023` | |
| openSUSE Leap 15.6 | current | `opensuse/leap:15.6` | Its `python3` is 3.6, so the harness points Ansible at `python3.11`. |
| RHEL and CentOS 7 | end of life | `oraclelinux:7` | |
| Ubuntu 20.04, 18.04 | end of life | `ubuntu:20.04`, `ubuntu:18.04` | |
| RHEL and CentOS 6 | end of life | `oraclelinux:6` | No arm64 image. rsyslog 5, so the legacy template and no RELP. |

The end-of-life bucket runs best-effort in CI and does not pass. Its hosts ship a `python3` older than current `ansible-core` drives, which is the same limit you meet deploying to them ([deploying to legacy targets](deploying-to-legacy-targets.md)).

Gaps in the matrix, which are not statements of non-support:

- EL 8 (Rocky, Alma or Oracle Linux 8) has no entry, so nothing tests it.
- Licensed RHEL, SLES and Ubuntu Pro images are never used.
- The harness runs no kernel. Rule loading and detections are tested on Ubuntu in CI, and rule order on Debian 13, Ubuntu 24.04 and Rocky 9 in the lab ([test/README.md](../test/README.md)).

Where an old release needs an old tool, such as `ansible==5.10` on the control node for el6, the pin stays. A newer version will not install on that release, or will not reach it, so upgrading the pin breaks every host on it. Moving the support floor is a separate decision, and it does not license upgrading the pins of a release still in range.

RHEL and CentOS 5 are not supported. el5 never deployed without hand-built Python RPMs, an old Ansible and per-host SSH cipher changes, and no safe or maintained container image of it exists. el6 is the floor.
