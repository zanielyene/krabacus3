#!/bin/bash

NAME="krabacus"                                  # Name of the application
DJANGODIR=/home/krabacus/krabacus3             # Django project directory
SOCKFILE=/tmp/gunicorn.sock  # we will communicte using this unix socket
USER=krabacus                                        # the user to run as
GROUP=krabacus                                     # the group to run as
NUM_WORKERS=3                                     # how many worker processes should Gunicorn spawn
DJANGO_SETTINGS_MODULE=conf.production             # which settings file should Django use


echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
source env/bin/activate
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
#export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec gunicorn --pythonpath app conf.wsgi \
  --name $NAME \
  --workers $NUM_WORKERS \
  --user=$USER --group=$GROUP \
  --bind=unix:$SOCKFILE \
  --log-level=debug \
  --log-file=/home/krabacus/logs/gunicorn.log \
  --timeout 90 \
  --keep-alive 70
