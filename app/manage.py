#!/usr/bin/env python
import sys
# Apply monkey-patch if we are running the huey consumer.
import grequests



#if 'run_huey' in sys.argv:
#    from gevent import monkey
#    monkey.patch_all()

import os
import sys
import pymysql

from gevent import monkey
monkey.patch_all()


pymysql.install_as_MySQLdb()

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
