# HyperI Linux audit collector - test harness central syslog receiver.
# One instance persists across the whole test run; each OS-under-test forwards
# its audit (12201) + syslog (12205) here. Ports the central collector of the
# old VM test regime (which used a long-lived collector VM).
#
# Debian trixie per the HyperI container standard (never Alpine/musl). rsyslog
# is a plain distro package here - no glibc-wheel concern - and debian-slim is
# multi-arch (arm64 + amd64) just like the rest of the matrix.
FROM debian:trixie-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends rsyslog rsyslog-relp \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /var/log/hyperi-received /var/spool/rsyslog
COPY rsyslog-receiver.conf /etc/rsyslog.conf
EXPOSE 12201 12205 20514
CMD ["rsyslogd", "-n", "-f", "/etc/rsyslog.conf"]
