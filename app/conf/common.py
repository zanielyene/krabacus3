import os
import pickle
import logging.config
from .huey_queues import *

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# If CCP ESI is crapping itself, we should give it a solid amount of time to get its shit together
# because it usually does so pretty reliably. Blowing all our retries in a few milliseconds is a waste.
ESI_RETRY_TIME_INTERVAL_SECONDS = 1

# number of times to retry an ESI request that failed due to a connection error/CCP-side error.
MAX_ESI_RETRIES = 3

# how long to cache the results of all ESI requests
ESI_CACHE_DURATION_SECONDS = 60 * 10

AUTHENTICATION_BACKENDS = [
    # Uncomment following if you want to access the admin
    'django.contrib.auth.backends.ModelBackend'
]

# Zone Settings
TIME_ZONE = 'UTC'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = True
USE_TZ = True

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Defines the Static Media storage as per staticfiles contrib
STATIC_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'static')

STATIC_URL = '/static/'

STATICFILES_DIRS = (
    os.path.join(os.path.dirname(BASE_DIR), "app", "static"),
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = ''

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

MIDDLEWARE = [
    'raven.contrib.django.middleware.SentryResponseErrorIdMiddleware',
    #'corsheaders.middleware.CorsMiddleware',
'django.contrib.sessions.middleware.SessionMiddleware',
    #'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',
    #'oauth2_provider.middleware.OAuth2TokenMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'waffle.middleware.WaffleMiddleware',
]
CORS_ORIGIN_ALLOW_ALL = True

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates/', os.path.join(os.path.dirname(__file__), '..', 'templates'), ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

INSTALLED_APPS = [
    'dal',
    'dal_select2',
    'suit',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.messages',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'raven.contrib.django',
    'waffle',
    'bootstrap4',
    'eve_api',
    'sso',
    'market',
    'payments',
    'notifications',
]

BOOTSTRAP4 = {
    "css_url": {
        "href": "/static/css/bootstrap.min.css",
    },
}



AUTH_PROFILE_MODULE = 'sso.SSOUser'
LOGIN_REDIRECT_URL = "/profile"
LOGIN_URL = "/login"

### OAuth

OAUTH_AUTH_VIEW = 'api.views.oauth_auth_view'
OAUTH_CALLBACK_VIEW = 'api.views.oauth_callback_view'

## EVE Proxy

EVE_API_URL = "https://api.eveonline.com"
EVE_CDN_URL = "https://image.eveonline.com"
EVE_ESI_URL = "https://esi.evetech.net"



LOGGING_CONFIG = None
logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console': {
            # exact format is not important, this is the minimum information
            'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        },
        'colored': {
            '()': 'colorlog.ColoredFormatter',
            'format': "%(log_color)s %(asctime)s %(levelname)-8s %(name)-12s %(reset)s %(message)s"
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'colored',
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
        'payments': {
            'level': 'INFO',
            'handlers': ['console', 'sentry'],
            # required to avoid double logging with root logger
            'propagate': False,
        },
    },
}

# List of base ESI Scopes. Any key with these scopes is considered good for alliance-wide use. Do not add keys to this
# list. Only add keys to ALLIANCE_NEW_ESI_SCOPES, or else users with older ESI keys will have their keys downgraded
# to allied keys.

ESI_SCOPES = [
    'esi-wallet.read_character_wallet.v1',
    'esi-search.search_structures.v1',
    'esi-markets.read_character_orders.v1',
    'esi-assets.read_assets.v1',
    'esi-markets.structure_markets.v1',
    'esi-universe.read_structures.v1'

]

ALLIANCE_LEGACY_ESI_SCOPES = [
     'esi-industry.read_character_mining.v1',
     'esi-industry.read_corporation_mining.v1',
     'esi-calendar.read_calendar_events.v1',
     'esi-location.read_location.v1',
     'esi-location.read_ship_type.v1',
     'esi-mail.read_mail.v1',
     'esi-skills.read_skills.v1',
     'esi-skills.read_skillqueue.v1',
     'esi-wallet.read_character_wallet.v1',
     'esi-search.search_structures.v1',
     'esi-clones.read_clones.v1',
     'esi-characters.read_contacts.v1',
     'esi-universe.read_structures.v1',
     'esi-fleets.read_fleet.v1',
     'esi-characters.read_loyalty.v1',
     'esi-characters.read_opportunities.v1',
     'esi-characters.read_chat_channels.v1',
     'esi-characters.read_standings.v1',
     'esi-characters.read_agents_research.v1',
     'esi-industry.read_character_jobs.v1',
     'esi-markets.read_character_orders.v1',
     'esi-contracts.read_character_contracts.v1',
     'esi-contracts.read_corporation_contracts.v1',
     'esi-clones.read_implants.v1',
     'esi-characters.read_fatigue.v1',
     'esi-characters.read_notifications.v1',
     'esi-characters.read_corporation_roles.v1',
     'esi-wallet.read_corporation_wallets.v1',
     'esi-corporations.read_corporation_membership.v1',
     'esi-corporations.read_divisions.v1',
     'esi-corporations.track_members.v1',
     'esi-corporations.read_contacts.v1',
     'esi-corporations.read_titles.v1',
     'esi-characters.read_titles.v1',
     'esi-corporations.read_structures.v1',
     'esi-markets.read_corporation_orders.v1',
     'esi-assets.read_assets.v1',
     'esi-assets.read_corporation_assets.v1',
     'esi-markets.structure_markets.v1',
     'esi-corporations.read_facilities.v1'
]

SUBSCRIPTION_PRICE_PER_MONTH = 150000000

# zanielyene
PAYMENT_CHARACTER_ID = 1433355584
GLOBALLY_DISABLE_ESI_CACHE = False

EVEOAUTH = {
     "BASE_URL" :"https://login.eveonline.com/oauth/",
     "AUTHORIZATION_URL" : "authorize",
     "TOKEN_URL" : "token",
}

