from django.db.models import get_model
from django.conf import settings
from apps.catalogue.utils import create_category
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _


Range = get_model('offer', 'Range')
CoverageCondition = get_model('offer', 'CoverageCondition')
PercentageDiscountBenefit = get_model('offer', 'PercentageDiscountBenefit')
ConditionalOffer = get_model('offer', 'ConditionalOffer')

class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Create special requests offers")

    def flush_special_requests_offers(self):
        Range.objects.all().delete()
        CoverageCondition.objects.all().delete()
        PercentageDiscountBenefit.objects.all().delete()
        ConditionalOffer.objects.all().delete()


    def handle(self, **options):
        #self.flush_special_requests_offers()
        #offers work on categories, therefore we need to create categories for fees we would like
        #to have discounts for
        predefined_special_requests_category = create_category('predefined_special_requests_fee')
        create_category('fee')
        special_requests_category =  create_category('special_requests_fee')
        #create range that includes all predefined special requests
        predefined_special_requests_range, _ = Range.objects.get_or_create(
            name="predefined_special_requests")
        predefined_special_requests_range.included_categories.add(
            predefined_special_requests_category)
        #create range that includes all non predefined special requests
        special_requests_range, _ = Range.objects.get_or_create(
            name="special_requests")
        special_requests_range.included_categories.add(
            special_requests_category)
        #create conditions for both
        predefined_special_requests_condition, _ = CoverageCondition.objects.get_or_create(
            type='Coverage', range=predefined_special_requests_range, value=1)
        special_requests_condition, _ = CoverageCondition.objects.get_or_create(
            type='Coverage', range=special_requests_range, value=2)
        #create both benefits
        predefined_special_requests_benefit, _ = PercentageDiscountBenefit.objects.get_or_create(
            type='Percentage', range=predefined_special_requests_range, value=settings.SPECIAL_REQUESTS_PREDEFINED_DISCOUNT)
        special_requests_benefit, _ = PercentageDiscountBenefit.objects.get_or_create(
            type='Percentage', range=special_requests_range, value=settings.SPECIAL_REQUESTS_BUNDLE_DISCOUNT)
        #create conditional offers
        try:
            ConditionalOffer.objects.get(name='Bundled Extra Services')
        except ConditionalOffer.DoesNotExist:
            ConditionalOffer.objects.create(
                name='Bundled Extra Services',
                benefit=special_requests_benefit,
                condition=special_requests_condition)
        try:
            ConditionalOffer.objects.get(name='Pre-Ordered Extra Services')
        except ConditionalOffer.DoesNotExist:
             ConditionalOffer.objects.create(
                name='Pre-Ordered Extra Services',
                benefit=predefined_special_requests_benefit,
                condition=predefined_special_requests_condition)

        #create the infra for shipping method offer
        #create range that includes all shipping method fees
        shipping_method_category = create_category('shipping_method')
        shipping_method_range, _ = Range.objects.get_or_create(
            name="shipping_method")
        shipping_method_range.included_categories.add(
            shipping_method_category)






