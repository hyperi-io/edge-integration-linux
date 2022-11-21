There are two options when deploying to RHEL5 or earlier

1. Deploy using an older version of Ansible on the system performing the deploy 
- Ansible 2.3

2. Attempt to upgrade python on each RHEL server
- Use the rhel5-upgrade-python-local.sh or rhel5-upgrade-python.sh script
- Add the ansible_python_interpreter: /usr/bin/python2.6 variable to the environment file

 
