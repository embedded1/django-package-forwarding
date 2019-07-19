from oscar.apps.address.abstract_models import AbstractUserAddress, AbstractShippingAddress
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core import exceptions

class PostCodesRegex(object):
    # Regex for each country. Not listed countries don't use postcodes
    # Based on http://en.wikipedia.org/wiki/List_of_postal_codes
    POSTCODES_REGEX = {
        'AC': r'^[A-Z]{4}[0-9][A-Z]$',
        'AD': r'^AD[0-9]{3}$',
        'AF': r'^[0-9]{4}$',
        'AI': r'^AI-2640$',
        'AL': r'^[0-9]{4}$',
        'AM': r'^[0-9]{4}$',
        'AR': r'^([0-9]{4}|[A-Z][0-9]{4}[A-Z]{3})$',
        'AS': r'^[0-9]{5}(-[0-9]{4}|-[0-9]{6})?$',
        'AT': r'^[0-9]{4}$',
        'AU': r'^[0-9]{4}$',
        'AX': r'^[0-9]{5}$',
        'AZ': r'^AZ[0-9]{4}$',
        'BA': r'^[0-9]{5}$',
        'BB': r'^BB[0-9]{5}$',
        'BD': r'^[0-9]{4}$',
        'BE': r'^[0-9]{4}$',
        'BG': r'^[0-9]{4}$',
        'BH': r'^[0-9]{3,4}$',
        'BL': r'^[0-9]{5}$',
        'BM': r'^[A-Z]{2}([0-9]{2}|[A-Z]{2})',
        'BN': r'^[A-Z]{2}[0-9]{4}$',
        'BO': r'^[0-9]{4}$',
        'BR': r'^[0-9]{5}(-[0-9]{3})?$',
        'BT': r'^[0-9]{3}$',
        'BY': r'^[0-9]{6}$',
        'CA': r'^[A-Z][0-9][A-Z][0-9][A-Z][0-9]$',
        'CC': r'^[0-9]{4}$',
        'CH': r'^[0-9]{4}$',
        'CL': r'^([0-9]{7}|[0-9]{3}-[0-9]{4})$',
        'CN': r'^[0-9]{6}$',
        'CO': r'^[0-9]{6}$',
        'CR': r'^[0-9]{4,5}$',
        'CU': r'^[0-9]{5}$',
        'CV': r'^[0-9]{4}$',
        'CX': r'^[0-9]{4}$',
        'CY': r'^[0-9]{4}$',
        'CZ': r'^[0-9]{5}$',
        'DE': r'^[0-9]{5}$',
        'DK': r'^[0-9]{4}$',
        'DO': r'^[0-9]{5}$',
        'DZ': r'^[0-9]{5}$',
        'EC': r'^EC[0-9]{6}$',
        'EE': r'^[0-9]{5}$',
        'EG': r'^[0-9]{5}$',
        'ES': r'^[0-9]{5}$',
        'ET': r'^[0-9]{4}$',
        'FI': r'^[0-9]{5}$',
        'FK': r'^[A-Z]{4}[0-9][A-Z]{2}$',
        'FM': r'^[0-9]{5}(-[0-9]{4})?$',
        'FO': r'^[0-9]{3}$',
        'FR': r'^[0-9]{5}$',
        'GA': r'^[0-9]{2}.*[0-9]{2}$',
        'GB': r'^[A-Z][A-Z0-9]{1,3}[0-9][A-Z]{2}$',
        'GE': r'^[0-9]{4}$',
        'GF': r'^[0-9]{5}$',
        'GG': r'^([A-Z]{2}[0-9]{2,3}[A-Z]{2})$',
        'GI': r'^GX111AA$',
        'GL': r'^[0-9]{4}$',
        'GP': r'^[0-9]{5}$',
        'GR': r'^[0-9]{5}$',
        'GS': r'^SIQQ1ZZ$',
        'GT': r'^[0-9]{5}$',
        'GU': r'^[0-9]{5}$',
        'GW': r'^[0-9]{4}$',
        'HM': r'^[0-9]{4}$',
        'HN': r'^[0-9]{5}$',
        'HR': r'^[0-9]{5}$',
        'HT': r'^[0-9]{4}$',
        'HU': r'^[0-9]{4}$',
        'ID': r'^[0-9]{5}$',
        'IL': r'^[0-9]{7}$',
        'IM': r'^IM[0-9]{2,3}[A-Z]{2}$$',
        'IN': r'^[0-9]{6}$',
        'IO': r'^[A-Z]{4}[0-9][A-Z]{2}$',
        'IQ': r'^[0-9]{5}$',
        'IR': r'^[0-9]{5}-[0-9]{5}$',
        'IS': r'^[0-9]{3}$',
        'IT': r'^[0-9]{5}$',
        'JE': r'^JE[0-9]{2}[A-Z]{2}$',
        'JM': r'^JM[A-Z]{3}[0-9]{2}$',
        'JO': r'^[0-9]{5}$',
        'JP': r'^[0-9]{3}-?[0-9]{4}$',
        'KE': r'^[0-9]{5}$',
        'KG': r'^[0-9]{6}$',
        'KH': r'^[0-9]{5}$',
        'KR': r'^[0-9]{3}-?[0-9]{3}$',
        'KY': r'^KY[0-9]-[0-9]{4}$',
        'KZ': r'^[0-9]{6}$',
        'LA': r'^[0-9]{5}$',
        'LB': r'^[0-9]{8}$',
        'LI': r'^[0-9]{4}$',
        'LK': r'^[0-9]{5}$',
        'LR': r'^[0-9]{4}$',
        'LS': r'^[0-9]{3}$',
        'LT': r'^[0-9]{5}$',
        'LU': r'^[0-9]{4}$',
        'LV': r'^LV-[0-9]{4}$',
        'LY': r'^[0-9]{5}$',
        'MA': r'^[0-9]{5}$',
        'MC': r'^980[0-9]{2}$',
        'MD': r'^MD-?[0-9]{4}$',
        'ME': r'^[0-9]{5}$',
        'MF': r'^[0-9]{5}$',
        'MG': r'^[0-9]{3}$',
        'MH': r'^[0-9]{5}$',
        'MK': r'^[0-9]{4}$',
        'MM': r'^[0-9]{5}$',
        'MN': r'^[0-9]{5}$',
        'MP': r'^[0-9]{5}$',
        'MQ': r'^[0-9]{5}$',
        'MT': r'^[A-Z]{3}[0-9]{4}$',
        'MV': r'^[0-9]{4,5}$',
        'MX': r'^[0-9]{5}$',
        'MY': r'^[0-9]{5}$',
        'MZ': r'^[0-9]{4}$',
        'NA': r'^[0-9]{5}$',
        'NC': r'^[0-9]{5}$',
        'NE': r'^[0-9]{4}$',
        'NF': r'^[0-9]{4}$',
        'NG': r'^[0-9]{6}$',
        'NI': r'^[0-9]{3}-[0-9]{3}-[0-9]$',
        'NL': r'^[0-9]{4}[A-Z]{2}$',
        'NO': r'^[0-9]{4}$',
        'NP': r'^[0-9]{5}$',
        'NZ': r'^[0-9]{4}$',
        'OM': r'^[0-9]{3}$',
        'PA': r'^[0-9]{6}$',
        'PE': r'^[0-9]{5}$',
        'PF': r'^[0-9]{5}$',
        'PG': r'^[0-9]{3}$',
        'PH': r'^[0-9]{4}$',
        'PK': r'^[0-9]{5}$',
        'PL': r'^[0-9]{2}-?[0-9]{3}$',
        'PM': r'^[0-9]{5}$',
        'PN': r'^[A-Z]{4}[0-9][A-Z]{2}$',
        'PR': r'^[0-9]{5}$',
        'PT': r'^[0-9]{4}(-?[0-9]{3})?$',
        'PW': r'^[0-9]{5}$',
        'PY': r'^[0-9]{4}$',
        'RE': r'^[0-9]{5}$',
        'RO': r'^[0-9]{6}$',
        'RS': r'^[0-9]{5}$',
        'RU': r'^[0-9]{6}$',
        'SA': r'^[0-9]{5}$',
        'SD': r'^[0-9]{5}$',
        'SE': r'^[0-9]{5}$',
        'SG': r'^([0-9]{2}|[0-9]{4}|[0-9]{6})$',
        'SH': r'^(STHL1ZZ|TDCU1ZZ)$',
        'SI': r'^(SI-)?[0-9]{4}$',
        'SK': r'^[0-9]{5}$',
        'SM': r'^[0-9]{5}$',
        'SN': r'^[0-9]{5}$',
        'SV': r'^01101$',
        'SZ': r'^[A-Z][0-9]{3}$',
        'TC': r'^TKCA1ZZ$',
        'TD': r'^[0-9]{5}$',
        'TH': r'^[0-9]{5}$',
        'TJ': r'^[0-9]{6}$',
        'TM': r'^[0-9]{6}$',
        'TN': r'^[0-9]{4}$',
        'TR': r'^[0-9]{5}$',
        'TT': r'^[0-9]{6}$',
        'TW': r'^[0-9]{5}$',
        'UA': r'^[0-9]{5}$',
        'US': r'^[0-9]{5}(-[0-9]{4}|-[0-9]{6})?$',
        'UY': r'^[0-9]{5}$',
        'UZ': r'^[0-9]{6}$',
        'VA': r'^00120$',
        'VC': r'^VC[0-9]{4}',
        'VE': r'^[0-9]{4}[A-Z]?$',
        'VG': r'^VG[0-9]{4}$',
        'VI': r'^[0-9]{5}$',
        'VN': r'^[0-9]{6}$',
        'WF': r'^[0-9]{5}$',
        'XK': r'^[0-9]{5}$',
        'YT': r'^[0-9]{5}$',
        'ZA': r'^[0-9]{4}$',
        'ZM': r'^[0-9]{5}$',
    }

class UserAddress(PostCodesRegex, AbstractUserAddress):
    #: Whether this address is merchant address
    #: to support return to merchant option
    is_merchant = models.BooleanField(
        _("Merchant address?"), default=False)

    def ensure_postcode_is_valid_for_country(self):
        """
        Validate postcode given the country
        Only when postcode was missing and the addresses in country
        require a postcode
        Currently, we removed Oscar's postcode validation
        """
        if not self.postcode and self.country_id:
            country_code = self.country.iso_3166_1_a2
            regex = self.POSTCODES_REGEX.get(country_code, None)
            if regex:
                msg = _("Addresses in %(country)s require a valid postcode") \
                    % {'country': self.country}
                raise exceptions.ValidationError(msg)

    def _ensure_defaults_integrity(self):
        if self.is_default_for_shipping:
            self.__class__._default_manager\
                .filter(user=self.user, is_merchant=self.is_merchant, is_default_for_shipping=True)\
                .update(is_default_for_shipping=False)
        if self.is_default_for_billing:
            self.__class__._default_manager\
                .filter(user=self.user, is_merchant=self.is_merchant, is_default_for_billing=True)\
                .update(is_default_for_billing=False)

    def full_address_format(self):
        fields = [self.salutation, self.line1]
        if self.line2:
            fields.append(self.line2)
        fields.append(self.join_fields(
            ('line4', 'state', 'postcode'),
            separator=u" "))
        try:
            fields.append(self.country.name)
        except exceptions.ObjectDoesNotExist:
            pass
        try:
            fields.append(self.phone_number.as_international)
        except AttributeError:
            pass
        return [f.strip() for f in fields]


class AffiliatorAddress(PostCodesRegex, AbstractShippingAddress):
    user = models.OneToOneField(
        'auth.user', related_name='affiliate_address',
        verbose_name=_("User"))

    def __unicode__(self):
        return u"Affiliator %s address" % self.user

    class Meta:
        verbose_name = _("Affiliator address")
        verbose_name_plural = _("Affiliator addresses")

from oscar.apps.address.models import *
