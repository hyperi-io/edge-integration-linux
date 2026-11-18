# Test harness syslog receiver, listening for audit (TCP 12201), syslog (12205),
# syslog over TLS (6514, a CA-signed cert for its container name) and RELP (20514).
# The harness passes BASE with a Docker Hub mirror prefix on runners that have one.
ARG BASE=debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
FROM ${BASE}
RUN apt-get update \
 && apt-get install -y --no-install-recommends rsyslog rsyslog-relp rsyslog-gnutls openssl \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /var/log/hyperi-received /var/spool/rsyslog /etc/hyperi-tls
WORKDIR /etc/hyperi-tls
RUN openssl req -x509 -newkey rsa:3072 -nodes -days 3650 -subj "/CN=hyperi test CA" \
      -keyout ca.key -out ca.pem \
 && openssl req -newkey rsa:3072 -nodes -subj "/CN=hyperi-audit-receiver" \
      -keyout server.key -out server.csr \
 && printf 'subjectAltName=DNS:hyperi-audit-receiver\n' > san.ext \
 && openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
      -days 3650 -extfile san.ext -out server.pem \
 && chmod 0644 ca.pem server.pem && chmod 0600 server.key ca.key
COPY rsyslog-receiver.conf /etc/rsyslog.conf
EXPOSE 12201 12205 6514 20514
CMD ["rsyslogd", "-n", "-f", "/etc/rsyslog.conf"]
