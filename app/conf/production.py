from .common import *

## Database
## Imported from dbsettings file now

## EVE Proxy
import raven


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'krabacus',
        'USER': 'krabacus',
        'PASSWORD': 'nice desu ne',
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



LOGGING = {}
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
sentry_sdk.init(
    dsn="deez nutz",
    integrations=[DjangoIntegration()]
)

DEMO_FILE_LOCATION = "/home/krabacus/krabacus3/app/"


## Server Mail
SERVER_EMAIL = ''
DEFAULT_FROM_EMAIL = ""

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


## Django
DEBUG = False
SECRET_KEY = 'womp womp'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'dev.krabacus.com', 'krabacus.com']

ADMINS = ()
MANAGERS = ADMINS

TEMPLATE_DEBUG=True
# Debug Toolbar
INTERNAL_IPS = ['127.0.0.1']



LAMBDA_URL_ROOT = ""

EVEOAUTH["CONSUMER_KEY"] = "eve api consumer key"
EVEOAUTH["CONSUMER_SECRET"] = "eve api consumer secret"


logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            # exact format is not important, this is the minimum information
            'format': '%(name)-12s %(levelname)-8s %(message)s',
        },
        'colored': {
            '()': 'colorlog.ColoredFormatter',
            'format': "%(log_color)s %(asctime)s %(levelname)-8s %(name)-12s %(reset)s %(message)s"
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'console',
        },
        # Add Handler for Sentry for `warning` and above
        'sentry': {
            'level': 'WARNING',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
    },
    'loggers': {
    # root logger
        '': {
            'level': 'WARNING',
            'handlers': ['console', 'sentry'],
        },
        'sso': {
            'level': 'INFO',
            'handlers': ['console', 'sentry'],
            # required to avoid double logging with root logger
            'propagate': False,
        },
        'eve_api': {
            'level': 'INFO',
            'handlers': ['console', 'sentry'],
            # required to avoid double logging with root logger
            'propagate': False,
        },
        'market': {
            'level': 'INFO',
            'handlers': ['console', 'sentry'],
            # required to avoid double logging with root logger
            'propagate': False,
        },
    },
}


logging.config.dictConfig(logging_config)

if DEBUG:
    MIDDLEWARE.insert(0,'debug_toolbar.middleware.DebugToolbarMiddleware')
    INSTALLED_APPS.insert(0,'debug_toolbar')
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

