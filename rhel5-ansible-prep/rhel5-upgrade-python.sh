#!/bin/bash
wget http://archives.fedoraproject.org/pub/archive/epel/5/x86_64/libffi-3.0.5-1.el5.x86_64.rpm -O /tmp/libffi-3.0.5-1.el5.x86_64.rpm
wget http://archives.fedoraproject.org/pub/archive/epel/5/x86_64/python26-libs-2.6.8-2.el5.x86_64.rpm -O /tmp/python26-libs-2.6.8-2.el5.x86_64.rpm
wget http://archives.fedoraproject.org/pub/archive/epel/5/x86_64/python26-2.6.8-2.el5.x86_64.rpm -O /tmp/python26-2.6.8-2.el5.x86_64.rpm
sudo yum -y install /tmp/python26-2.6.8-2.el5.x86_64.rpm /tmp/python26-libs-2.6.8-2.el5.x86_64.rpm /tmp/python26-2.6.8-2.el5.x86_64.rpm
rm /tmp/libffi-3.0.5-1.el5.x86_64.rpm
rm /tmp/python26-libs-2.6.8-2.el5.x86_64.rpm
rm /tmp/python26-2.6.8-2.el5.x86_64.rpm
