from django.views.generic import RedirectView
from django.core.urlresolvers import reverse


class BasketView(RedirectView):
    """
    We don't want to show the basket to our customers so we redirect to
    control panel main page
    """
    def get_redirect_url(self, **kwargs):
        return reverse('customer:profile-view')

