from oscar.apps.customer import abstract_models
from django.db import models
from apps.utils import get_site_properties
from django.utils.translation import ugettext_lazy as _


class Email(abstract_models.AbstractEmail):
    pass


class CommunicationEventType(abstract_models.AbstractCommunicationEventType):
    def get_messages(self, ctx=None):
        """
        Add current site url
        """
        if ctx is None:
            ctx = {}
        ctx.update(get_site_properties())
        headers = ctx.pop('headers', {})
        messages = super(CommunicationEventType, self).get_messages(ctx)
        #add headers (if any)
        messages['headers'] = headers
        return messages


class Notification(abstract_models.AbstractNotification):
    pass


class ProductAlert(abstract_models.AbstractProductAlert):
    pass

class CustomerFeedback(models.Model):
    GREAT, GOOD, BAD = "Great", "Good", "Bad"
    TYPE_CHOICES = (
        (GREAT, _(GREAT)),
        (GOOD, _(GOOD)),
        (BAD, _(BAD)))
    customer = models.ForeignKey(
        'auth.User', related_name='feedbacks', null=True)
    order = models.OneToOneField(
        'order.Order', related_name='feedback')
    question1 = models.TextField(
        verbose_name=_('Describe why you feel that forwarding your parcel with us was successful'),
        help_text=_("With your permission, your thoughts will be posted on our website."))
    question2 = models.TextField(
        verbose_name=_('What would you like to see us add to the USendHome experience?'), blank=True, null=True,
        help_text=_("This can be anything from new shipping carriers to new services you would like to see."))
    question3 = models.TextField(
        verbose_name=_('What can we do to improve the package delivery checkout process?'), blank=True, null=True,
        help_text=_("Let us know how to make our checkout process easier to complete."))
    quote_testimonial = models.BooleanField(
        verbose_name=_("Quote testimonial"),
        default=True)
    type = models.CharField(
        verbose_name=_("Feedback type"), max_length=32,
        choices=TYPE_CHOICES, blank=True
    )
    date_created = models.DateTimeField(
        _("Date created"), auto_now_add=True)

    def __unicode__(self):
        return u"Feedback for order #%s" % self.order.number

    @property
    def testimonial(self):
        return self.question1


from .alerts.receivers import *
