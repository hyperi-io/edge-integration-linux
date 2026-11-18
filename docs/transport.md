# Transport

Both streams travel as plain TCP syslog unless you pick otherwise. RELP adds acknowledged delivery, TLS adds encryption, and `relp-tls` does both. One variable picks the transport for both streams.

| `hyperi_audit_transport` | rsyslog action | Acknowledged | Encrypted | Package the role installs |
|---|---|---|---|---|
| `tcp` (default) | `omfwd` | no | no | none |
| `syslog-tls` | `omfwd` with the `gtls` driver | no | yes | `rsyslog-gnutls` |
| `relp` | `omrelp` | yes | no | `rsyslog-relp` |
| `relp-tls` | `omrelp` with `tls="on"` | yes | yes | `rsyslog-relp` |

Every transport gets the same disk-assisted queue per stream, so a receiver outage spools records to disk rather than dropping them. RELP closes the remaining gap: TCP syslog can lose the records in flight when a connection breaks, and RELP resends anything the receiver did not acknowledge.

EdgeStream Hub takes syslog over UDP, TCP and TLS, so use `tcp` or `syslog-tls` with it. RELP ingest is not in EdgeStream Hub yet, tracked in [issue #2](https://github.com/hyperi-io/edge-integration-linux/issues/2). Any rsyslog `imrelp` listener, syslog-ng or other RELP receiver takes `relp` and `relp-tls`.

RELP needs rsyslog 7 or later. On the rsyslog 5 and 6 hosts of the el6 era the role fails a RELP run and says to use `syslog-tls` or `tcp`. `syslog-tls` works there through the old directive syntax, which the role writes for you.

The role sends audit to `hyperi_audit_port_audit` (default 12201) and syslog to `hyperi_audit_port_syslog` (default 12205). Point both at the listener for the transport you picked: 6514 is the usual syslog over TLS port and 20514 the usual RELP port. On SELinux hosts the role labels any port that has no SELinux type yet as `syslogd_port_t`, so rsyslog can connect out on it.

## TLS trust is set by `hyperi_audit_tls_mode`

The mode decides whether the endpoint checks the receiver's certificate, and whether it presents one of its own.

| Mode | Endpoint checks the receiver | Endpoint presents a certificate | Needs |
|---|---|---|---|
| `anon` (default) | no | no | nothing |
| `server` | yes, against the CA and a name | no | `hyperi_audit_tls_ca_file` |
| `mutual` | yes, against the CA and a name | yes | CA, client certificate and key |

`relp-tls` takes `anon` or `mutual`. librelp negotiates mutual authentication for any authenticated mode, so the role rejects `relp-tls` with `server`.

Under `server` and `mutual` the endpoint accepts a receiver certificate only if the CA signed it and it carries the expected name. That name is `hyperi_audit_tls_permitted_peer`, or the receiver address when that is empty. A receiver addressed by IP needs `hyperi_audit_tls_permitted_peer` set, and the role fails the run without it.

`hyperi_audit_tls_permitted_peer` limits the endpoint's check of the receiver and nothing else. The receiver decides which endpoint certificates it accepts in its config.

`anon` encrypts but authenticates nobody, so an active man-in-the-middle can read the stream. Use it on a path you trust, such as a VPN, and use `server` or `mutual` anywhere else. It also needs anonymous Diffie-Hellman ciphers, which the default crypto policy on RHEL 8 and later disables. There the handshake fails with `No supported cipher suites have been found`.

The role reads certificate files from the paths you give it and never creates, copies or rotates them. Put them on each endpoint before the role runs, with your config management or your image build.

| File | Variable | Owner and mode |
|---|---|---|
| CA certificate | `hyperi_audit_tls_ca_file` | root, `0644` |
| Client certificate | `hyperi_audit_tls_client_cert` | root, `0644` |
| Client private key | `hyperi_audit_tls_client_key` | `0600` root, or `0640` root and the rsyslog group where rsyslog drops privileges (`syslog` on Ubuntu) |

One client certificate shared by every endpoint gives `mutual` with one file to rotate. Issue one per endpoint when the receiver must tell endpoints apart.

## Examples

Encrypted to EdgeStream Hub over a VPN, with no certificates:

```yaml
all:
  vars:
    hyperi_audit_receiver_address: "esh.example.com"
    hyperi_audit_transport: "syslog-tls"
    hyperi_audit_tls_mode: "anon"
    hyperi_audit_port_audit: "6514"
    hyperi_audit_port_syslog: "6514"
```

Encrypted, checking the receiver's certificate:

```yaml
all:
  vars:
    hyperi_audit_receiver_address: "receiver.example.com"
    hyperi_audit_transport: "syslog-tls"
    hyperi_audit_tls_mode: "server"
    hyperi_audit_tls_ca_file: "/etc/pki/hyperi/ca.pem"
    hyperi_audit_port_audit: "6514"
    hyperi_audit_port_syslog: "6514"
```

Acknowledged and encrypted to a RELP receiver, with a client certificate:

```yaml
all:
  vars:
    hyperi_audit_receiver_address: "relay.example.com"
    hyperi_audit_transport: "relp-tls"
    hyperi_audit_tls_mode: "mutual"
    hyperi_audit_tls_ca_file: "/etc/pki/hyperi/ca.pem"
    hyperi_audit_tls_client_cert: "/etc/pki/hyperi/client.pem"
    hyperi_audit_tls_client_key: "/etc/pki/hyperi/client.key"
    hyperi_audit_port_audit: "20514"
    hyperi_audit_port_syslog: "20514"
```

The rendered config lands in `/etc/rsyslog.d/99-hyperi-rsyslog.conf`. The role runs `rsyslogd -N1` on it and fails the run on a parse error.
