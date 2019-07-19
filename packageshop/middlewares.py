from django.core.urlresolvers import reverse
from apps.checkout.utils import CheckoutSessionData
from apps.user.models import Profile
import urlparse
import logging

logger = logging.getLogger(__name__)

class RequestSessionCleanerMiddleware(object):
    """
    This middleware only task is to flush session attributes when user
    has navigated away from certain pages
    for example: we need to flush calculator namespace when user navigated away from calculator
    page to properly reset his search session
    we need to flush shipping repository, package data and custom form namespaces when user has
    navigated away from checkout page
    """

    def process_request(self, request):
        full_path = request.get_full_path()
        checkout_path = reverse('checkout:index')

        if not checkout_path in full_path:
            if hasattr(request, 'user'):
                try:
                    #only registered users have profile
                    request.user.get_profile()
                except (AttributeError, Profile.DoesNotExist):
                    pass
                else:
                    check_session = CheckoutSessionData(request)
                    check_session.turn_off_package_checkout()

class SaveReferrerMiddleware(object):
    def process_request(self, request):
        if not request.user.is_authenticated() and 'external_referer' not in request.session:
            referer = request.META.get('HTTP_REFERER')
            if referer is not None:
                parsed_url = urlparse.urlparse(referer)
                if parsed_url:
                    domain = getattr(parsed_url, 'netloc', None)
                    if domain is not None and domain not in ['www.usendhome.com', 'usendhome.com']:
                        # External referer - obey the 200 characters limit
                        request.session['external_referer'] = referer[:200]


class GoogleAnalyticsMiddleware(object):
    def process_request(self, request):
        data_available = False
        required_fields = (
            'utm_source', 'utm_medium', 'utm_campaign',
            'utm_term', 'utm_content'
        )
        # check if adwords tagging exists
        if required_fields[0] in request.GET:
            for field in required_fields:
                if field in request.GET:
                    if not data_available:
                        request.session['adwords_data'] = {}
                        data_available = True
                    request.session['adwords_data'][field] = request.GET[field]
            if data_available:
                request.session.modified = True