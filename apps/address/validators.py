from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

alphanumeric = RegexValidator(
    regex=r'^[a-zA-Z]*$',
    message=_("Only english characters allowed."),
    code='alphanumeric'
)

alphanumeric_and_space = RegexValidator(
    regex=r'^[a-zA-Z ]*$',
    message=_("Only english characters or space allowed."),
    code='alphanumeric_and_space'
)

alphanumeric_and_numbers = RegexValidator(
    regex=r'^[0-9a-zA-Z -.]*$',
    message=_("Only English characters, numbers, space or -. allowed."),
    code='alphanumeric_and_numbers'
)

alphanumeric_and_space_and_dash = RegexValidator(
    regex=r'^[a-zA-Z ]*$',
    message=_("Only english characters, - or space allowed."),
    code='alphanumeric_and_space_and_dash'
)

class AddressValidators(object):
    def add_validators(self, fields):
        #validate shipping address only contains english characters
        if 'line1' in fields:
            fields['line1'].validators = [alphanumeric_and_numbers]
        if 'line2' in fields:
            fields['line2'].validators = [alphanumeric_and_numbers]
        if 'line3' in fields:
            fields['line3'].validators = [alphanumeric_and_numbers]
        if 'state' in fields:
            fields['state'].validators = [alphanumeric_and_space]
            fields['state'].label = _("State")
        if 'first_name' in fields:
            fields['first_name'].validators = [alphanumeric_and_space]
        if 'last_name' in fields:
            fields['last_name'].validators = [alphanumeric_and_space]
        if 'country' in fields:
            fields['country'].empty_label = "---------"
        if 'postcode' in fields:
            fields['postcode'].label = _("Postcode")
