from .common import *

## Database
## Imported from dbsettings file now

## EVE Proxy
import raven


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'krabacus3',
        'USER': 'root',
        'PASSWORD': 'getfuckedlol',
        'HOST': 'localhost',   # Or an IP Address that your DB is hosted on
        'PORT': '3306',
        #'CONN_MAX_AGE': 60
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/0',
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            'CONNECTION_POOL_CLASS': 'redis.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
        },
        "KEY_PREFIX": "krabacus"
    }
}

DEMO_FILE_LOCATION = "/home/bsamuels/krabacus3/app/"



LOGGING = {}
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="put sentry dsn here",
    integrations=[DjangoIntegration()]
)

EVE_API_URL = "https://api.eveonline.com"
EVE_PROXY_KEEP_LOGS = 30

## SSO
DISABLE_SERVICES = False
GENERATE_SERVICE_PASSWORD = False
IGNORE_CORP_GROUPS = [29]

## Server Mail
SERVER_EMAIL = ''
DEFAULT_FROM_EMAIL = ""

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


## Django
DEBUG = True
SECRET_KEY = ''
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', '*']

ADMINS = ()
MANAGERS = ADMINS


TEMPLATE_DEBUG=True
# Debug Toolbar
INTERNAL_IPS = ['127.0.0.1']



LAMBDA_URL_ROOT = ""

EVEOAUTH["CONSUMER_KEY"] = "eve api consumer key debug"
EVEOAUTH["CONSUMER_SECRET"] = "eve api consumer secret debug"

logging.config.dictConfig(logging_config)


if DEBUG:
    MIDDLEWARE.insert(0,'debug_toolbar.middleware.DebugToolbarMiddleware')
    INSTALLED_APPS.insert(0,'debug_toolbar')
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'