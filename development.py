import sys
import os

from django.core.wsgi import get_wsgi_application

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
os.environ['DJANGO_SETTINGS_MODULE'] = 'app.conf.development'
application = get_wsgi_application()
