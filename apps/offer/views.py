from oscar.apps.offer.views import OfferDetailView as CoreOfferDetailView
from django.http import Http404


class OfferDetailView(CoreOfferDetailView):
    def get(self, request, *args, **kwargs):
        """
        We don't support offers pages, therefore we raise page not found exception
        """
        raise Http404

