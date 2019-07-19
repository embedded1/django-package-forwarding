from oscar.apps.customer.notifications.views import DetailView as CoreDetailView, InboxView as CoreInboxView
from django.utils.translation import ugettext as _
from django.utils.html import strip_tags
from ..mixins import AjaxTemplateMixin
from django.core.paginator import InvalidPage
from django.http import Http404

class DetailView(AjaxTemplateMixin, CoreDetailView):
    def get_page_title(self):
        """Append subject to page title"""
        title = strip_tags(self.object.subject)
        return u'%s: %s' % (_('Notification'), title[:30] + "...")


class InboxView(CoreInboxView):
    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, if needed.
        """
        paginator = self.get_paginator(queryset, page_size, allow_empty_first_page=self.get_allow_empty())
        page = self.kwargs.get('page') or self.request.GET.get('page') or 1
        try:
            page_number = int(page)
        except ValueError:
            if page == 'last':
                page_number = paginator.num_pages
            else:
                raise Http404(_(u"Page is not 'last', nor can it be converted to an int."))
        try:
            page = paginator.page(page_number)
        except InvalidPage:
            # This used to raise a 404, but we're replacing this functionality
            #raise Http404(_(u'Invalid page (%(page_number)s)') % {
            #                    'page_number': page_number
            #})
            #return last page where invalid page received
            page = paginator.page(paginator.num_pages)

        return (paginator, page, page.object_list, page.has_other_pages())