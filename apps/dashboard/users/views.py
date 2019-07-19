from oscar.apps.dashboard.users.views import (
    IndexView as CoreIndexView,
    UserDetailView as CoreUserDetailView)
from django.utils.translation import ugettext as _
from oscar.views.generic import ObjectLookupView
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User
from django.views.generic import (
    ListView, DetailView,
    UpdateView, TemplateView)
from django.conf import settings
from .forms import UserProfileUpdateForm
from django.db.models import get_model
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.db.models import Q, Count
from apps.customer.tasks import unsubscribe_user, subscribe_user

CustomerFeedback = get_model('customer', 'CustomerFeedback')
AccountStatus = get_model('user', 'AccountStatus')
Product = get_model('catalogue', 'Product')
Profile = get_model('user', 'Profile')

class IndexView(CoreIndexView):
    desc_template = _('%(main_filter)s %(email_filter)s %(name_filter)s %(uuid_filter)s %(country_filter)s')

    def get_queryset(self):
        queryset = super(IndexView, self).get_queryset()
        self.desc_ctx.update({'uuid_filter': '', 'country_filter': ''})
        if not self.form.is_valid():
            return queryset
        cleaned_data = self.form.cleaned_data
        uuid = cleaned_data.get('uuid')
        country = cleaned_data.get('country')
        if uuid:
            queryset = self.model.objects.all().order_by('-date_joined').filter(profile__uuid=uuid)
            self.desc_ctx['uuid_filter'] = _(" with uuid matching '%s'") % uuid
        elif country:
            queryset = queryset.filter(profile__country=country)
            self.desc_ctx['country_filter'] = _(" with country matching '%s'") % country
        return queryset

    def is_filters_applied(self):
        for key, val in self.desc_ctx.iteritems():
            if key != 'main_filter' and val:
                return True
        return False

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['filters_applied'] = self.is_filters_applied()
        return context

    def _change_users_active_status(self, users, value):
        for user in users:
            if not user.is_superuser:
                if value == False:
                    profile = user.get_profile()
                    in_store_packages = Product.in_store_packages.filter(owner=user)
                    waiting_for_consolidation_packages = Product.packages\
                        .filter(owner=user, status='consolidation_taking_place')
                    if in_store_packages.exists() or waiting_for_consolidation_packages.exists():
                        in_store_packages.update(status='pending')
                        for consolidated_package in waiting_for_consolidation_packages:
                            consolidated_package.combined_products.all().update(status='pending')
                            consolidated_package.delete()
                        #need to make sure user has failed_verification AccountStatus
                        #to make sure he could only return his in store packages back to the senders
                        if profile.has_account_status():
                            profile.account_status.verification_status = AccountStatus.VERIFICATION_FAILED
                            profile.account_status.save()
                        else:
                            AccountStatus.objects.create(
                                profile=profile,
                                verification_status=AccountStatus.VERIFICATION_FAILED)
                    #make user inactive
                    user.is_active = False
                    user.save()

                    #remove user from mailchimp list
                    list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_USERS]
                    unsubscribe_user.apply_async(
                        kwargs={
                            'user': user,
                            'list_id': list_id
                        },
                        queue='analytics'
                    )
                else:
                    profile = user.get_profile()
                    if profile.has_account_status():
                        profile.account_status.verification_status = AccountStatus.VERIFIED
                        profile.account_status.save()
                    user.is_active = True
                    user.save()
                    #add user to mailchimp list
                    list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_USERS]
                    subscribe_user.apply_async(
                        kwargs={
                            'user': user,
                            'list_id': list_id
                        },
                        queue='analytics'
                    )
        messages.info(self.request, _("Users' status successfully changed"))
        return HttpResponseRedirect(reverse(self.current_view))

class UserDetailView(CoreUserDetailView):
    def get_packages_qs(self):
        return self.object.packages.prefetch_related(
            'stockrecords', 'stockrecords__partner').filter(
            product_class__name='package').order_by('-date_created')

    def get_context_data(self, **kwargs):
        ctx = super(UserDetailView, self).get_context_data(**kwargs)
        ctx['package_list'] = self.get_packages_qs()
        return ctx


class UserProfileUpdateView(UpdateView):
    template_name = 'dashboard/users/profile_update.html'
    model = Profile
    form_class = UserProfileUpdateForm
    context_object_name = 'profile'

    def get_success_url(self):
        messages.success(self.request, _("User profile updated"))
        report_referer = self.request.session.get('REPORT_REFERER')
        if report_referer:
            del self.request.session['REPORT_REFERER']
            return report_referer
        return reverse('dashboard:users-index')


class UserLookupView(ObjectLookupView):
    model = User

    def get_query_set(self):
        #exclude staff users
        return self.model.objects.exclude(is_staff=True)

    def lookup_filter(self, qs, term):
        #first try to match by uuid
        try:
            int(term)
            return qs.filter(profile__uuid__startswith=term)
        except ValueError:
            pass
        #try matching by first and last name
        try:
            first_name, last_name = term.split(' ', 1)
            return qs.filter(
                Q(first_name__istartswith=first_name) &
                Q(last_name__istartswith=last_name))
        except ValueError:
            pass
        return qs.filter(first_name__istartswith=term)


    def format_object(self, obj):
        return {
            'id': obj.pk,
            'text': unicode(obj.get_profile().uuid),
            'name': obj.get_full_name()
        }

class UserFeedbackListView(ListView):
    template_name = 'dashboard/users/feedback_list.html'
    paginate_by = 25
    model = CustomerFeedback
    context_object_name = 'feedback_list'

    def get_queryset(self):
        """
        Show latest feedbacks first
        """
        return  self.model.objects.select_related(
            'order', 'customer').all().order_by('-date_created')


class UserFeedbackView(DetailView):
    template_name = 'dashboard/users/feedback_detail.html'
    model = CustomerFeedback
    context_object_name = 'feedback'


class UserGeoBreakdown(TemplateView):
    template_name = 'dashboard/users/geo_breakdown.html'

    def get_context_data(self, **kwargs):
        ctx = super(UserGeoBreakdown, self).get_context_data(**kwargs)
        ctx['breakdown_list'] = User.objects\
            .filter(profile__country__isnull=False,
                    is_active=True,
                    is_staff=False,
                    partners__isnull=True)\
            .values_list('profile__country')\
            .annotate(user_count=Count('id', distinct=True))\
            .annotate(order_count=Count('orders', distinct=True))\
            .order_by('-order_count')
        return ctx

class UserRegistrationTypeBreakdown(TemplateView):
    template_name = 'dashboard/users/registration_type_breakdown.html'

    def get_context_data(self, **kwargs):
        ctx = super(UserRegistrationTypeBreakdown, self).get_context_data(**kwargs)
        ctx['breakdown_list'] = User.objects\
            .filter(is_active=True,
                    is_staff=False,
                    partners__isnull=True)\
            .values_list('profile__registration_type')\
            .annotate(user_count=Count('id', distinct=True))\
            .annotate(order_count=Count('orders', distinct=True))\
            .order_by('-order_count')
        return ctx