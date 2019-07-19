import django.dispatch

product_status_change_alert = django.dispatch.Signal(providing_args=["customer", "package", "extra_msg"])

