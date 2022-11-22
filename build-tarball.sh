#!/bin/bash
VERSION=$( git tag --sort="version:refname" | tail -1 )
rm -f ./hypersec-linux-ansible-${VERSION}.tar.gz
tar --exclude="./deploy" --exclude="./build-tarball.sh" --exclude="./environments/hs*" --exclude="./.git" --exclude="./.gitattributes" --exclude="./*.tar.gz" -zcvf ./hypersec-collector-endpoint-linux-$VERSION.tar.gz .
