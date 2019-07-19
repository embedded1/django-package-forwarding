from envelope.forms import ContactForm
from django.utils.translation import ugettext as _


class ContactUsForm(ContactForm):
    template_name = 'envelope/email_body.html'

    def __init__(self, *args, **kwargs):
        super(ContactUsForm, self).__init__(*args, **kwargs)
        #remove category field
        #self.fields.pop('category')
        #set placeholder attributes
        self.fields['sender'].widget.attrs['placeholder'] = _('Name')
        self.fields['email'].widget.attrs['placeholder'] = _("Email Address")
        self.fields['subject'].widget.attrs['placeholder'] = _("Subject")
        self.fields['message'].widget.attrs['placeholder'] = _("Message")
        #make all fields required
        self.fields['subject'].required = True
        self.fields['email'].required = True
        self.fields['subject'].required = True
        self.fields['message'].required = True