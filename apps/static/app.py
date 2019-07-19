from django.conf.urls import patterns, url
from . import views
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy
from django.views.generic.simple import direct_to_template
from oscar.core.application import Application


class StaticApplication(Application):
    contact_us_view = views.ContactUsView
    faq_view = views.FaqView
    forwarding_destination_view = views.ForwardingDestinationView
    redirect_forwarding_destination_view = views.RedirectForwardingDestinationView
    producthunt_redirect_view = views.ProductHuntRedirectView
    chrome_tool_added = views.ChromeToolAddedView

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^contact/$', self.contact_us_view.as_view(),
                name='contact'),
            url(r'^about-us/$', direct_to_template,
                {'template': 'static/aboutus.html'}, name='aboutus'),
            #url(r'^contactus.html$', 'django.views.generic.simple.direct_to_template',
            #    {'template': 'static/contactus.html'}, name='contactus'),
            url(r'^support/faq/$',
                RedirectView.as_view(url=reverse_lazy(
                    'faq', kwargs={'active_tab': 'intro'})), name='faq'),
            url(r'^support/faq/(?P<active_tab>[\w-]*)/$',
                self.faq_view.as_view(), name='faq'),
            url(r'^features/$', direct_to_template,
                {'template': 'static/features.html'}, name='features'),
            url(r'^learn-more-about-fees/$', direct_to_template,
                {'template': 'static/fees-explained.html'}, name='fees-explained'),
            url(r'^legal/terms/$', direct_to_template,
                {'template': 'static/terms.html'}, name='terms'),
            url(r'^legal/privacy/$', direct_to_template,
                {'template': 'static/privacy.html'}, name='privacy'),
            url(r'^referral-program/$', direct_to_template,
                {'template': 'static/referral-program.html'}, name='referral-program'),
            url(r'^affiliate-program/$', direct_to_template,
                {'template': 'static/affiliate-program.html'}, name='affiliate-program'),
            url(r'^pricing/$', direct_to_template,
                {'template': 'static/pricing.html'}, name='pricing'),
            url(r'^amazon-worldwide-shipping/$', direct_to_template,
                {'template': 'static/amazon-chrome-extension.html'}, name='chrome-ext'),
            url(r'^how-usendhome-works/$', direct_to_template,
                {'template': 'static/how-it-works.html'}, name='how-it-works'),
            url(r'^amazon-worldwide-shipping/producthunt/$',
                self.producthunt_redirect_view.as_view(), name='chrome-ext-producthunt'),
            url(r'^gb/ship-from-usa-to-great-britain/$',
                RedirectView.as_view(url='/gb/ship-from-usa-to-united-kingdom/')),
            url(r'^ship-from-usa-to-(?P<country_name>[\w-]*)/$',
                self.redirect_forwarding_destination_view.as_view(), name='redirect-forwarding-destination'),
            url(r'^(?P<country_code>[\w-]*)/ship-from-usa-to-(?P<country_name>[\w-]*)/$',
                self.forwarding_destination_view.as_view(), name='forwarding-destination'),
            url(r'^(?P<country_code>[\w-]*)/ship-from-usa-to-(?P<country_name>[\w-]*)/(?P<lang>[\w]*)/$',
                self.forwarding_destination_view.as_view(), name='forwarding-destination'),
            url(r'^amazon-worldwide-shipping/welcome/$', direct_to_template,
                {'template': 'static/amazon-extension-welcome.html'}, name='chrome-welcome'),
            url(r'^giveaway/$', direct_to_template,
                {'template': 'static/giveaway.html'}, name='giveaway'),
            url(r'^chrome/added/$',
                self.chrome_tool_added.as_view(), name='chrome-added'),
            url(r'^complete/twitter/$',
                RedirectView.as_view(url=reverse_lazy('custom_social_auth:profile-form')), name='twitter-auth'),
        )
        return self.post_process_urls(urlpatterns)


application = StaticApplication()

