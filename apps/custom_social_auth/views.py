from apps.customer.forms import ProfileWithEmailForm
from apps.customer.utils import RegisterSessionData
from django.views.generic import FormView
from django.views.generic.base import TemplateView
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.conf import settings
from oscar.core.loading import get_class
from django.utils.translation import ugettext as _
import logging
import copy

logger = logging.getLogger(__name__)
RegisterUserMixin = get_class('customer.mixins', 'RegisterUserMixin')

class CustomSocialAuthProfileView(RegisterUserMixin, FormView, RegisterSessionData):
    """
    We prompt user who is logging in via 3-rd party social service platform to fill in profile related data
    """
    template_name = 'customer/registration_profile.html'
    form_class = ProfileWithEmailForm
    backend = None
    user_extra_data = None

    def dispatch(self, request, *args, **kwargs):
        self.register_session_data = RegisterSessionData(request)
        partial_pipeline = request.session.get('partial_pipeline')
        if partial_pipeline:
            self.backend = partial_pipeline.get('backend')
        self.social_data = request.session.get('social_details')
        return super(CustomSocialAuthProfileView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        #get user location
        self.user_extra_data = self.get_user_extra_data(request)
        #get a copy of the POST data
        self.post_data = copy.deepcopy(request.POST)
        self.align_photos_service()
        return super(CustomSocialAuthProfileView, self).post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        #redirect back to homepage if no backend is found
        if not self.backend:
            logger.critical("No backend found! redirected back to home page")
            messages.error(self.request, _("Something went wrong, please try to sign up with your email address."))
            return HttpResponseRedirect(reverse('customer:register'))
        self.capture_potential_user_email(self.social_data.get("email", ''))
        return super(CustomSocialAuthProfileView, self).get(request, *args, **kwargs)


    def get_form_kwargs(self):
        kwargs = {'initial': self.get_initial()}
        #we show this form before user is created
        kwargs['user'] = None
        kwargs['ip_country'] = self.user_extra_data['country'] if self.user_extra_data else None
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.post_data,
                'files': self.request.FILES,
            })
        return kwargs

    def form_valid(self, form):
        register_data = self.register_session_data.get_account_data()
        profile = form.save(commit=False)
        profile.is_account_setup_completed = True
        profile.country = form.cleaned_data['country']
        #get user location
        user_extra_data = self.get_user_extra_data(self.request)
        if user_extra_data is not None:
            profile.city = user_extra_data['city']
            #profile.country = user_extra_data['country']
            profile.ip = user_extra_data['ip']

        #save profile in session and we will save this profile to db after
        #user will be created
        self.request.session['social_profile'] = profile
        #save user's properties as email, first and last name for user creating stage
        self.request.session['social_details']['email'] = form.cleaned_data['email'].lower()
        self.request.session['social_details']['first_name'] = form.cleaned_data['first_name']
        self.request.session['social_details']['last_name'] = form.cleaned_data['last_name']
        self.request.session['social_details']['mixpanel_anon_id'] = form.cleaned_data.get('mixpanel_anon_id')
        self.request.session['social_details']['register_type'] = register_data.get('register_type', 'organic')
        #mark that social user created
        self.request.session['social_extra_settings_populated'] = True
        self.request.session.modified = True
        self.add_tour_message()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super(CustomSocialAuthProfileView, self).get_context_data(**kwargs)
        #always show the accept tos and pp checkbox for social auth
        ctx['show_terms'] = True
        return ctx

    def get_success_response(self):
        return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super(CustomSocialAuthProfileView, self).get_initial()
        if self.social_data:
            initial['email'] = self.social_data.get('email', '')
            initial['first_name'] = self.social_data.get('first_name', '')
            initial['last_name'] = self.social_data.get('last_name', '')
        return initial

    def get_success_url(self):
        url = reverse('social:complete', kwargs={'backend': self.backend})
        return url


class CustomSocialAuthErrorView(TemplateView):
    template_name = 'custom_social_auth/login_error.html'

    def collect_error_messages(self):
        storage = messages.get_messages(self.request)
        return ", ".join([unicode(msg) for msg in storage])

    def log_error_messages(self):
        #log critical message indicating that social login failed
        error_msgs = self.collect_error_messages()
        logger.critical("python-social-auth: login error - %s" % error_msgs)


    def get(self, request, *args, **kwargs):
        self.log_error_messages()
        return super(CustomSocialAuthErrorView, self).get(request, *args, **kwargs)


    #def get_context_data(self, **kwargs):
    #    context = super(CustomSocialAuthErrorView, self).get_context_data(**kwargs)
    #    msgs = messages.get_messages(self.request)
    #    context['messages'] = msgs
    #    return context
