from oscar.apps.dashboard.reports.utils import GeneratorRepository as CoreGeneratorRepository
from oscar.core.loading import get_classes, get_class
import copy


PackagesToConsolidateReportGenerator, PackageSpecialRequestsReportGenerator, \
AdditionalReceiverActionReportGenerator,\
PackageWaitingTimeForShipmentReportGenerator, \
PackagesInWarehouseReportGenerator,\
DiscardedPackagesReportGenerator,\
PackagesBreakdownReportGenerator = get_classes(
    'catalogue.reports', ['PackagesToConsolidateReportGenerator',
    'PackageSpecialRequestsReportGenerator',
    'AdditionalReceiverActionReportGenerator',
    'PackageWaitingTimeForShipmentReportGenerator',
    'PackagesInWarehouseReportGenerator',
    'DiscardedPackagesReportGenerator',
    'PackagesBreakdownReportGenerator'])

PackageReadyForShippingReportGenerator, PrintShippingLabelsReportGenerator,\
PendingFraudCheckOrderReportGenerator, DownloadReturnLabelReportGenerator,\
PartnerPaymentsReportReportGenerator,\
PaymentsReportReportGenerator,\
OrdersBreakdownReportGenerator,\
BitcoinPaymentsReportGenerator = get_classes(
    'order.reports', ['PackageReadyForShippingReportGenerator',
    'PrintShippingLabelsReportGenerator',
    'PendingFraudCheckOrderReportGenerator',
    'DownloadReturnLabelReportGenerator',
    'PartnerPaymentsReportReportGenerator',
    'PaymentsReportReportGenerator',
    'OrdersBreakdownReportGenerator',
    'BitcoinPaymentsReportGenerator'])
OrderReportGenerator = get_class('order.reports', 'OrderReportGenerator')
ProductReportGenerator, UserReportGenerator = get_classes(
    'analytics.reports', ['ProductReportGenerator',
    'UserReportGenerator'])
OpenBasketReportGenerator, SubmittedBasketReportGenerator = get_classes(
    'basket.reports', ['OpenBasketReportGenerator',
    'SubmittedBasketReportGenerator'])
OfferReportGenerator = get_class('offer.reports', 'OfferReportGenerator')
VoucherReportGenerator = get_class('voucher.reports', 'VoucherReportGenerator')
SuspendedUserAccountReportGenerator,\
AccountStatusActionReportGenerator,\
UserROIReportGenerator= get_classes(
    'user.reports',
    ['SuspendedUserAccountReportGenerator',
    'AccountStatusActionReportGenerator',
    'UserROIReportGenerator'])


class GeneratorRepository(CoreGeneratorRepository):
        generators = [
            PackageSpecialRequestsReportGenerator,
            PackagesToConsolidateReportGenerator,
            PackageReadyForShippingReportGenerator,
            PrintShippingLabelsReportGenerator,
            DownloadReturnLabelReportGenerator,
            PartnerPaymentsReportReportGenerator,
            PaymentsReportReportGenerator,
            OrdersBreakdownReportGenerator,
            BitcoinPaymentsReportGenerator,
            PackagesBreakdownReportGenerator,
            PackagesInWarehouseReportGenerator,
            PendingFraudCheckOrderReportGenerator,
            PackageWaitingTimeForShipmentReportGenerator,
            AccountStatusActionReportGenerator,
            UserROIReportGenerator,
            AdditionalReceiverActionReportGenerator,
            DiscardedPackagesReportGenerator,
            SuspendedUserAccountReportGenerator,
            OrderReportGenerator,
            ProductReportGenerator,
            UserReportGenerator,
            OpenBasketReportGenerator,
            SubmittedBasketReportGenerator,
            VoucherReportGenerator,
            OfferReportGenerator
        ]


        def __init__(self, user=None):
            super(GeneratorRepository, self).__init__()
            gen_copy = copy.deepcopy(self.generators)
            self.generators = [
                g for g in gen_copy if user is None or g(formatter='HTML').is_available_to(user)
            ]


