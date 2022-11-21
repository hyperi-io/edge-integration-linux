#!/bin/bash
#
# Install HyperSec Ansible versioned for legacy distro support
# (c) HyperSec 2022
#
# v1.1      2022-11-08      Updated for  RHEL5/6
# v1.0      2019-12-16      Initial version

echo
echo "Install HyperSec Ansible versioned for legacy distro support v1.1"
echo 

if [ "$1" == "--help"  ] || [ "$1" == "-?"  ] ; then
    echo "Usage: hs-setup-ansible-versioned.sh <path>"
    exit 0
fi

# Prerequesite checks
DEPLOY_TO=~
if [ -z "$1" ] ; then 
    echo "No path specified, deploying to home directory ~"
else
    if [ -d "$1" ] ; then
        echo "Deploying to path $1"
        DEPLOY_TO=$1
    else
        echo "ERROR: Path not found: $1"
        exit 1
    fi
fi

if ! command -v python3 &> /dev/null
then
    echo "ERROR: python3 could not be found, please install python3"
    exit 1
fi

if ! command -v pip3 &> /dev/null
then
    echo "ERROR: pip3 could not be found, please install python3 pip"
    exit 1
fi

# OK to continue
echo "This installation will install multiple ansible versions for different"
echo "Linux distrubution support into: $DEPLOY_TO"
echo
while true; do
    read -p "Continue (y/n)" yn
    case $yn in
        [Yy]* ) make install; break;;
        [Nn]* ) exit;;
        * ) echo "Please answer yes or no.";;
    esac
done

# Directory structure and venvs
pushd $DEPLOY_TO

mkdir -p ./ansible-venvs
cd ./ansible-venvs

echo "Installing ansible-latest"
python3 -m venv ansible-latest
cd ansible-latest
source bin/activate
python3 -m pip install --upgrade pip
pip3 install wheel ansible
deactivate
cd ..

echo "Installing ansible 5.10"
python3 -m venv ansible-5.10
cd ansible-5.10
source bin/activate
python3 -m pip install --upgrade pip
pip3 install wheel ansible==5.10
deactivate
cd ..

echo "Installing ansible 2.3"
python3 -m venv ansible-2.3
cd ansible-2.3
source bin/activate
pip3 install --upgrade pip==20.0.2
pip3 uninstall pycrypto
pip3 install wheel pycryptodome 
pip3 install ansible==2.3.3
deactivate
cd..

echo "source $DEPLOY_TO/ansible-venvs/ansible-5.10/bin/activate" > $DEPLOY_TO/ansible-rhel6.sh
chmod +x $DEPLOY_TO/ansible-rhel6.sh
echo "source $DEPLOY_TO/ansible-venvs/ansible-2.3/bin/activate" > $DEPLOY_TO/ansible-rhel5.sh
chmod +x $DEPLOY_TO/ansible-rhel5.sh

popd
