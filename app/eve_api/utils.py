from datetime import datetime
from xml.dom import minidom
import waffle
from django.utils.timezone import utc
from eve_api.models import *


def parse_eveapi_date(datestring):
    return datetime.strptime(datestring, "%Y-%m-%d %H:%M:%S").replace(tzinfo=utc)


