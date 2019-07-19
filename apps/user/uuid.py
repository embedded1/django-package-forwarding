from apps.user.models import Profile
from django.db.models import Max


def generate_uuid():
    """
    We would like to keep private suite numbers starting from 10000 and
    increment it by 1 for every new customer
    This function is called after user has been saved to db therefore we calculate
    the current max uuid and increment it by 1 for the new user
    """
    try:
        p = Profile.objects.aggregate(Max('uuid'))
        max_uuid = p['uuid__max']
        new_uuid = int(max_uuid) + 1
        return str(new_uuid)
    #starting point for the first created profile
    except (Profile.DoesNotExist, TypeError):
        return '10000'