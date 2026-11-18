# Test harness syslog receiver: one instance for the whole run, listening for
# audit (TCP 12201), syslog (TCP 12205) and RELP (20514).
# The harness passes BASE with a Docker Hub mirror prefix on runners that have one.
ARG BASE=debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
FROM ${BASE}
RUN apt-get update \
 && apt-get install -y --no-install-recommends rsyslog rsyslog-relp \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /var/log/hyperi-received /var/spool/rsyslog
COPY rsyslog-receiver.conf /etc/rsyslog.conf
EXPOSE 12201 12205 20514
CMD ["rsyslogd", "-n", "-f", "/etc/rsyslog.conf"]
