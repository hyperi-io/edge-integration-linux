# Enterprise Linux target image for dnf distros (EL8+, Amazon Linux 2023).
# Bakes in python3, procps-ng (the role reads `ps`), rsyslog and audit so each
# converge is config-only. EOL EL (yum) uses Dockerfile.el-yum.
# BASE comes from matrix.yml.
ARG BASE
FROM ${BASE}
RUN dnf -y install python3 sudo procps-ng rsyslog audit \
 && dnf clean all
