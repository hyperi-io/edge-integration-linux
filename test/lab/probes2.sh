#!/usr/bin/env bash
# Check the security review's kernel claims: setuid exec, execveat, unix-socket
# connect to a path watch. Run as root from an ssh session.
set -uo pipefail

LOGIN_USER="${SUDO_USER:-lab}"
RUN="p${RANDOM}"

load() {
    local file
    file="$(mktemp)"
    cat > "${file}"
    auditctl -D > /dev/null
    auditctl -R "${file}" > /dev/null 2>&1
    rm -f "${file}"
}

events() { ausearch --input-logs -k "$1" --raw 2> /dev/null | grep -c '^type=SYSCALL' || true; }

auditctl -e 1 > /dev/null

load <<EOF
-a always,exit -F arch=b64 -S execve -F euid=0 -F suid!=0 -k S1_old_${RUN}
-a always,exit -F arch=b64 -S execve -F euid=0 -C uid!=euid -k S1_new_${RUN}
EOF
sudo -u "${LOGIN_USER}" sudo -n true > /dev/null 2>&1
sudo -u "${LOGIN_USER}" passwd -S "${LOGIN_USER}" > /dev/null 2>&1
echo "S1 setuid exec by user: old(euid=0 suid!=0)=$(events "S1_old_${RUN}") new(uid!=euid)=$(events "S1_new_${RUN}")"

cp /usr/bin/true /dev/shm/probe-x && chmod 755 /dev/shm/probe-x
load <<EOF
-a always,exit -F arch=b64 -S execve -F dir=/dev/shm -k S2_execve_${RUN}
-a always,exit -F arch=b64 -S execveat -F dir=/dev/shm -k S2_execveat_${RUN}
EOF
sudo -u "${LOGIN_USER}" python3 -c 'import os; fd = os.open("/dev/shm/probe-x", os.O_RDONLY); os.execve(fd, ["x"], {})' > /dev/null 2>&1
echo "S2 fexecve from /dev/shm: execve-rule=$(events "S2_execve_${RUN}") execveat-rule=$(events "S2_execveat_${RUN}")"
load <<EOF
-a always,exit -F arch=b64 -F perm=x -F dir=/dev/shm -k S2_permx_${RUN}
EOF
auditctl -l | head -1
sudo -u "${LOGIN_USER}" /dev/shm/probe-x > /dev/null 2>&1
sudo -u "${LOGIN_USER}" python3 -c 'import os; fd = os.open("/dev/shm/probe-x", os.O_RDONLY); os.execve(fd, ["x"], {})' > /dev/null 2>&1
echo "S2b perm=x dir rule: execve+fexecve events=$(events "S2_permx_${RUN}") (2 = both caught)"
rm -f /dev/shm/probe-x

python3 -c 'import socket, os; p = "/run/probe.sock"; os.path.exists(p) and os.unlink(p); s = socket.socket(socket.AF_UNIX); s.bind(p); s.listen(); os.chmod(p, 0o666); import time; time.sleep(30)' &
SRV=$!
sleep 1
load <<EOF
-w /run/probe.sock -p rwa -k S3_watch_${RUN}
-a always,exit -F arch=b64 -S connect -F path=/run/probe.sock -k S3_connect_${RUN}
EOF
sudo -u "${LOGIN_USER}" python3 -c 'import socket; s = socket.socket(socket.AF_UNIX); s.connect("/run/probe.sock")' > /dev/null 2>&1
echo "S3 unix connect: -w -p rwa=$(events "S3_watch_${RUN}") -S connect path=$(events "S3_connect_${RUN}")"
kill "${SRV}" 2> /dev/null
rm -f /run/probe.sock

auditctl -D > /dev/null
