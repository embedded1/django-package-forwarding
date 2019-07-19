from django.contrib import admin
from django.http import HttpResponse
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q
from django.contrib.auth.models import User
from .models import (
    Profile, AccountStatus,
    AccountAuthenticationDocument,
    GoogleAnalyticsData,
    PotentialUser)

# Define an inline admin descriptor for Employee model
# which acts a bit like a singleton
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'

# Define a new User admin
class UserAdmin(UserAdmin):
    inlines = (ProfileInline, )
    actions = ['export_csv']

    def export_csv(self, request, queryset):
        import csv
        from django.utils.encoding import smart_str
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=users.csv'
        writer = csv.writer(response, csv.excel)
        response.write(u'\ufeff'.encode('utf8')) # BOM (optional...Excel needs it to open UTF-8 file properly)
        writer.writerow([
            smart_str(u"Email Address"),
            smart_str(u"First Name"),
            smart_str(u"Last Name"),
        ])
        #filter out some users
        queryset = queryset.exclude(
            Q(partners__isnull=False) |
            Q(is_active=False) |
            Q(email='yanivkoter@gmail.com'))
        for obj in queryset:
            #check email confirmed
            profile = obj.get_profile()
            if profile.email_confirmed:
                writer.writerow([
                    smart_str(obj.email),
                    smart_str(obj.first_name),
                    smart_str(obj.last_name),
                ])
        return response
    export_csv.short_description = u"Export CSV"

class AccountStatusAdmin(admin.ModelAdmin):
    pass

class AccountAuthenticationDocumentAdmin(admin.ModelAdmin):
    pass

class PotentialUserAdmin(admin.ModelAdmin):
    pass

class GoogleAnalyticsDataAdmin(admin.ModelAdmin):
    pass

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(AccountStatus, AccountStatusAdmin)
admin.site.register(AccountAuthenticationDocument, AccountAuthenticationDocumentAdmin)
admin.site.register(PotentialUser, PotentialUserAdmin)
admin.site.register(GoogleAnalyticsData, GoogleAnalyticsDataAdmin)