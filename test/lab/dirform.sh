#!/usr/bin/env bash
# Compare the per-syscall cost of a directory watch written as -w against the
# same watch as an -a exit rule with perm=, which auditctl gives a narrowed mask.
set -uo pipefail

mkdir -p /etc/benchdir
for i in $(seq 1 40); do mkdir -p "/etc/benchdir/d${i}"; done

run_form() {
    local name="$1" file
    file="$(mktemp)"
    for i in $(seq 1 40); do
        if [[ "${name}" == w ]]; then
            echo "-w /etc/benchdir/d${i}/ -p wa -k bench"
        else
            echo "-a always,exit -F arch=b64 -F perm=wa -F dir=/etc/benchdir/d${i} -k bench"
        fi
    done > "${file}"
    auditctl -D > /dev/null
    auditctl -R "${file}" > /dev/null 2>&1
    printf '%-6s rules=%-3s %s\n' "${name}" "$(auditctl -l | grep -c bench)" "$(sudo -u "${SUDO_USER:-lab}" /tmp/bench | tr '\n' ' ')"
    rm -f "${file}"
}

auditctl -D > /dev/null
auditctl -e 1 > /dev/null
printf '%-6s rules=%-3s %s\n' none 0 "$(sudo -u "${SUDO_USER:-lab}" /tmp/bench | tr '\n' ' ')"
run_form w
run_form a
auditctl -l | head -2
auditctl -D > /dev/null
