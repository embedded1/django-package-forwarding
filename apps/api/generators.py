from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from apps.user.models import Profile
from apps.user.uuid import generate_uuid
from apps.user import utils as user_utils
from django.utils.encoding import smart_str
from apps.utils import operation_suspended
from apps.customer.forms import generate_username
from django.conf import settings
from collections import OrderedDict
from apps.customer.tasks import (
    send_api_complete_registration_email,
    send_api_complete_registration_follow_up_email,
    send_api_email_confirmation_email,
    subscribe_user
)
import hashlib
import logging


logger = logging.getLogger("management_commands")

class ForwardingAddressGenerator(object):
    issuer_keys = {
        'purse': 'PURSE_API_KEY',
        'shopify': 'SHOPIFY_API_KEY',
        'amazon': 'AMAZON_API_KEY',
    }

    def is_signature_valid(self, signature_to_verify, issuer, data):
        if issuer == 'amazon':
            return True
        if not signature_to_verify:
            return False
        calculated_signature = self.calculate_signature(issuer, data)
        return calculated_signature and signature_to_verify == calculated_signature

    def calculate_signature(self, issuer, data):
        sig_data = ''
        try:
            key = getattr(settings, self.issuer_keys[issuer])
        except (KeyError, AttributeError):
            return None
        ordered_data = OrderedDict(sorted(data.items()))
        for k, v in ordered_data.iteritems():
            sig_data += "%s%s" % (k, smart_str(v))
        return hashlib.sha256(key + sig_data).hexdigest()

    def get_forwarding_addresses(self, first_name, last_name, profile):
        forwarding_addresses = []
        warehouse_addrs = user_utils.get_warehouse_address()
        for addr in profile.generate_virtual_addresses(warehouse_addrs):
            forwarding_addresses.append({
                'first_name': first_name,
                'last_name': last_name,
                'address1': addr.line1,
                'address2': addr.line2,
                'city': addr.city,
                'state': addr.state,
                'state_code': 'CA',#get_us_state_code(addr.state),
                'zip': addr.postcode,
                'country': addr.country.printable_name,
                'phone': addr.phone_number.as_national
            })
        return forwarding_addresses

    def generate_address(self, data):
        issuer = data.get('issuer', '').lower()
        req_signature = data.pop('signature', None)
        if not operation_suspended() and self.is_signature_valid(req_signature, issuer, data):
            email = data.get('email')
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            password = data.get('password')
            if not all([first_name, last_name, email, password, issuer]):
                return [], 200
            try:
                user = User.objects\
                        .select_related('profile')\
                        .get(email=email)
                profile = user.get_profile()
                status = 200
            except User.MultipleObjectsReturned:
                # take the first account
                users = User.objects\
                        .select_related('profile')\
                        .filter(email=email)
                user = users[0]
                profile = user.get_profile()
                status = 200
            except User.DoesNotExist:
                user = User.objects.create(
                    email=email,
                    first_name=first_name[:30],
                    last_name=last_name[:30],
                    username=generate_username(),
                    password=make_password(password))
                #create Profile
                profile = Profile(
                    uuid=generate_uuid(),
                    user=user,
                    registration_type=issuer
                )

                # check if user is qualified for exclusive club's offers
                # auto-enrol
                club = profile.get_exclusive_club()
                if club:
                    profile.qualified_for_exclusive_club_offers = True

                #save profile
                profile.save()

                if password:
                    #we got all required data, the account is active
                    #add user to the unconfirmed group
                    list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_USERS]
                    unconfirmed_group_id = settings.MAILCHIMP_LIST_GROUPS[list_id][settings.MAILCHIMP_GROUP_UNCONFIRMED]
                    group_settings = {unconfirmed_group_id: True}
                    try:
                        api_group_id = settings.MAILCHIMP_LIST_GROUPS[list_id][issuer]
                        group_settings[api_group_id] = True
                    except KeyError:
                        logger.error("invalid issuer for mailchimp group %s", issuer)

                    subscribe_user.apply_async(
                        kwargs={
                            'user': user,
                            'list_id': list_id,
                            'group_settings': group_settings,
                            'is_conf_url_required': True
                        },
                        queue='analytics'
                    )

                #send email to user with a link to complete the registration process (selection extra services)
                #we use celery to speed up the response
                #send_api_complete_registration_email.apply_async(queue='emails',
                #                                                 kwargs={'user': user,
                #                                                         'issuer': issuer})
                send_api_email_confirmation_email.apply_async(queue='emails',
                                                              kwargs={'user': user,
                                                                      'profile': profile,
                                                                      'issuer': issuer})
                #set up a follow-up email if the the signup process didn't complete in 1 day
                send_api_complete_registration_follow_up_email.apply_async(queue='emails',
                                                                           kwargs={'user_id': user.id,
                                                                                   'issuer': issuer},
                                                                           countdown=60 * 60 * 12) #12 hours delay
                #mark that a new resource was created
                status = 201
            addresses = self.get_forwarding_addresses(first_name, last_name, profile)
            return addresses, status
        return None, 403
