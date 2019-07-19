from packageshop.celery import app
from gdata.client import RequestError
import gdata.contacts, gdata.contacts.client
from django.conf import settings
from django.utils import simplejson as json
from django.template import Context, loader
from django.core.exceptions import ValidationError
from post_office import mail
import re

EMAIL_REGEX = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]+$")


@app.task(soft_time_limit=30)
def get_google_contacts(auth_token):
    def process_feed(feed):
        contacts = []
        for entry in feed.entry:
            email_address = None
            for email in entry.email:
                if email.primary and email.primary == 'true':
                    email_address = email.address
                    break
            if email_address:
                contacts.append({
                    'name': entry.name.full_name.text if entry.name else '',
                    'email': email_address
                })
        return contacts

    #Create a data client, in this case for the Contacts API
    gd_client = gdata.contacts.client.ContactsClient()
    #Authorize it with your authentication token
    auth_token.authorize(gd_client)
    #get up to 500 contacts at once
    query = gdata.contacts.client.ContactsQuery()
    query.max_results = 500
    #Get the data feed
    try:
        feed = gd_client.GetContacts(q=query)
    except RequestError:
        #force the user to re-authenticate
        return None
    return process_feed(feed)

@app.task(soft_time_limit=30)
def email_contacts(friend_name, referral_link, contact_emails):
    emails = []
     # Load templates
    email_subject_tpl = loader.get_template('customer/emails/referrals/invite_subject.txt')
    email_body_tpl = loader.get_template('customer/emails/referrals/invite_body.txt')
    email_body_html_tpl = loader.get_template('customer/emails/referrals/invite_body.html')

    ctx = Context({
        'friend_name': friend_name,
        'referral_link': referral_link
    })

    subject = email_subject_tpl.render(ctx).strip()
    body = email_body_tpl.render(ctx)
    html_body = email_body_html_tpl.render(ctx)

    for contact_email in contact_emails:
        #run a sanity test to make sure the email address is valid
        if EMAIL_REGEX.match(contact_email):
            # Build email and add to list
            email = {
                'recipients': [contact_email],
                'sender': settings.OSCAR_FROM_EMAIL,
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            #add category for sendgrid analytics
            if not settings.DEBUG:
                email['headers'] = {'X-SMTPAPI': json.dumps({"category": "Friend Invite"})}
            emails.append(email)

    #we use celery to dispatch emails, therefore we iterate over all emails and add
    #each one of them to the task queue,send_many doesn't work with priority = now
    #therefore, we use the regular send mail
    for email in emails:
        try:
            mail.send(**email)
        except ValidationError, e:
            pass