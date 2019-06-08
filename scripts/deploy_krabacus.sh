#!/bin/bash

supervisorctl stop all
cd /home/krabacus/krabacus3
git pull origin master
rm -rf ./static
source ./env/bin/activate
cd ./app
./manage.py collectstatic --noinput
deactivate
cd ..
chown -R krabacus:krabacus *

redis-cli -n 1 flushdb
supervisorctl start all
