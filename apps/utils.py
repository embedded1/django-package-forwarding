from django.contrib.sites.models import Site
from datetime import datetime
from django.conf import settings


def get_site_properties():
    ctx = {}
    current_site = Site.objects.get_current()
    ctx['site'] = "https://%s" % current_site.domain
    ctx['site_name'] = current_site.name
    return ctx

def operation_shut_down(user):
    email = getattr(user, 'email', None)
    if user.is_staff or email in settings.ALLOW_TO_SHIP_USERS:
        return False
    # Operation shuts down on September 11, 2018
    cut_off_date = datetime(2018, 9, 11)
    now = datetime.now()
    return now >= cut_off_date

def operation_suspended(user):
    if isinstance(user, basestring):
        email = user
    else:
        email = getattr(user, 'email', None)

    if email in settings.ALLOW_TO_SIGNUP_EMAILS:
        return False
    # US address will be suspended on August 25
    cut_off_date = datetime(2018, 8, 25)
    now = datetime.now()
    return now >= cut_off_date