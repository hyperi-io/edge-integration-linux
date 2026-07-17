# HyperI audit collector test harness - Enterprise Linux bake image (dnf/yum).
# Modern EL (Rocky/Alma/Oracle 8+/9/10, Amazon Linux 2023): python3, sudo,
# procps-ng (the role reads `ps`), rsyslog and audit via dnf. Pre-installed so
# the per-test converge is config-only and fast. EOL EL (el6/el7) uses python2 +
# yum + the CentOS vault / OL repos - a separate bake variant (best-effort).
ARG BASE=rockylinux:9
FROM ${BASE}
RUN dnf -y install python3 sudo procps-ng rsyslog audit \
 && dnf clean all
