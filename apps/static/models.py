from django.db import models
from django.utils.translation import ugettext_lazy as _

class Statistics(models.Model):
    name = models.CharField(
        _("Application name"), max_length=32
    )
    usage_counter = models.BigIntegerField(
        _("Usage counter"),
        default=0
    )

    def __unicode__(self):
        return u"%s stats" % self.name