#!/usr/bin/env python
import sys
# Apply monkey-patch if we are running the huey consumer.
import grequests

import os

#if 'run_huey' in sys.argv:
#    from gevent import monkey
#    monkey.patch_all()

import os
import sys
import pymysql

from gevent import monkey
monkey.patch_all()


pymysql.install_as_MySQLdb()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.production")

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
