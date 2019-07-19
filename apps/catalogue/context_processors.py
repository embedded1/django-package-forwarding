from django.db.models import get_model

Product = get_model('catalogue', 'Product')

def incoming_packages(request):
    ctx = {}
    if request.user and request.user.is_authenticated():
        num_incoming_packages = Product.objects.filter(
            owner=request.user, product_class__name='package', status__startswith='pending').count()
        ctx['num_incoming_packages'] = num_incoming_packages
    return ctx


def packages_waiting_for_consolidation(request):
    ctx = {}
    if request.user and request.user.is_authenticated():
        num_packages_waiting_for_consolidation = Product.objects.filter(
            owner=request.user, product_class__name='package', status__in=[
            'predefined_waiting_for_consolidation', 'waiting_for_consolidation']).count()
        ctx['num_packages_waiting_for_consolidation'] = num_packages_waiting_for_consolidation
    return ctx

def pending_consolidation_requests(request):
    ctx = {}
    if request.user and request.user.is_authenticated():
        pending_consolidation_requests = Product.objects.filter(
            owner=request.user, product_class__name='package',
            status='consolidation_taking_place').count()
        ctx['num_pending_consolidation_requests'] = pending_consolidation_requests
    return ctx

def pending_extra_services_requests(request):
    ctx = {}
    if request.user and request.user.is_authenticated():
        pending_extra_services_requests = Product.objects.filter(
            owner=request.user, product_class__name='package',
            status='handling_special_requests').count()
        ctx['num_pending_extra_services_requests'] = pending_extra_services_requests
    return ctx
