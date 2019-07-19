from django.views.generic import RedirectView
from django.core.urlresolvers import reverse
from django.contrib import messages
from .mixins import VerificationStatusUpdateView
from apps.order.models import Order
from apps.order.utils import OrderValidator
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _
from apps.user.models import AccountStatus
from apps.catalogue.models import Product, AdditionalPackageReceiver
import logging


logger = logging.getLogger("management_commands")


class UpdatePendingFraudCheckOrder(RedirectView):
    permanent = False
    model = Order

    def suspend_account(self, user):
        user.is_active = False
        user.save()

    def get_redirect_url(self, **kwargs):
        next = self.request.session.get('REPORT_REFERER', reverse('dashboard:reports-index'))
        try:
            order = self.model.objects.get(number=kwargs['order_num'])
        except self.model.DoesNotExist:
            messages.error(self.request, "Failed, order not found")
            return next

        #we just update the proxy data need to run the order through
        #all validations test
        pay_key = order.sources.all()[0].reference
        OrderValidator().validate_order(order=order, key=pay_key)
        messages.success(self.request, "Operation succeeded")
        return next


class ResumeUserAccountView(RedirectView):
    permanent = False
    model = User

    def get_redirect_url(self, **kwargs):
        next = self.request.session.get('REPORT_REFERER', reverse('dashboard:reports-index'))
        try:
            user = self.model.objects.get(id=kwargs['user_num'])
        except self.model.DoesNotExist:
            messages.error(self.request, "Failed, user not found")
            return next

        #resume customer account
        user.is_active = True
        user.save()

        messages.success(self.request, "Operation succeeded")
        return next

class UpdateAccountStatus(VerificationStatusUpdateView):
    model = AccountStatus
    notify_cb_name = 'send_account_verification_verdict_email'
    user_field_name = 'profile.user'

    def get_redirect_url(self, **kwargs):
        """
        Here we have some extra work because an order triggers the account verification
        therefore, based on our decision we need to update the order
        """
        url = super(UpdateAccountStatus, self).get_redirect_url(**kwargs)

        if self.obj is None:
            return url

        user = self.obj.profile.user

        try:
            order = user.orders.get(status='Pending fraud check')
        except Order.MultipleObjectsReturned:
            logger.error("We found more than 1 order in pending fraud"
                         " check status, user = %s" % user)
            order = user.orders.filter(
                status='Pending fraud check').order_by(
                '-date_placed')[0]
        except Order.DoesNotExist:
            messages.error(self.request, "We couldn't found any pending fraud"
                         " check order for user %s" % user)
            return self.request.session.get('REPORT_REFERER', reverse('dashboard:reports-index'))

        pay_key = order.sources.all()[0].reference
        if self.obj.verification_status == self.model.VERIFIED:
            #we need to run through the validate_order flow once again
            #since the order can ben cancelled or completed
            OrderValidator().validate_order(order=order, key=pay_key)
        elif  self.obj.verification_status == self.model.VERIFICATION_FAILED:
            order.set_status('Cancelled')
            cancelled_reason = _("suspect it is fraudulent")
            OrderValidator().cancel_order(
                order=order,
                key=pay_key,
                cancelled_reason=cancelled_reason,
                suspend_account=True)

        return url



class UpdateAdditionalPackageReceiver(VerificationStatusUpdateView):
    model = AdditionalPackageReceiver
    notify_cb_name = 'send_additional_receiver_verification_verdict_email'
    user_field_name = 'package_owner'

    def get_redirect_url(self, **kwargs):
        """
        We need to take care of a case where the additional receiver verification
        failed, in that case we must change all additional receiver packages status to pending
        to allow them to be sent back to the senders
        This is the only action we permit for unverified additional receivers
        """
        url = super(UpdateAdditionalPackageReceiver, self).get_redirect_url(**kwargs)

        if self.obj is None:
            return url

        if  self.obj.verification_status == self.model.VERIFICATION_FAILED:
            Product.in_store_packages\
                .filter(additional_receiver=self.obj).update(status='pending')

        return url