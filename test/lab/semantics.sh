#!/usr/bin/env bash
# Probe how the kernel combines exit-list rules and per-inode watch rules.
# Run as root from an ssh session (auid = the login user). Prints one line per case.
set -uo pipefail

LOGIN_USER="${SUDO_USER:-lab}"
RUN="r${RANDOM}"

load() {
    local file
    file="$(mktemp)"
    cat > "${file}"
    auditctl -D > /dev/null
    auditctl -R "${file}" > /dev/null 2>&1 || echo "  load warnings for: $(tr '\n' ' ' < "${file}")"
    rm -f "${file}"
}

count() {
    # Events for key $1 whose exe is $2, once auditd has caught up: the log is
    # in order, so the marker written now lands after them.
    local marker="settle_${RUN}_${RANDOM}"
    auditctl -m "${marker}" > /dev/null 2>&1
    for _ in $(seq 1 50); do
        tail -n 200 /var/log/audit/audit.log 2> /dev/null | grep -q "${marker}" && break
        sleep 0.1
    done
    ausearch -if /var/log/audit/audit.log -k "$1" --raw 2> /dev/null | grep -c "exe=\"$2\"" || true
}

# Exit 126 or 127 means the command never ran. false exits 1 by design.
as_user() {
    runuser -u "${LOGIN_USER}" -- "$@" > /dev/null
    (($? < 126)) || echo "as_user could not run: $*" >&2
}
as_daemon() {
    systemd-run --quiet --wait -p User=nobody "$@" > /dev/null
    (($? < 126)) || echo "as_daemon could not run: $*" >&2
}

report() { printf '%-4s %-60s %s\n' "$1" "$2" "$3"; }

auditctl -e 1 > /dev/null
# A login gives the user's commands an auid. Without one (a CI runner), set it
# as login does, so runuser children inherit it. printf is a builtin, so this
# shell sets its own loginuid, not a child's.
LOGIN_UID="$(id -u "${LOGIN_USER}")"
printf '%s' "${LOGIN_UID}" > /proc/self/loginuid 2> /dev/null || true

# Private copies of the tools the probes run, so exe= and path= name plain files
# whatever coreutils the host ships. A multicall build picks its tool by name.
P="$(mktemp -d /usr/local/lib/hprobe.XXXXXX)"
for t in true false cat head touch; do
    cp "$(readlink -f "$(type -P "${t}")")" "${P}/${t}"
done
chmod 0755 "${P}" "${P}"/*
trap 'rm -rf "${P}"' EXIT

# E1: always on the exit list, then never on the inode list for one binary.
load <<EOF
-a always,exit -F arch=b64 -S execve -F auid!=unset -F auid>=1000 -k E1_exit_${RUN}
-a never,exit -F arch=b64 -S execve -F path=${P}/true -F perm=x -k E1_never_${RUN}
EOF
as_user "${P}/true"
as_user "${P}/false"
report E1 "exit always + inode never: true logged? false logged?" "true=$(count E1_exit_${RUN} "${P}/true") false=$(count E1_exit_${RUN} "${P}/false")"

# E2: same two rules, inode never loaded first.
load <<EOF
-a never,exit -F arch=b64 -S execve -F path=${P}/true -F perm=x -k E2_never_${RUN}
-a always,exit -F arch=b64 -S execve -F auid!=unset -F auid>=1000 -k E2_exit_${RUN}
EOF
as_user "${P}/true"
as_user "${P}/false"
report E2 "inode never first, then exit always" "true=$(count E2_exit_${RUN} "${P}/true") false=$(count E2_exit_${RUN} "${P}/false")"

# E3: both on the exit list (exe= is not an inode rule), never first then always.
load <<EOF
-a never,exit -F arch=b64 -S execve -F exe=${P}/true -k E3_never_${RUN}
-a always,exit -F arch=b64 -S execve -F auid!=unset -F auid>=1000 -k E3_exit_${RUN}
EOF
as_user "${P}/true"
as_user "${P}/false"
report E3 "exit never (exe=) first, then exit always" "true=$(count E3_exit_${RUN} "${P}/true") false=$(count E3_exit_${RUN} "${P}/false")"

# E3b: always first, then never, both exit list.
load <<EOF
-a always,exit -F arch=b64 -S execve -F auid!=unset -F auid>=1000 -k E3b_exit_${RUN}
-a never,exit -F arch=b64 -S execve -F exe=${P}/true -k E3b_never_${RUN}
EOF
as_user "${P}/true"
report E3b "exit always first, then exit never (exe=)" "true=$(count E3b_exit_${RUN} "${P}/true")"

# E4: exit-list never against an inode watch on the same binary.
load <<EOF
-a never,exit -F arch=b64 -S execve -F exe=${P}/true -k E4_never_${RUN}
-w ${P}/true -p x -k E4_watch_${RUN}
EOF
as_user "${P}/true"
report E4 "exit never (exe=) vs inode watch -p x" "true=$(count E4_watch_${RUN} "${P}/true")"

# E5: shadow readers excluded by exe, inode never before the inode watch.
load <<EOF
-a never,exit -F path=/etc/shadow -F exe=${P}/cat -k E5_never_${RUN}
-w /etc/shadow -p r -k E5_watch_${RUN}
EOF
"${P}/cat" /etc/shadow > /dev/null
"${P}/head" -1 /etc/shadow > /dev/null
report E5 "path never (exe=cat) then -w shadow -p r: cat? head?" "cat=$(count E5_watch_${RUN} "${P}/cat") head=$(count E5_watch_${RUN} "${P}/head")"

# E6: a session exclude (auid!=unset) must not hide a daemon (auid unset).
load <<EOF
-a always,exit -F arch=b64 -S execve -F euid=65534 -k E6_daemon_${RUN}
-a never,exit -F arch=b64 -S execve -F auid!=unset -F auid>=1000 -F path=${P}/true -F perm=x -k E6_never_${RUN}
EOF
as_daemon "${P}/true"
report E6 "session exclude vs daemon exec (auid unset)" "daemon_true=$(count E6_daemon_${RUN} "${P}/true")"

# E7: a directory watch with -p wa ignores reads.
load <<EOF
-w /etc/cron.d/ -p wa -k E7_dir_${RUN}
EOF
"${P}/cat" /etc/cron.d/* > /dev/null 2>&1 || true
"${P}/touch" /etc/cron.d/e7probe && rm -f /etc/cron.d/e7probe
report E7 "dir watch -p wa: read events, write events" "read=$(count E7_dir_${RUN} "${P}/cat") touch=$(count E7_dir_${RUN} "${P}/touch")"

auditctl -D > /dev/null
