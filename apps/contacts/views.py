from django.views.generic import RedirectView, View, TemplateView
from django.conf import settings
from django.contrib import messages
from django.template.loader import render_to_string
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.utils.translation import ungettext, ugettext as _
from django.utils import simplejson as json
from apps.tasks.mixins import CeleryTaskStatusMixin
from apps.customer.mixins import AjaxTemplateMixin
from .tasks import get_google_contacts, email_contacts
from apps.customer.tasks import mixpanel_track_user_invited
from .cache import GoogleTokenCache
import gdata.gauth
import gdata.contacts.client



class AuthView(RedirectView, GoogleTokenCache):
    GOOGLE_SCOPE = "https://www.googleapis.com/auth/contacts.readonly"

    def get_redirect_uri(self):
        if settings.DEBUG:
            host = settings.GOOGLE_API_SANDBOX_RETURN_DOMAIN
        else:
            host = Site.objects.get_current().domain
        scheme = 'https' if self.request.is_secure() else 'http'
        redirect_uri = '%s://%s%s' % (
            scheme, host, reverse('contacts:auth'))
        return redirect_uri

    def get_redirect_url(self, **kwargs):
        #Try to fetch the authentication token from cache
        auth_token = self.get_token(self.request.user.pk)
        #If an authentication token does not exist already,
        #create one and store it in the session.
        if not auth_token:
            auth_token = gdata.gauth.OAuth2Token(
                    client_id=settings.GOOGLE_CLIENT_ID,
                    client_secret=settings.GOOGLE_CLIENT_SECRET,
                    scope=self.GOOGLE_SCOPE,
                    user_agent='USendHome 1.0')

            self.store_token(key=self.request.user.pk, token=auth_token)
            #Generate the url on which authentication request will be sent
            authorize_url = auth_token.generate_authorize_url(
                redirect_uri=self.get_redirect_uri())
                #approval_prompt='force')
            return authorize_url

        #here we process the response from Google
        #The code that google sends in case of a successful authentication
        code = self.request.GET.get('code')
        if code:
            #Set the redirect url on the token
            auth_token.redirect_uri = self.get_redirect_uri()
            #Generate the access token
            auth_token.get_access_token(code)
            #save the access auth token in cache
            self.store_token(key=self.request.user.pk, token=auth_token)
            url = "%s?show_contacts=1" % reverse('customer:referrals-index')
            return url

        #use the refresh token to get access to contacts
        if auth_token:
            auth_token = gdata.gauth.OAuth2Token(
                    client_id=settings.GOOGLE_CLIENT_ID,
                    client_secret=settings.GOOGLE_CLIENT_SECRET,
                    scope=self.GOOGLE_SCOPE,
                    user_agent='USendHome 1.0',
                    refresh_token=auth_token.refresh_token)
            gd_client = gdata.contacts.client.ContactsClient()
            auth_token.authorize(gd_client)
            self.store_token(key=self.request.user.pk, token=auth_token)
            url = "%s?show_contacts=1" % reverse('customer:referrals-index')
            return url

        #error returned from Google
        messages.info(self.request, _("Authentication cancelled"))
        return reverse('customer:profile-view')

class InviteFriendsView(AjaxTemplateMixin, TemplateView):
    ajax_template_name = "customer/referrals/friends.html"

    def get_success_url(self):
        return reverse('customer:referrals-index')

    def get_context_data(self, **kwargs):
        ctx = super(InviteFriendsView, self).get_context_data(**kwargs)
        ctx['remaining_invites'] = self.request.user.get_profile().remaining_invites
        return ctx

    def post(self, request, *args, **kwargs):
        if self.request.is_ajax():
            emails_tags = json.loads(request.POST.get('email_tags', []))
            emails = [tag['text'] for tag in emails_tags]
            emails_count = len(emails)
            if emails_count:
                profile = request.user.get_profile()
                if profile.remaining_invites == 0:
                    messages.info(self.request, _("You ran out of invitations for today, please try again tomorrow."))
                else:
                    #make sure we don't exceed the daily quota
                    kwargs = {
                        'friend_name': request.user.get_full_name().title(),
                        'referral_link': profile.referral_link,
                        'contact_emails': emails[:profile.remaining_invites]
                    }
                    #update daily quota
                    if emails_count > profile.remaining_invites:
                        sent_emails_count = profile.remaining_invites
                        profile.remaining_invites = 0
                    else:
                        profile.remaining_invites -= emails_count
                        sent_emails_count = emails_count
                    profile.save()
                    #fire the background email task
                    email_contacts.apply_async(queue='checkout', kwargs=kwargs)
                    #track performence
                    mixpanel_track_user_invited.apply_async(queue='analytics', kwargs={
                        'user_id': request.user.id,
                        'invitee_emails': emails[:profile.remaining_invites],
                        'invite_type': 'manual'
                    })
                    #display success message
                    messages.success(self.request, ungettext(
                        "%(count)d person was successfully invited to USendHome",
                        "%(count)d persons were successfully invited to USendHome",
                        sent_emails_count) % {'count': sent_emails_count})
            else:
                messages.info(self.request, _("No invitation sent :("))
            return self.json_response(
                is_valid=True,
                redirect_url=self.get_success_url()
            )
        return HttpResponseRedirect(reverse('customer:profile-view'))


class InviteContactsView(View, CeleryTaskStatusMixin, GoogleTokenCache):
    template_name = 'customer/referrals/contacts.html'

    def handle_celery_task_result(self, result):
        if result is None:
            #maybe user revoked permissions, need to begin the auth once again
            self.delete_token(self.request.user.pk)
            return self.json_response(
                ctx=None,
                redirect_url=reverse('contacts:auth'),
                status='COMPLETED')

        ctx = {'contacts': result}
        return self.json_response(
            ctx=ctx,
            status='COMPLETED')

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'send-invites')
        if action == 'google-auth':
            return self.json_response(
                ctx=None, redirect_url=reverse('contacts:auth'))
        else:
            emails = request.POST.getlist('google_contact', [])
            emails_count = len(emails)

            if emails_count:
                profile = request.user.get_profile()
                #make sure we don't exceed the daily quota
                kwargs = {
                    'friend_name': request.user.get_full_name().title(),
                    'referral_link': profile.referral_link,
                    'contact_emails': emails
                }
                #fire the background email task
                email_contacts.apply_async(queue='checkout', kwargs=kwargs)
                #track performence
                mixpanel_track_user_invited.apply_async(queue='analytics', kwargs={
                    'user_id': request.user.id,
                    'invitee_emails': emails,
                    'invite_type': 'google'
                })
                #display success message
                messages.success(request, ungettext(
                    "%(count)d person was successfully invited to USendHome",
                    "%(count)d persons were successfully invited to USendHome",
                    emails_count) % {'count': emails_count})
            else:
                messages.info(request, _("No invitation sent :("))
        return HttpResponseRedirect(reverse('customer:referrals-index'))

    def get(self, request, *args, **kwargs):
        if request.is_ajax():
            #Fetch the auth_token that we set in our base view
            auth_token = self.get_token(self.request.user.pk)
            task_id = request.GET.get('task_id')
            if task_id:
                return self.task_status(
                    task_id=task_id)
            if not auth_token:
                return self.json_response(
                    ctx=None, redirect_url=reverse('contacts:auth'))
            #run the background task to fetch all contacts
            task = get_google_contacts.apply_async(
                queue='checkout',
                kwargs={'auth_token': auth_token})
            return self.json_response(
                ctx=None,
                task_id=task.id,
                status_url=reverse('contacts:google-invite'),
                status='RUNNING')
        return HttpResponseRedirect(reverse('customer:referrals-index'))

    def json_response(self, ctx, **payload):
        if ctx:
            contacts_html = render_to_string(
                self.template_name,
                RequestContext(self.request, ctx))
            payload['contacts_html'] = contacts_html
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")


