from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from decimal import Decimal as D
from django.conf import settings
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _
from pinax.referrals.models import Referral, ReferralResponse
from apps.catalogue.abstract_models import (
    AbstractSpecialRequests,
    AuthenticationStatus,
    AuthenticationDocument)
from apps.utils import operation_suspended


class Profile(AbstractSpecialRequests):
    """
    profile model that adds uuid for easy matching package to user
    """
    EXCLUSIVE_CLUBS = {
        'purse': {'services': ('express_checkout')}
    }
    PERSONAL, BUSINESS, AFFILIATE = ("Personal", "Business", "Affiliate")
    ACCOUNT_TYPE_CHOICES = (
        (PERSONAL, _(PERSONAL)),
        (BUSINESS, _(BUSINESS)),
        (AFFILIATE, _(AFFILIATE)),
    )
    FACEBOOK, TWITTER, EMAIL = ("Facebook", "Twitter", "Email")
    REGISTRATION_METHOD_CHOICES = (
        (EMAIL, EMAIL),
        (FACEBOOK, FACEBOOK),
        (TWITTER, TWITTER),
    )
    user = models.OneToOneField(
        User, related_name="profile")
    uuid = models.CharField(
        max_length=64, db_index=True,
        verbose_name='UUID', unique=True)
    package_tracking = models.BooleanField(
        verbose_name=_('Package Tracking'), default=False,
        help_text=_("Know where your package is with our automated and integrated tracking system"))
    is_consolidate_every_new_package = models.BooleanField(
        _('Package Consolidation ($2/package)'), default=False,
        help_text=_("Consolidate multiple packages into one container and save shipping costs"))
    email_confirmed = models.BooleanField(
        _("email address confirmed?"), default=False)
    country = models.CharField(
        _('Country Code'), max_length=3, blank=True, null=True)
    city = models.CharField(
        _("City"), max_length=255, blank=True, null=True)
    ip = models.GenericIPAddressField(
        _("IP Address"), blank=True, null=True)
    proxy_score = models.DecimalField(
        _("Maxmind proxy score"), max_digits=5,
        decimal_places=2, blank=True, null=True)
    tour_started = models.BooleanField(
        _("Welcome tour started?"), default=False)
    tour_end_step = models.SmallIntegerField(
        _("Welcome tour end step"), default=0)
    remaining_invites = models.SmallIntegerField(
        _("Remaining referral invites per day"),
        default=settings.DAILY_REFERRAL_INVITES_QUOTA)
    referral = models.OneToOneField(
        Referral, blank=True, null=True)
    short_referral_url = models.URLField(
        max_length=200, blank=True, null=True)
    added_chrome_extension = models.BooleanField(
         _("User added the Chrome extension?"), default=False)
    date_chrome_extension_added = models.DateTimeField(
        _("Date user added the Chrome extension"), null=True, blank=True)
    account_type = models.CharField(
        _('Account type'), max_length=32,
        choices=ACCOUNT_TYPE_CHOICES,
        default=ACCOUNT_TYPE_CHOICES[0][0])
    is_control_panel_modal_shown = models.BooleanField(
        _('Control panel video modal shown to the user?'), default=False)
    is_account_setup_completed = models.BooleanField(
        _('Account setup completed?'), default=False)
    qualified_for_black_friday_promo = models.BooleanField(
        _('Is user qualified for black friday promotion?'), default=False)
    qualified_for_exclusive_club_offers = models.BooleanField(
        _('Is user qualified for exclusive club offers?'), default=False)
    registration_type = models.CharField(
        _("Registration Type"), max_length=16,
        default='N/A')
    registration_method = models.CharField(
        _("Registration Method"), max_length=32,
        choices=REGISTRATION_METHOD_CHOICES,
        default=REGISTRATION_METHOD_CHOICES[0][0])
    external_referer = models.URLField(
        _("External referer"), null=True, blank=True)


    def __unicode__(self):
        return u"%s profile" % self.user.get_full_name()

    def _url(self, type):
        path = '/{}/{}'.format(type, self.referral.code)
        domain = Site.objects.get_current().domain
        protocol = "https" if settings.PINAX_REFERRALS_SECURE_URLS else "http"
        return "{}://{}{}".format(protocol, domain, path)

    @property
    def referral_link(self):
        if self.short_referral_url:
            return self.short_referral_url
        return self._url('referrals')

    @property
    def affiliate_link(self):
        return self._url('affiliates')

    def is_business_account(self):
        return self.account_type == self.BUSINESS

    def is_affiliate_account(self):
        return self.account_type == self.AFFILIATE

    def verification_status(self):
        if self.has_account_status():
            return self.account_status.verification_status
        return _("Verified")

    def registered_behind_proxy(self):
        return self.proxy_score is not None and self.proxy_score > 0

    def is_predefined_consolidation(self):
        return self.is_consolidate_every_new_package

    def get_model_attrs(self, model_keys):
        return dict((k, v) for k, v in self.__dict__.iteritems() if k in model_keys)

    def generate_virtual_addresses(self, warehouse_addrs):
        for warehouse_addr in warehouse_addrs:
            #line2 the suite template, we only need to fill in the
            #suite number
            warehouse_addr.line2 = warehouse_addr.line2 % self.uuid
            warehouse_addr.first_name = self.user.first_name
            warehouse_addr.last_name = self.user.last_name
        return warehouse_addrs

    def has_account_status(self):
        try:
            self.account_status
        except AccountStatus.DoesNotExist:
            return False
        else:
            return self.has_account_status is not None

    def signed_up_through_api(self):
        return self.registration_type.lower() in ['purse', 'amazon', 'shopify']

    def hide_us_address(self):
        return operation_suspended(self.user)

    def user_manually_verified(self):
        return self.has_account_status() and \
               self.account_status.verification_status == AccountStatus.VERIFIED

    def account_verification_in_process(self):
        if not self.has_account_status():
            return False
        return self.account_status.verification_status == AccountStatus.VERIFICATION_IN_PROGRESS

    def account_verification_failed(self):
        if not self.has_account_status():
            return False
        return self.account_status.verification_status == AccountStatus.VERIFICATION_FAILED

    def account_verification_required(self):
        if not self.has_account_status():
            return False
        return self.account_status.verification_status == AccountStatus.UNVERIFIED

    def account_verification_requires_more_docs(self):
        if not self.has_account_status():
            return False
        return self.account_status.verification_status == AccountStatus.WAITING_FOR_MORE_DOCUMENTS

    def account_verified(self):
        """
        Account is consider verified if it has no account status object
        or it does have and the verification status is VERIFIED
        We create an AccountStatus only if the account needs to be verified
        """
        if not self.has_account_status():
            return True
        return self.account_status.verification_status == AccountStatus.VERIFIED

    def referral_unredeemed_credit(self):
        total_unredeemed_referral_credit = self.rewards_referralreward_related\
            .filter(date_redeemed__isnull=True, is_active=True)\
            .aggregate(total_credit=Sum('amount'))['total_credit']

        if total_unredeemed_referral_credit is None:
            total_unredeemed_referral_credit = D('0.00')

        return total_unredeemed_referral_credit

    def referral_redeemed_credit(self):
        total_redeemed_referral_credit = self.rewards_referralreward_related\
            .filter(date_redeemed__isnull=False, is_active=True)\
            .aggregate(total_credit=Sum('amount'))['total_credit']

        if total_redeemed_referral_credit is None:
            total_redeemed_referral_credit = D('0.00')

        return total_redeemed_referral_credit

    def loyalty_unredeemed_credit(self):
        total_unredeemed_loyalty_credit = self.rewards_loyaltyreward_related\
            .filter(date_redeemed__isnull=True, is_active=True)\
            .aggregate(total_credit=Sum('amount'))['total_credit']

        if total_unredeemed_loyalty_credit is None:
            total_unredeemed_loyalty_credit = 0

        return total_unredeemed_loyalty_credit

    def total_unredeemed_credit(self):
        """
        Sum up all unredeemed but active credits
        """
        return self.referral_unredeemed_credit() + \
               self.loyalty_unredeemed_credit()

    def is_registered_through_referral_link(self):
        """
        Return True if user registered through referral link
        """
        try:
            ReferralResponse.objects.get(
                user=self.user,
                action='USER_SIGNUP')
        except ReferralResponse.DoesNotExist:
            return False
        return True

    def is_qualified_for_exclusive_club_offers(self, club):
        return self.qualified_for_exclusive_club_offers and\
               self.registration_type.lower() == club

    def get_exclusive_club(self):
        active_clubs = ('purse',)
        for club in active_clubs:
            if self.registration_type.lower() == club:
                return club
        return None

    def get_exclusive_club_services_offer(self):
        """
        Return a list of free services that come along with the exclusive club
        """
        club = self.get_exclusive_club()
        services = []

        if club:
            if not self.is_qualified_for_exclusive_club_offers(club):
                return services
            services.append(self.EXCLUSIVE_CLUBS[club]['services'])

        return services



class AccountStatus(AuthenticationStatus):
    profile = models.OneToOneField(
        'user.Profile', related_name='account_status')

    def __unicode__(self):
        return u"Account status of %s" % self.profile

    class Meta:
        verbose_name = _('Account Status')
        verbose_name_plural = _('Accounts Status')


class AccountAuthenticationDocument(AuthenticationDocument):
    account_status = models.ForeignKey(
        'user.AccountStatus', related_name='auth_documents')

    def __unicode__(self):
        return u"%s document of %s" % (self.category, self.account_status)

    class Meta:
        verbose_name = _('Account Authentication Document')
        verbose_name_plural = _('Account Authentication Documents')


class GoogleAnalyticsData(models.Model):
    profile = models.OneToOneField(
       'user.Profile', related_name='adwords_data')
    number = models.CharField(
        max_length=256, verbose_name='Campaign number',
        null=True, db_index=True)
    source = models.CharField(
        max_length=256, verbose_name='source',
        null=True, db_index=True)
    medium = models.CharField(
        max_length=256, verbose_name='medium',
        null=True, db_index=True)
    term = models.CharField(
        max_length=256, verbose_name='term',
        null=True, db_index=True)
    content = models.CharField(
        max_length=256, verbose_name='content',
        null=True, db_index=True)
    name = models.CharField(
        max_length=256, verbose_name='name',
         null=True, db_index=True)

    def __unicode__(self):
        return u"Google Analytics source %s data" % self.source

    class Meta:
        verbose_name = _('Google Analytics Data')


class PotentialUser(models.Model):
    user = models.ForeignKey(User, null=True)
    email = models.EmailField(
        _('e-mail address'))
    date_visited = models.DateTimeField(
        _("Date user visited website"),
        auto_now_add=True)

    def __unicode__(self):
        return u"%s" % self.email

    class Meta:
        verbose_name = _('Potential User')
        verbose_name_plural = _('Potential User')

#Show user full name instead of the auto generated username
User.__unicode__ = User.get_full_name





