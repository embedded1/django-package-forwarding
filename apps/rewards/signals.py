from django.dispatch import Signal


affiliate_registered = Signal(providing_args=["user"])