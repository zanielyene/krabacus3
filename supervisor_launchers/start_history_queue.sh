#!/bin/bash

cd /home/krabacus/krabacus3
source env/bin/activate
export DJANGO_SETTINGS_MODULE=conf.production

cd app
exec python ./manage.py run_consumer --queue history_queue --worker-type greenlet --workers 1