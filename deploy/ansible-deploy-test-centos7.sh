#!/bin/bash
ansible-playbook site.yml --extra-vars "ansible_user=root ansible_password=changethisPassw0rd" --ssh-common-args='-o StrictHostKeyChecking=no' -i environments/hs-centos7 
