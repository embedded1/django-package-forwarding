from __future__ import absolute_import

import os

from celery import Celery

from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'packageshop.settings')

app = Celery('packageshop')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('celeryconfig')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

if __name__ == '__main__':
    app.start()

