from django import forms


class PackageForwardingAccountForm(forms.Form):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60)
    password = forms.CharField()