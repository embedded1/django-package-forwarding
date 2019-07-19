from django.contrib.sites.models import get_current_site
from apps.utils import operation_shut_down, operation_suspended

def site(request):
    site = get_current_site(request)
    protocol = 'https' if request.is_secure() else 'http'
    return {
        'site': "%s://%s" % (protocol, site.domain),
        'site_name': site.name
    }

def clicky_global_properties(request):
    return {
        'clicky_visitor': {
            'email': request.user.email if request.user.is_authenticated() else 'Not Registered'
        }
    }

def crazyegg_global_properties(request):
    return {
        'crazy_egg_var1':
            request.user.email if request.user.is_authenticated() else 'Not Registered'
    }

def operation_status(request):
    return {
        'operation_suspended': operation_suspended(request.user),
        'operation_shut_down': operation_shut_down(request.user)
    }