# collector-endpoint-linux

## Summary and Design Decisions
Automated ansible deployment for customer Linux syslog and auditd with connectivity to HyperI collectors. Support provided for multiple endpoint Linux distributions including end-of-life versions.
A minimal number of components are deployed to reduce:
- inter-distro incompatibility of deployment 
- inter-version dependency breakages
- deprecaction implications such as audisp
- consideration for local disk consumption

## What is Deployed
Rsyslog and auditd with recommmended auditd configuration

## Legacy and End-of-Life Linux Releases
There are multiple dependency combination issues when deploying to legacy and end-of-life Linux releases. Most of these are addressed by the Ansible deployment. Ansible itself also has python and library dependencies when deploying to these systems. When deploying to the oldest of systems (e.g. RHEL4/5) a specific version of Ansible is required. If a python version or library version error is received when attemtpting to deploy this is the most likely cause.  

When deploying to these systems a versioned implementation of ansible is required. The support scripts to deploy this environment is located in the ansible-versioned directory.
- First prep the system using ```hs-setup-ansible-versioned-prerequesites.sh``` (sudo account)
- Then deploy multiple versioned ansible instances using your local account using ```hs-setup-ansible-versioned.sh```
These will deploy the most common combinations requred for older Ubuntu, Debian, RHEL, CentOS and SUSE releases. Scripts to enable specific distro versions are placed in the installation path. These must be executed before deploying to these older systems.

For some edge RHEL5 cases Python remediation is required for deployment. In these instances use with rhel5-upgrade-python.sh and rhel5-upgrade-python-local.sh scripts and associated installation files located in rhel5-ansible-prep.

## SELinux
Distros with SELinux have SELinux exceptions applied to permit safe and reliable rsyslog usage, varying on release version.

## Installation
- Extract ```tar.gz``` file to a directory 
- Change directory to the extracted path (same directory as site.yml)
- Create a file in ```./environments``` (and example is present that can be copied)
    - Set the IP and hostname of the destination systems in this file - recommend creating a file per Linux distro + major version (e.g. rhel5)
    - Set the IP and hostname of the local collector in this file

## Deploy 
Execute ```ansible-playbook site.yml -i environments/<a file you just created>```

Useful commands / notes
To use a username/password either place this in the environment file you created easier or add ```--extra-vars "ansible_user=<username> ansible_password=<password>"``` to the command or add the following to the environment: 
```
[all:vars]
ansible_user=user
ansible_passowrd=password
```

For distros with old / insecure ciphers (such as RHEL4/5) add ```-o KexAlgorithms=diffie-hellman-group1-sha1```  to the command 

To ignore ssh host key checking add ```-o StrictHostKeyChecking=no``` to the command

## Versioning
Semantic Versioning and Changelog applied as per:  
https://semver.org/  
https://www.gitkraken.com/gitkon/semantic-versioning-git-tags  
https://keepachangelog.com

## Create deployment tarball
Execute ```./build-tarball.sh```