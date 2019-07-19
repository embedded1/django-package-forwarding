from oscar.apps.dashboard.users.forms import UserSearchForm as CoreUserSearchForm
from django import forms
from apps.user.models import Profile
from django.utils.translation import ugettext_lazy as _


class UserSearchForm(CoreUserSearchForm):
    uuid = forms.CharField(required=False, label=_("UUID"))
    country = forms.CharField(required=False, label=_("Country"))

class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('country', 'city', 'proxy_score', 'ip')