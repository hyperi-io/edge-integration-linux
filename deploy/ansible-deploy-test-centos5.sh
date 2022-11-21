#!/bin/bash
ansible-playbook site.yml --extra-vars "ansible_user=root ansible_password=changethisPassw0rd" --ssh-common-args="-o StrictHostKeyChecking=no -o KexAlgorithms=diffie-hellman-group1-sha1" -i environments/hs-centos5 
