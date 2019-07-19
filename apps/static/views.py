from envelope.views import ContactView
from .forms import ContactUsForm
from django.utils.translation import ugettext as _
from django.views.generic import TemplateView, RedirectView, View
from django.http import Http404, HttpResponse
from django.core.urlresolvers import reverse
from datetime import datetime
from django.contrib import messages
import urllib

class ContactUsView(ContactView):
    form_class = ContactUsForm
    template_name = "static/contact.html"

    def get_initial(self):
        """
        Automatically fills form fields for authenticated users.
        """
        initial = super(ContactView, self).get_initial()
        user = self.request.user
        if user.is_authenticated():
            initial.update({
                'sender': user.get_full_name(),
                'email': user.email,
            })
        return initial

    def form_valid(self, form):
        #add success message and redirect
        messages.success(self.request, _("Thank you for your message, we will get back to you soon."))
        return super(ContactUsView, self).form_valid(form)

    def form_invalid(self, form):
        """
        When the form has errors, display it again.
        """
        return self.render_to_response(self.get_context_data(form=form))



class FaqView(TemplateView):
    active_tab = 'intro'
    valid_tab_names = [
        'intro', 'control-panel', 'shipping',
        'package-handling', 'pricing', 'tutorials',
        'referral-program', 'affiliate-program'
    ]

    def dispatch(self, request, *args, **kwargs):
        active_tab = kwargs.get('active_tab', '')
        if active_tab in self.valid_tab_names:
            self.active_tab = active_tab
        return super(FaqView, self).dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return ["static/faq/%s.html" % self.active_tab]

    def get_context_data(self, **kwargs):
        ctx = super(FaqView, self).get_context_data(**kwargs)
        ctx['active_tab'] = self.active_tab
        return ctx

class ForwardingDestinationView(TemplateView):
    template_name = 'static/destinations/base.html'
    countries = [
        ('ca', 'canada'), ('ru', 'russia'),
        ('au', 'australia'), ('fr', 'france'),
        ('gb', 'united-kingdom'), ('br', 'brazil'),
        ('sa', 'saudi-arabia')
    ]
    translated_countries = [
        'france', 'saudi-arabia', 'brazil'
    ]


    def dispatch(self, request, *args, **kwargs):
        self.country_name = kwargs.get('country_name', '')
        self.country_code = kwargs.get('country_code', '')
        self.lang = kwargs.get('lang', '')
        if (self.country_code, self.country_name) not in self.countries:
            raise Http404
        if self.lang and self.lang != 'en':
            raise Http404
        return super(ForwardingDestinationView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(ForwardingDestinationView, self).get_context_data(**kwargs)
        ctx['country_name'] = self.country_name.replace('-', ' ').title()
        ctx['flag_icon'] = 'flag-icon-%s' % self.country_code
        return ctx

    def get_template_names(self):
        if self.country_name in self.translated_countries:
            if not self.lang:
                return "static/destinations/%s.html" % self.country_name
        return self.template_name

class RedirectForwardingDestinationView(RedirectView):
    countries = {
        'canada': 'ca',
        'russia': 'ru',
        'australia': 'au',
        'france': 'fr',
        'united-kingdom': 'gb',
        'great-britain': 'gb',
        'saudi-arabia': 'sa',
        'brazil': 'br',
    }
    def get_redirect_url(self, **kwargs):
        country_name = self.kwargs.get('country_name')
        if country_name not in self.countries:
            raise Http404
        params = urllib.urlencode(self.request.GET)
        return reverse('forwarding-destination', kwargs={
            'country_name': country_name,
            'country_code': self.countries[country_name]
        }) + "?%s" % params

class ProductHuntRedirectView(RedirectView):
    def get_redirect_url(self, **kwargs):
        return reverse('chrome-ext') + '?producthunt=true'

class ChromeToolAddedView(View):
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            profile = request.user.get_profile()
            profile.added_chrome_extension = True
            profile.date_chrome_extension_added = datetime.now()
            profile.save()
        else:
            request.session['added_chrome_extension'] = True
        return HttpResponse()