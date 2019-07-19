from django.dispatch import Signal

user_registered = Signal(providing_args=["user", "request", "mixpanel_anon_id", "backend"])
affiliate_registered = Signal(providing_args=["user"])