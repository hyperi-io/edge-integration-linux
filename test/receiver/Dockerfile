# HyperI Linux audit collector - test harness central syslog receiver.
# One instance persists across the whole test run; each OS-under-test forwards
# its audit (12201) + syslog (12205) here. Alpine + rsyslog = tiny, fast, and
# native on both arm64 and amd64. Ports the central collector of the old VM
# test regime (which used a long-lived collector VM).
FROM alpine:3.20
RUN apk add --no-cache rsyslog \
 && mkdir -p /var/log/hyperi-received /var/spool/rsyslog
COPY rsyslog-receiver.conf /etc/rsyslog.conf
EXPOSE 12201 12205
CMD ["rsyslogd", "-n", "-f", "/etc/rsyslog.conf"]
