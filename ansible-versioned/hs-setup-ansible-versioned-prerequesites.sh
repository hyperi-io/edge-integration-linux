#!/bin/bash
#
# Install HyperI Ansible for CentOS deployments
# (c) HyperI 2022
#
# v1.1      2022-11-08      Updated for RHEL5/6
# v1.0      2019-12-16      Initial version

echo
echo "Install HyperI Ansible versioned prerequesite insatllation"
echo "for legacy distro support v1.1"
echo 

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

packagesNeeded='python3 python3-pip python3-venv sshpass'
if [ -x "$(command -v apk)" ];       then sudo apk add --no-cache $packagesNeeded
elif [ -x "$(command -v apt-get)" ]; then sudo apt-get install $packagesNeeded
elif [ -x "$(command -v dnf)" ];     then sudo dnf install $packagesNeeded
elif [ -x "$(command -v yum)" ];  then sudo yum install $packagesNeeded
elif [ -x "$(command -v zypper)" ];  then sudo zypper install $packagesNeeded
else echo "FAILED TO INSTALL PACKAGE: Package manager not found. You must manually install: $packagesNeeded">&2; fi
