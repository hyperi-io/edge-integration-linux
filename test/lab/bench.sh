#!/usr/bin/env bash
# Bench every ruleset in /tmp/rules: syscall cost (bench.c) and events per workload.
# Run as root in a lab VM. Rulesets load without their final -e 2.
set -uo pipefail

LOGIN_USER="${SUDO_USER:-lab}"
LOG=/var/log/audit/audit.log
cd /tmp || exit 1

cc -O2 -o /tmp/bench /tmp/bench.c

workload() {
    local i
    for i in $(seq 1 40); do
        sudo -u "${LOGIN_USER}" sh -c 'ls /etc >/dev/null; cat /etc/hostname >/dev/null; grep -q root /etc/passwd; id >/dev/null; uname -a >/dev/null'
        sudo -u "${LOGIN_USER}" sh -c 'f=$(mktemp); chmod 600 "$f"; mv "$f" "$f.x"; rm -f "$f.x"'
        sh -c 'touch /var/tmp/wl; rm -f /var/tmp/wl; getent hosts localhost >/dev/null'
        systemd-run --quiet --wait -p User=nobody sh -c 'ls /tmp >/dev/null; id >/dev/null' >/dev/null 2>&1
    done
    sudo -u "${LOGIN_USER}" /tmp/bench >/dev/null
}

measure() {
    local name="$1" before after lost0 lost1 b
    lost0="$(auditctl -s | awk '/^lost/ {print $2}')"
    before="$(wc -l < "${LOG}")"
    workload
    sleep 3
    after="$(wc -l < "${LOG}")"
    lost1="$(auditctl -s | awk '/^lost/ {print $2}')"
    b="$(sudo -u "${LOGIN_USER}" /tmp/bench | tr '\n' ' ')"
    printf '%-22s rules=%-4s events=%-7s lost=%-6s %s\n' "${name}" "$(auditctl -l | grep -c '^-[aw] ')" \
        "$((after - before))" "$((lost1 - lost0))" "${b}"
}

mkdir -p /etc/benchdir
for i in $(seq 1 40); do mkdir -p "/etc/benchdir/d${i}"; touch "/etc/benchdir/f${i}"; done

RULES_DIR="${1:-/tmp/rules}"
BASELINES="${2:-yes}"

auditctl -D >/dev/null
if [[ "${BASELINES}" == yes ]]; then
auditctl -e 0 >/dev/null
measure off
auditctl -e 1 >/dev/null
measure empty

for kind in d f; do
    file="$(mktemp)"
    for i in $(seq 1 40); do
        if [[ "${kind}" == d ]]; then echo "-w /etc/benchdir/d${i}/ -p wa -k bench"; else echo "-w /etc/benchdir/f${i} -p wa -k bench"; fi
    done > "${file}"
    auditctl -D >/dev/null
    auditctl -R "${file}" >/dev/null 2>&1
    measure "synthetic-40${kind}"
    rm -f "${file}"
done
fi
auditctl -e 1 >/dev/null

for rules in "${RULES_DIR}"/*.rules; do
    stripped="$(mktemp)"
    grep -v '^-e 2' "${rules}" > "${stripped}"
    auditctl -D >/dev/null
    auditctl -R "${stripped}" >/dev/null 2>&1
    measure "$(basename "${rules}" .rules)"
    rm -f "${stripped}"
done

auditctl -D >/dev/null
