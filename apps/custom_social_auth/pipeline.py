from apps.user.uuid import generate_uuid
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from apps.customer.forms import generate_username
from social.pipeline.partial import partial
from oscar.apps.customer.signals import user_registered
from apps.customer.alerts import senders
from apps.user.models import PotentialUser
import logging

logger = logging.getLogger(__name__)


@partial
def require_extra_settings(strategy, details, user=None, is_new=False, *args, **kwargs):
    #collect extra data from new users only
    is_social_user_created = strategy.session_get('social_extra_settings_populated')
    #redirect new users to profile form
    if is_new and not is_social_user_created:
        #save details in session for next form initial values
        strategy.session_set('social_details', details)
        return HttpResponseRedirect(reverse('custom_social_auth:profile-form'))
    #continue with pipeline for registered users
    #reset session data
    if is_new:
        profile = strategy.session_pop('social_profile')
        user_details = strategy.session_pop('social_details')
        strategy.session_pop('social_extra_settings_populated')
        #update user email address with the data we collected from the user
        details['email'] = user_details['email']
        #pass needed data to next pipeline function
        return {
            'profile': profile,
            'first_name': user_details['first_name'],
            'last_name': user_details['last_name'],
            'mixpanel_anon_id': user_details['mixpanel_anon_id'],
            'register_type': user_details['register_type']
        }


def generate_new_username(strategy, details, user=None, *args, **kwargs):
    #we will use oscar's generate_username function to generate a unique
    #username to every social network user
    return {'username': generate_username()}


def save_profile(strategy, details, user=None, *args, **kwargs):
    """
    This is the last stage where we should have a newly created user and
    a profile, need to match between the user and the profile and save it to DB
    """
    def link_potential_user(user):
        PotentialUser.objects\
            .filter(email=user.email.lower())\
            .update(user=user)

    profile = kwargs.get('profile')
    first_name = kwargs.get('first_name')
    last_name = kwargs.get('last_name')
    mixpanel_anon_id = kwargs.get('mixpanel_anon_id')
    register_type = kwargs.get('register_type')

    if user and profile and first_name and last_name:
        #set user attribute and save profile
        profile.user = user
        profile.uuid = generate_uuid()
        profile.save()
        #set first name and last name of the user and save
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        #link user to potential user so we won't send the follow up email
        link_potential_user(user)
        #send registration email for new social networks user - for mixpanel processing to start
        fields = {
            'request': strategy.request,
            'mixpanel_anon_id': mixpanel_anon_id,
            'register_type': register_type
        }
        if 'social' in kwargs:
            fields['backend'] = kwargs['social'].provider.title()
        user_registered.send_robust(sender=strategy, user=user, profile=profile, **fields)
        senders.add_new_registration_notification(user)



