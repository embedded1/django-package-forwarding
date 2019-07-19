import django.dispatch

order_confirmed = django.dispatch.Signal(providing_args=["order"])