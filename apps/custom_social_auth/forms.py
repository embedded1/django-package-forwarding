from django import forms
from apps.user.models import Profile


class SocialUserProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        exclude = ('user', 'uuid')

