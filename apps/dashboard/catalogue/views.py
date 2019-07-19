from apps.user.alerts import send_new_package_alert
from oscar.apps.dashboard.catalogue.views import (
    ProductCreateUpdateView, ProductListView, ProductDeleteView)
from oscar.apps.catalogue.models import ProductClass
from apps.dashboard.catalogue.forms import (
    CustomsDeclarationForm, CustomsFormItemFormSet, SpecialRequestForm,
    ConsolidationRequestForm, PredefinedParcelsForm,
    DamagedPackageForm, ReturnedPackageForm,
    EnvelopeRestrictionsForm, AdditionalPackageReceiverForm,
    ExtraConsolidationPackagesFormSet, PackageLocationForm)
from django.core.exceptions import ObjectDoesNotExist
from apps.partner.utils import create_package_stock_record, get_partner_name
from django.contrib import messages
from django.utils.translation import ugettext as _
from apps.catalogue.signals import product_status_change_alert
from apps.catalogue.cache import ProductCache
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from oscar.core import ajax
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils import simplejson as json
from apps.catalogue.models import (
    ProductSpecialRequests, CustomsFormItem,
    Product, AdditionalPackageReceiver, PackageLocation)
from apps.catalogue import utils
from apps.customer.alerts import senders
from apps.customer.tasks import mixpanel_track_sent_package
from django.conf import settings
from forkit import tools
from decimal import Decimal as D
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.html import mark_safe
from datetime import datetime
from .utils import find_shopify_store_id
import copy
import string
import logging


logger = logging.getLogger("management_commands")


def filter_products(queryset, user):
    """
    Restrict the queryset to products the given user has access to.
    A staff user is allowed to access all Products.
    A non-staff user is only allowed access to a product if they are in at
    least one stock record's partner user list.
    """
    if user.is_staff:
        return queryset

    return queryset.filter(stockrecords__partner__users__pk=user.pk).distinct()


class CustomProductListView(ProductListView):
    damaged_package_form_class = DamagedPackageForm
    returned_package_form_class = ReturnedPackageForm
    allow_empty = True

    def is_damaged_package_form_submitted(self):
        return 'damaged-owner' in self.request.GET or 'damaged-merchant_name' in self.request.GET

    def is_returned_package_form_submitted(self):
        return 'returned-owner' in self.request.GET or 'returned-package_upc' in self.request.GET

    def send_product_status_change_alert(self, package):
        product_status_change_alert.send(
            sender=Product,
            customer=package.owner,
            package=package,
            extra_msg=None
        )

    def dup_package(self, org_package, condition, battery_status):
        #fork org_package to enter a new package into the system for the returned package
        returned_package = tools.fork(
            org_package,
            fields=('title', 'is_discountable', 'customs_form', 'images'),
            deep=True,
            commit=False)
        returned_package.upc = utils.generate_upc()
        returned_package.condition = condition
        returned_package.battery_status = battery_status
        returned_package.status = 'pending_returned_package'
        returned_package.is_client_id_missing = False
        returned_package.owner = org_package.owner
        returned_package.product_class = org_package.product_class
        #returned_package.combined_products = org_package.combined_products.all()
        #returned_package.product_class = ProductClass.objects.get(name='package')
        setattr(returned_package.attr, 'weight', getattr(org_package.attr, 'weight'))
        setattr(returned_package.attr, 'height', getattr(org_package.attr, 'height'))
        setattr(returned_package.attr, 'width',  getattr(org_package.attr, 'width'))
        setattr(returned_package.attr, 'length', getattr(org_package.attr, 'length'))
        setattr(returned_package.attr, 'is_envelope', getattr(org_package.attr, 'is_envelope'))
        #save returned package to DB
        tools.commit(returned_package)
        #create all customs form items, fork did not create those
        if org_package.has_customs_form():
            items = []
            utils.collect_customs_form_items(org_package.customs_form, returned_package.customs_form, items)
            #create all items in once
            CustomsFormItem.objects.bulk_create(items)
        #set partner
        create_package_stock_record(returned_package, self.request.user)
        #set package location
        PackageLocation.objects.create(
            package=returned_package,
            warehouse=org_package.location.warehouse,
            loc1=org_package.location.loc1,
            loc2=org_package.location.loc2,
            loc3=org_package.location.loc3,
        )
        return returned_package

    def get(self, request, *args, **kwargs):
        super(CustomProductListView, self).get(request, *args, **kwargs)
        #delete REPORT_REFERER
        if 'REPORT_REFERER' in request.session:
            del request.session['REPORT_REFERER']
        damaged_package_form = self.damaged_package_form_class(data=request.GET, prefix='damaged')
        returned_package_form = self.returned_package_form_class(data=request.GET, prefix='returned')
        if self.is_damaged_package_form_submitted():
            if damaged_package_form.is_valid():
                messages.success(request, _("Notification was sent to customer"))
                owner = damaged_package_form.cleaned_data['owner']
                merchant_name = string.capwords(damaged_package_form.cleaned_data['merchant_name'])
                #notify customer that his damaged package returned to store
                senders.send_damaged_package_return_to_store_alert(owner, merchant_name)
                return HttpResponseRedirect(reverse('dashboard:catalogue-product-list'))
        elif self.is_returned_package_form_submitted():
            if returned_package_form.is_valid():
                messages.success(request, _("Returned package was successfully re-added into the system"))
                owner = returned_package_form.cleaned_data['owner']
                upc = returned_package_form.cleaned_data['package_upc']
                condition = returned_package_form.cleaned_data['condition']
                battery_status = returned_package_form.cleaned_data['battery_status']
                reason = returned_package_form.cleaned_data['reason']
                #get original package from db (check that the package belong to partner)
                try:
                    org_package = Product.packages\
                        .by_partner_user(request.user)\
                        .get(upc=upc, owner=owner)
                except Product.DoesNotExist:
                    raise Http404
                #create a duplication for the returned package
                returned_package = self.dup_package(org_package, condition, battery_status)
                #notify customer that we received his returned package
                senders.send_returned_package_alert(owner, returned_package, reason)
                return HttpResponseRedirect(reverse('dashboard:catalogue-product-list'))

        context = self.get_context_data(object_list=self.object_list)
        return self.render_to_response(context)

    def get_owner_name(self, data, key):
        try:
            user_id = data[key]
            user = User.objects.get(id=user_id)
        except (TypeError, KeyError, ValueError, User.DoesNotExist):
            return ''
        return user.get_full_name()


    def get_context_data(self, **kwargs):
        """
        Allow to add only packages
        """
        ctx = super(CustomProductListView, self).get_context_data(**kwargs)
        ctx['product_classes'] = ProductClass.objects.filter(name='package')
        data = self.request.GET if self.is_damaged_package_form_submitted() else None
        ctx['damaged_package_form'] = self.damaged_package_form_class(data=data, prefix='damaged')
        ctx['damaged_package_owner_name'] = self.get_owner_name(data, 'damaged-owner')
        data = self.request.GET if self.is_returned_package_form_submitted() else None
        ctx['returned_package_form'] = self.returned_package_form_class(data=data, prefix='returned')
        ctx['returned_package_owner_name'] = self.get_owner_name(data, 'returned-owner')
        return ctx

    def get_queryset(self):
        """
        Build the queryset for this list
        show only packages that belong to active partner
        who operates the dashboard now
        """
        queryset = Product.packages.all().prefetch_related('stockrecords', 'stockrecords__partner')
        queryset = self.filter_queryset(queryset)
        queryset = self.apply_search(queryset)
        queryset = self.apply_ordering(queryset)
        return queryset


class CustomProductCreateUpdateView(ProductCreateUpdateView, ProductCache):
    predefined_parcels = {
        'PEN': {'length': 12.5, 'width':  0.75, 'height': 9.5},
        'LEN': {'length': 15,   'width':  0.75, 'height': 9.5},
        'XS':  {'length': 10,   'width':  8,    'height': 6},
        'SM':  {'length': 12,   'width':  10,   'height': 8},
        'MD':  {'length': 16,   'width':  12,   'height': 10},
        'LR':  {'length': 20,   'width':  14,   'height': 14}
    }
    #packaging_image_formset = ProductPackagingImageFormSet
    customs_form = CustomsDeclarationForm
    customs_item_formset = CustomsFormItemFormSet
    special_requests_form = SpecialRequestForm
    consolidation_requests_form = ConsolidationRequestForm
    predefined_parcels_form = PredefinedParcelsForm
    envelope_restrictions_form = EnvelopeRestrictionsForm
    additional_package_receiver_form = AdditionalPackageReceiverForm
    extra_consolidation_packages_formset = ExtraConsolidationPackagesFormSet
    package_location_form = PackageLocationForm
    prefix = 'product-details'
    predefined_special_requests = False

    def get(self, request, *args, **kwargs):
        res = super(CustomProductCreateUpdateView, self).get(request, *args, **kwargs)
        #show pending special requests / consolidation requests on update
        self.print_get_messages(self.object, request)
        return res

    def get_queryset(self):
        """
        Filter products that the user doesn't have permission to update
        """
        return filter_products(Product.packages.all(), self.request.user)

    def print_get_messages(self, package, request):
        if package:
            try:
                pending_special_requests_summary = package.special_requests.pending_special_requests_summary()
            except ObjectDoesNotExist:
                pass
            else:
                if pending_special_requests_summary:
                    messages.info(request, self.predefined_special_requests_msg(pending_special_requests_summary))
            if package.is_consolidated:
                try:
                    pending_consolidation_requests = package.consolidation_requests.pending_requests()
                except ObjectDoesNotExist:
                    pass
                else:
                    messages.info(request,
                                  self.consolidation_requests_msg(pending_consolidation_requests),
                                  extra_tags='safe')
                locations = []
                for inner_package in package.combined_products.all():
                    try:
                        location = inner_package.location.printable_location()
                    except ObjectDoesNotExist:
                        pass
                    else:
                        locations.append(location)
                if locations:
                    messages.info(request,
                                  self.consolidation_locations_msg(locations),
                                  extra_tags='safe')

    def waiting_for_consolidation_msg(self):
        return _("Package is waiting for consolidation")

    def predefined_special_requests_msg(self, pending_special_requests_summary):
        return _("Package has pending special requests: %s") % pending_special_requests_summary

    def consolidation_requests_msg(self, pending_requests):
        html = "<strong>Package has pending consolidation requests:</strong>"
        html += "<ul>"
        for req in pending_requests:
            html += "<li>%s</li>" % req
        html += "</ul>"
        return html

    def consolidation_locations_msg(self, locations):
        html = "<strong style='display: block;'>Packages locations:</strong>"
        for i,location in enumerate(locations):
            if i % 4 == 0:
                html += "<ul style='display: inline-block;'>"
            html += "<li>%s</li>" % location
            if i % 4 == 3:
                html += "</ul>"
        return html

    def get_owner(self):
        if not getattr(self, 'creating', True):
            return self.object.owner

        user_id = self.request.POST.get(self.prefix + '-owner')
        if not user_id:
            return None
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

        return user

    def ajax_get_owner(self):
        if not getattr(self, 'creating', True):
            return self.object.owner
        user_id = self.request.POST.get('user_id')
        if not user_id:
            return None
        try:
            owner = User.objects.select_related('profile').get(pk=user_id)
        except User.DoesNotExist:
            return None

        return owner

    def get_owner_name(self, owner):
        """
        Check if the user is inactive or failed the account verification
        process, if so return BLOCKED
        otherwise, return owner's name
        """
        profile = owner.get_profile()
        if not owner.is_active or profile.account_verification_failed():
            return "BLOCKED - RETURN PACKAGE TO SENDER"
        return owner.get_full_name()

    def show_images_tab(self, photos_service_ordered):
        """
        We need to show the images tab in 2 cases:
            1 - user orders the photos extra service
            2 - single package and the partner is PREFERRED that
                takes pictures of each incoming package
        """
        return photos_service_ordered or (
            not self.is_create_new_consolidation_package() and
            get_partner_name(self.request.user) == settings.PREFERRED)


    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')
        if request.is_ajax():
            flash_messages = ajax.FlashMessages()
            ctx = {}
            if action == 'predefined_special_requests':
                owner = self.ajax_get_owner()
                if not owner:
                    flash_messages.error("owner can not be found")
                    return self.json_response(
                        ctx,
                        flash_messages,
                        is_valid=False)

                owner_name = self.get_owner_name(owner)
                owner_profile = owner.get_profile()
                #need to create special request form with the data
                #and add a message with all required special requests
                #if package is waiting for consolidation we need to display a message to admin as well
                #need to generate output for product special requests sections
                is_predefined_waiting_for_consolidation = owner_profile.is_predefined_consolidation()

                special_requests = utils.populate_special_requests(
                    owner_profile,
                    is_predefined_waiting_for_consolidation,
                    is_consolidated=False)

                ctx['special_requests_form'] = self.special_requests_form(
                    data=None,
                    instance=special_requests,
                    is_superuser=self.request.user.is_superuser)
                #add messages
                msgs = self.get_post_messages(is_predefined_waiting_for_consolidation, special_requests)
                for msg in msgs:
                    flash_messages.info(msg)

                return self.json_response(
                    ctx,
                    flash_messages,
                    is_valid=True,
                    owner_name=owner_name,
                    show_images_tab=self.show_images_tab(special_requests.is_photos_required),
                    show_customs_form_tab=special_requests.is_filling_customs_declaration,
                    show_package_dim_and_weight_tab=True,
                    show_package_location_tab=True,
                    #self.is_show_package_dim_and_weight_tab(is_predefined_waiting_for_consolidation),
                    show_special_requests_tab=special_requests.is_show_special_requests_tab()
                )
            elif action == 'predefined_parcels':
                selected_predefined_parcel = request.POST.get('predefined_parcel')
                ctx = None
                try:
                    selected_predefined_parcel_dimensions = self.predefined_parcels[selected_predefined_parcel]
                except KeyError:
                    flash_messages.error("Invalid predefined parcel")
                    return self.json_response(ctx, flash_messages)
                else:
                    return self.json_response(
                        ctx,
                        flash_messages,
                        **selected_predefined_parcel_dimensions)
            elif action == 'additional_receiver_status':
                first_name = request.POST.get('first_name')
                last_name = request.POST.get('last_name')
                owner_pk = request.POST.get('owner_pk')
                #try to match an additional receiver
                try:
                    additional_receiver = AdditionalPackageReceiver.objects.get(
                        first_name__iexact=first_name,
                        last_name__iexact=last_name,
                        package_owner__pk=owner_pk)
                except ObjectDoesNotExist:
                    additional_receiver = None

                if additional_receiver and \
                    additional_receiver.verification_failed():
                    #found receiver who failed the verification process
                    status_html = mark_safe('<p id="additional-receiver-status" '
                                            'style="color: red;">ADDITIONAL RECEIVER VERIFICATION FAILED,'
                                            ' RETURN PACKAGE BACK TO SENDER</p>')
                    return self.json_response(
                        ctx=None,
                        flash_messages=flash_messages,
                        status_html=status_html)
                return self.json_response(
                    ctx=None,
                    flash_messages=flash_messages)
            else:
                ctx = None
                flash_messages.error("General error")
                return self.json_response(ctx, flash_messages)
        if action == 'update_package_status':
            if 'package_status' in request.POST:
                package = get_object_or_404(Product, pk=self.kwargs['pk'])
                package.status = request.POST['package_status']
                package.save()
                if package.status != 'discarded':
                    self.send_product_status_change_alert(package)
                    messages.success(request, "Notification was sent to the customer")
            else:
                messages.error(request, "Something went wrong, please contact the manager")
            next = self.request.session.get('REPORT_REFERER', reverse('dashboard:reports-index'))
            return HttpResponseRedirect(next)
        if action == 'add_custom_fee':
            package = get_object_or_404(Product, pk=self.kwargs['pk'])
            description = request.POST.get('fee_description')
            charge = request.POST.get('fee_charge')
            if description and charge:
                idx = package.variants.filter(status='fixed_fees').count()
                upc = settings.CUSTOM_FEE_TEMPLATE % (package.upc, idx)
                utils.create_fee(
                    upc=upc,
                    title=description.title(),
                    package=package,
                    charge=D(charge),
                    status='fixed_fees')
                messages.success(request, "Custom fee was successfully added")
            else:
                messages.error(request, "Custom fee was not added!!")
            next = self.request.META.get('HTTP_REFERER', reverse('dashboard:catalogue-product-list'))
            return HttpResponseRedirect(next)
        return super(CustomProductCreateUpdateView, self).post(request, *args, **kwargs)

    def get_post_messages(self, is_predefined_waiting_for_consolidation, special_requests):
        msgs = []
        if is_predefined_waiting_for_consolidation:
            msgs.append(self.waiting_for_consolidation_msg())
        summary = special_requests.pending_special_requests_summary()
        if summary:
            msgs.append(self.predefined_special_requests_msg(summary))
        return msgs

    def json_response(self, ctx, flash_messages, **kwargs):
        payload = {
            'messages': flash_messages.to_json(),
        }

        if ctx:
            product_special_requests_html = render_to_string(
                'dashboard/catalogue/partials/product_special_requests_form.html',
                RequestContext(self.request, ctx))
            payload['product_special_requests_html'] = product_special_requests_html

        payload.update(kwargs)

        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def get_context_data(self, **kwargs):
        ctx = super(ProductCreateUpdateView, self).get_context_data(**kwargs)
        if 'image_formset' not in ctx:
            ctx['image_formset'] = self.image_formset(instance=self.object)
        if self.object is None:
            ctx['title'] = _('Create new %s product') % self.product_class.name
        else:
            ctx['title'] = ctx['product'].get_title()
            #show tabs based on object's special requests model
            try:
                special_requests = self.object.special_requests
            except ProductSpecialRequests.DoesNotExist:
                pass
            else:
                ctx['show_images_tab'] = self.show_images_tab(special_requests.is_photos_required)
                ctx['show_customs_form_tab'] = special_requests.is_filling_customs_declaration
                ctx['show_special_requests_tab'] = special_requests.is_show_special_requests_tab()
        #if 'packaging_image_formset' not in ctx or not ctx['packaging_image_formset']:
        #    ctx['packaging_image_formset'] = self.packaging_image_formset(instance=self.object)
        if 'customs_form' not in ctx or not ctx['customs_form']:
            ctx['customs_form'] = self.initiate_model_form('customs_form', 'customs_form')
        if 'customs_item_formset' not in ctx or not ctx['customs_item_formset']:
            ctx['customs_item_formset'] = self.customs_item_formset(instance=self.get_model_attr('customs_form'))
        if 'special_requests_form' not in ctx or not ctx['special_requests_form']:
            ctx['special_requests_form'] = self.initiate_model_form(
                'special_requests',
                'special_requests_form',
                is_superuser=self.request.user.is_superuser)
        if 'consolidation_requests_form' not in ctx or not ctx['consolidation_requests_form']:
            ctx['consolidation_requests_form'] = self.initiate_model_form(
                'consolidation_requests',
                'consolidation_requests_form')
        if 'predefined_parcels_form' not in ctx:
            ctx['predefined_parcels_form'] = self.initiate_form('predefined_parcels_form')
        if 'envelope_restrictions_form' not in ctx:
            ctx['envelope_restrictions_form'] = self.initiate_form('envelope_restrictions_form')
        if 'package_location_form' not in ctx:
            ctx['package_location_form'] = self.initiate_model_form(
                'location',
                'package_location_form')
        owner = self.get_owner()
        if owner:
            ctx['owner_name'] = self.get_owner_name(owner)
            #profile = owner.get_profile()
            ctx['show_package_dim_and_weight_tab'] = True
            ctx['show_package_location_tab'] = True
            #self.is_show_package_dim_and_weight_tab(profile.is_predefined_consolidation())
        if 'extra_consolidation_packages_formset' not in ctx:
            if self.object and self.object.is_consolidated:
                packages = self.object.combined_products.all()
            else:
                packages = []
            ctx['extra_consolidation_packages_formset'] = self.extra_consolidation_packages_formset(
                    packages=packages, data=self.request.POST or None)

        #show additional receiver form only on package intake
        if not self.object:
            if 'additional_package_receiver_form' not in ctx:
                ctx['additional_package_receiver_form'] = self.initiate_model_form(
                    'additional_receiver',
                    'additional_package_receiver_form')
        #ctx['is_take_measures'] = self.is_take_measures()
        return ctx

    #def is_show_package_dim_and_weight_tab(self, predefined_consolidation):
    #    return not predefined_consolidation or\
    #           self.is_take_measures() or\
    #           (getattr(self, 'object', False) and not self.object.is_waiting_for_consolidation)

    def get_model_attr(self, attr_name):
        try:
            obj = getattr(self.object, attr_name, None)
        except (AttributeError, ObjectDoesNotExist):
            # either self.object is None, or no customs_form
            obj = None
        return obj

    def initiate_model_form(self, attr_name, form_name, **kwargs):
        """
        Get the the ``CustomsDeclarationForm`` prepopulated with POST
        data if available. If the product in this view has a
        stock record it will be passed into the form as
        ``instance``.
        """
        instance = self.get_model_attr(attr_name)
        return getattr(self, form_name)(
            data=self.request.POST if self.is_form_submitted(form_name) else None,
            instance=instance,
            **kwargs)

    def initiate_form(self, form_name, **kwargs):
        """
        Get the the ``CustomsDeclarationForm`` prepopulated with POST
        data if available.
        """
        return getattr(self, form_name)(
            data=self.request.POST if self.is_form_submitted(form_name) else None,
            **kwargs)

    def is_form_submitted(self, form_name):
        """
        Check if there's POST data that matches CustomsDeclarationForm field names
        """
        form_obj = getattr(self, form_name, None)
        if not form_obj:
            return False

        fields = dict(form_obj.base_fields.items())
        try:
             fields.update(form_obj.declared_fields.items())
        except AttributeError:
            pass
        for name, field in fields.iteritems():
            if len(self.request.POST.get(name, '')) > 0:
                return True
        return False

    def is_product_image_uploaded(self, special_reqs):
        """
        Warehouse takes 1 free package of package exterior
        """
        currently_uploaded_images = filter(lambda x: 'images-' in x, self.request.FILES.keys())
        #num_uploaded_images = self.request.POST.get('images-INITIAL_FORMS', 0)
        num_of_required_images = special_reqs.get_number_of_photos()
        if num_of_required_images == 0: return False
        # we take photo of the package on take in step
        return len(currently_uploaded_images) > num_of_required_images if self.creating else\
               len(currently_uploaded_images) >= num_of_required_images

    def get_form(self, form_class):
        """
        Display only required fields when creating new package
        special treatment for consolidated where we need to delete
        the place holder package dimension attribute values
        """
        if self.is_create_new_consolidation_package(): #or self.is_take_measures():
            #delete attributes placeholder values
            self.object.attribute_values.filter(
                attribute__code__in=['weight', 'height', 'length', 'width', 'is_envelope']).delete()
        form = super(CustomProductCreateUpdateView, self).get_form(form_class)
        return form

    def get_form_kwargs(self):
        kwargs = super(CustomProductCreateUpdateView, self).get_form_kwargs()
        kwargs['prefix'] = self.prefix
        kwargs['is_staff'] = self.request.user.is_staff
        return kwargs

    def is_package_contain_prohibited_items(self):
        return self.request.POST.get('product-details-is_contain_prohibited_items', 'False') == 'True'

    def get_pending_special_requests_left(self):
        """
        Make sure that there is no pending special request left
        if such exists return False, otherwise return True
        """
        special_requests_form = self.initiate_model_form('dummy_field', 'special_requests_form')
        #don't bother to return pending special requests left if form did not validate
        if not special_requests_form.is_valid():
            return None
        #create special requests object based on the submitted data
        #we're not going to save it to db, we're using it only for getting
        #a list of pending special requests left
        special_requests = special_requests_form.save(commit=False)
        #mark special requests completed
        #these special requests are taken care automatically
        self.mark_photos_done(special_requests)
        self.mark_customs_form_done(special_requests)
        self.mark_express_checkout_done(special_requests)
        return special_requests.pending_special_requests_summary()

    def process_all_forms(self, form):
        """
        Short-circuits the regular logic to have one place to have our
        logic to check all forms
        """
        self.creating = self.object is None or self.is_create_new_consolidation_package()

        if self.object and self.object.is_consolidated:
            all_combined_packages = list(self.object.combined_products.all())
        else:
            all_combined_packages = []

        extra_consolidation_packages_formset = self.extra_consolidation_packages_formset(
            data=self.request.POST,
            packages=all_combined_packages,
            current_combined_packages_id=self.request.POST.getlist('product-details-combined_products', []))

        # need to create the product here because the inline forms need it
        # can't use commit=False because ProductForm does not support it
        if self.object is None and form.is_valid():
            self.object = form.save()

        #save a copy of current special requests for spotting new completed special requests
        try:
            self.old_special_requests = copy.deepcopy(self.object.special_requests)
        except (AttributeError, ProductSpecialRequests.DoesNotExist):
            self.old_special_requests = None

        image_formset = self.image_formset(self.request.POST,
                                           self.request.FILES,
                                           instance=self.object)

        #packaging_image_formset = self.packaging_image_formset(self.request.POST,
        #                                                       self.request.FILES,
        #                                                       instance=self.object)
        customs_form = self.initiate_model_form('customs_form', 'customs_form')
        if customs_form.is_valid():
            customs_form_obj = customs_form.save(commit=False)
        else:
            customs_form_obj = None

        customs_item_formset = self.customs_item_formset(self.request.POST, instance=customs_form_obj)
        special_requests_form = self.initiate_model_form(
            'special_requests',
            'special_requests_form',
            is_superuser=self.request.user.is_superuser)
        consolidation_requests_form = self.initiate_model_form(
            'consolidation_requests',
            'consolidation_requests_form')

        additional_package_receiver_form = self.initiate_model_form(
            'additional_receiver',
            'additional_package_receiver_form')

        package_location_form = self.initiate_model_form(
            'location',
            'package_location_form')

        all_forms = [
            form.is_valid(),
            image_formset.is_valid(),
            #packaging_image_formset.is_valid(),
            customs_item_formset.is_valid(),
            extra_consolidation_packages_formset.is_valid(),
            package_location_form.is_valid(),
            not self.is_form_submitted('customs_form') or customs_form.is_valid(),
            not self.is_form_submitted('special_requests_form') or
            (special_requests_form.is_valid() and
            (self.is_package_contain_prohibited_items() or not self.get_pending_special_requests_left())),
            not self.is_form_submitted('consolidation_requests_form') or consolidation_requests_form.is_valid(),
            not self.is_form_submitted('additional_package_receiver_form') or additional_package_receiver_form.is_valid(),
        ]

        is_valid = all(all_forms)
        if is_valid:
            return self.forms_valid(form, None, None,
                                    image_formset, None, customs_item_formset,
                                    customs_form, special_requests_form,
                                    consolidation_requests_form,
                                    additional_package_receiver_form,
                                    extra_consolidation_packages_formset,
                                    package_location_form)#, packaging_image_formset)
        else:
            ctx = {}
            #show pending predefined special requests and if package is waiting for consolidation
            if self.creating:
                try:
                    #try to fetch owner from object (in case product form was valid)
                    owner = self.object.owner
                except (ObjectDoesNotExist, AttributeError):
                    #try to fetch owner from submitted data
                    owner = self.get_owner()
                finally:
                    if owner:
                        profile = owner.get_profile()
                        is_predefined_waiting_for_consolidation = profile.is_predefined_consolidation()
                        special_requests = utils.populate_special_requests(
                            profile,
                            self.creating and is_predefined_waiting_for_consolidation,
                            self.is_create_new_consolidation_package()
                        )
                        special_requests_form = self.special_requests_form(
                            data=self.request.POST,
                            instance=special_requests,
                            is_superuser=self.request.user.is_superuser
                        )
                        #collect uncompleted services only if form is valid
                        if special_requests_form.is_valid():
                            special_requests = special_requests_form.save(commit=False)
                            msgs = self.get_post_messages(is_predefined_waiting_for_consolidation, special_requests)
                            for msg in msgs:
                                messages.info(self.request, msg)
                        ctx.update({
                            'show_images_tab': self.show_images_tab(special_requests.is_photos_required),
                            'show_customs_form_tab': special_requests.is_filling_customs_declaration,
                            'show_package_dim_and_weight_tab': True,
                            'show_package_location_tab': True,
                            #self.is_show_package_dim_and_weight_tab(is_predefined_waiting_for_consolidation),
                            'show_special_requests_tab': special_requests.is_show_special_requests_tab()
                        })
            #show pending special requests and pending consolidation requests
            else:
                self.print_get_messages(self.object, self.request)
            #show pending special requests left
            pending_special_requests_left = self.get_pending_special_requests_left()
            if pending_special_requests_left:
                messages.error(self.request, _("You did not complete all special requests "
                                                "Please complete the following: %s" % pending_special_requests_left))
            #
            # delete the temporary product again
            if self.creating and form.is_valid():
                #don't delete consolidated packages since we've already created it
                if not self.object.is_consolidated:
                    self.object.delete()
                    self.object = None
            return self.forms_invalid(form, None, None,
                                      image_formset, None, customs_item_formset,
                                      customs_form, special_requests_form,
                                      consolidation_requests_form,
                                      additional_package_receiver_form,
                                      extra_consolidation_packages_formset,
                                      package_location_form,
                                      ctx)

    def mark_photos_done(self, special_requests):
        if special_requests.is_photos_required and self.is_product_image_uploaded(special_requests):
            special_requests.photos_done = True

    def mark_customs_form_done(self, special_requests):
        if special_requests.is_filling_customs_declaration and self.is_form_submitted('customs_form'):
            special_requests.filling_customs_declaration_done = True

    def mark_express_checkout_done(self, special_requests):
        if special_requests.is_express_checkout:
            special_requests.express_checkout_done = True
        else:
            #we need to explicitly set this value because we use this value to sort the object by it
            #otherwise the value is undefined and the sort behaves abnormal
            special_requests.express_checkout_done = False

    def mark_exclusive_club_services_done(self, special_requests, services_with_offers):
        charges = {}
        for service in services_with_offers:
            #currently only express checkout is included
            if service == 'express_checkout':
                special_requests.is_express_checkout = True
                special_requests.express_checkout_done = True
                charges['express_checkout'] = D('0.00')
        return charges

    def is_predefined_special_requests_completed(self, new, old):
        #new package + special_requests_from submitted = predefined special requests needed
        ret = self.creating and self.is_at_least_one_special_requests_currently_completed(new, old)
        if ret:
            self.predefined_special_requests = True
        return ret

    def is_at_least_one_special_requests_currently_completed(self, new_sr, old_sr):
        completed_new_sr = new_sr.completed_special_requests()
        completed_old_sr = old_sr.completed_special_requests() if old_sr is not None else []
        completed_delta = set(completed_new_sr) - set(completed_old_sr)
        return len(completed_delta) > 0

    def is_non_predefined_special_requests_completed(self, new, old):
        status = getattr(self.object, 'status', '')
        ret = (status == 'handling_special_requests') and\
              (self.is_at_least_one_special_requests_currently_completed(new, old))
        return ret

    def forms_valid(self, form, stockrecord_form, category_formset,
                    image_formset, recommended_formset, customs_item_formset=None,
                    customs_form=None, special_requests_form=None,
                    consolidation_requests_form=None, additional_package_receiver_form=None,
                    extra_consolidation_packages_formset=None,
                    package_location_form=None):
        #save data
        if self.is_form_submitted('customs_form'):
            customs_form_obj = customs_form.save(commit=False)
            customs_form_obj.package = self.object
            customs_form_obj.save()

        new_special_requests = None
        owner = self.object.owner
        owner_profile = owner.get_profile()
         #exclusive club handling
        offered_services = owner_profile.get_exclusive_club_services_offer()

        if self.is_form_submitted('special_requests_form') or offered_services:
            if special_requests_form is None:
                special_requests_form = SpecialRequestForm()

            new_special_requests = special_requests_form.save(commit=False)
            new_special_requests.package = self.object

            #mark special requests completed
            #these special requests are taken care automatically
            self.mark_photos_done(new_special_requests)
            self.mark_customs_form_done(new_special_requests)
            self.mark_express_checkout_done(new_special_requests)

            exclusive_club_services = False
            charges = None
            if offered_services:
                exclusive_club_services = True
                charges = self.mark_exclusive_club_services_done(new_special_requests, offered_services)

            #check if package is waiting for special requests handling
            #before changing special requests attributes
            if self.is_non_predefined_special_requests_completed(new_special_requests, self.old_special_requests) or\
               self.is_predefined_special_requests_completed(new_special_requests, self.old_special_requests) or\
               exclusive_club_services:
                #create fees for completed special requests
                utils.create_special_requests_fees(new_special_requests,
                                                   self.old_special_requests,
                                                   self.object,
                                                   is_predefined=self.predefined_special_requests,
                                                   charges=charges)

            #save all changes to db
            new_special_requests.save()

        if self.is_form_submitted('consolidation_requests_form'):
            consolidation_requests = consolidation_requests_form.save(commit=False)
            consolidation_requests.package = self.object
            consolidation_requests.save()

        additional_package_receiver = None
        if self.is_form_submitted('additional_package_receiver_form'):
            owner = self.get_owner()
            additional_package_receiver = additional_package_receiver_form.save(package_owner=owner)
            self.object.additional_receiver = additional_package_receiver

        if self.is_form_submitted('package_location_form'):
            package_location = package_location_form.save(commit=False)
            package_location.package = self.object
            package_location.save()

        self.object = form.save()
        #we need to link newly created packages to partner
        #we do this by linking a stock record that holds the partner who's handling this package
        #this also applies to consolidated packages
        partner = create_package_stock_record(self.object, self.request.user)

        # Save formsets
        image_formset.save()
        customs_item_formset.save()
        extra_consolidation_packages_formset\
            .process_extra_consolidation_boxes(self.object)
        #packaging_image_formset.save()

        #for newly created packages check if heavy package fee or missing client id fee should applied
        if self.creating:
            #add over weight fee for package that weights more than 50 pounds
            max_package_weight = D(getattr(settings, 'MAX_PACKAGE_WEIGHT', '50.0'))
            if self.object.weight > max_package_weight:
                charge = D(getattr(settings, 'HEAVY_PACKAGE_FEE', '5'))
                upc = settings.OVER_WEIGHT_TEMPLATE % self.object.upc
                utils.create_fee(
                    upc,
                    _('Heavy Package Surcharge'),
                    self.object,
                    charge,
                    'fixed_fees')

            #add missing client id fee
            if self.object.is_client_id_missing:
                #only add fee if this is not the first time that the customer has dropped his
                #mailbox number out of the shipping address
                owner = self.get_owner()
                missing_client_id_count = Product.objects.filter(owner=owner,
                                                                 product_class__name='package',
                                                                 is_client_id_missing=True).count()
                if missing_client_id_count > 1:
                    charge = D(getattr(settings, 'MISSING_CLIENT_ID_FEE', '5.0'))
                    upc = settings.MISSING_CLIENT_ID_TEMPLATE % self.object.upc
                    utils.create_fee(
                        upc,
                        _('Missing Mailbox Number Surcharge'),
                        self.object,
                        charge,
                        'fixed_fees')

                #update status to pre_pending to delay package update in control panel
                self.object.status = 'pre_pending'

            # logic for newly received packages - not consolidated
            if not self.is_create_new_consolidation_package():
                #Check if package was coming from shopify store
                try:
                    shopify_store_id = find_shopify_store_id(self.object.title)
                except Exception:
                    pass
                else:
                    self.object.shopify_store_id = shopify_store_id

                #track Sent Package event
                mixpanel_track_sent_package.apply_async(
                    kwargs={
                        'package': self.object,
                        'extra_services': new_special_requests,
                        'partner_name': partner.name,
                        'additional_receiver': additional_package_receiver
                    },
                    queue='analytics')

        #update consolidation time as now
        if self.is_create_new_consolidation_package():
            self.object.date_consolidated = datetime.now()

        if self.is_package_contain_prohibited_items():
            extra_msg = form.cleaned_data.get('prohibited_items_msg')
        else:
            extra_msg = None
        #send notifications to user
        self.send_customer_notification(extra_msg)

        #special handling consolidated packages
        #where we need to update title and date_created to support cases where
        #multiple consolidated boxes needed
        #when the main consolidated box only contains 1 package - we cancel the consolidation
        #and change the status of the inner package to pending once again
        children = list(self.object.combined_products.all())
        if len(children) == 1:
            child = children[0]
            child.status='pending'
            child.save()
            self.object.delete()
            messages.success(self.request, "Operation succeed")
            return HttpResponseRedirect(
                reverse('dashboard:catalogue-product-list'))
        elif len(children) > 1:
            self.object.title = self.object.create_consolidated_package_title(children)
            self.object.date_created = self.object.calculate_date_created(children)

        if self.creating and self.object is not None:
            #send mail to admins on every new package
            send_new_package_alert(self.object)

        #before returning, flush changes to db
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, form, stockrecord_form, category_formset,
                      image_formset, recommended_formset, customs_item_formset=None,
                      customs_form=None, special_requests_form=None,
                      consolidation_requests_form=None,
                      additional_package_receiver_form=None,
                      extra_consolidation_packages_formset=None,
                      package_location_form=None, ctx=None):

        messages.error(self.request,
                       _("Your submitted data was not valid - please "
                         "correct the below errors"))

        new_ctx = self.get_context_data(
            form=form,
            image_formset=image_formset,
            customs_item_formset=customs_item_formset,
            customs_form=customs_form,
            special_requests_form=special_requests_form,
            consolidation_requests_form=consolidation_requests_form,
            additional_package_receiver_form=additional_package_receiver_form,
            extra_consolidation_packages_formset=extra_consolidation_packages_formset,
            package_location_form=package_location_form
        )
        if ctx:
            new_ctx.update(ctx)
        return self.render_to_response(new_ctx)

    def get_success_url(self):
        """
        Patch to redirect back to report page instead of redirect to dashboard catalogue
        This is only  used when the referrer is dashboard/reports and user clicked on save
        """
        if self.request.POST.get('action') != 'continue':
            report_referer = self.request.session.get('REPORT_REFERER')
            if report_referer:
                del self.request.session['REPORT_REFERER']
                messages.success(self.request, "Operation succeed")
                return report_referer
        return super(CustomProductCreateUpdateView, self).get_success_url()

    def is_create_new_consolidation_package(self):
        return self.request.GET.get('createconsolidationpackage', False)

    #def is_take_measures(self):
    #    return self.request.GET.get('takemeasures', False)


    def send_product_status_change_alert(self, package, extra_msg=None):
        product_status_change_alert.send(
            sender=Product,
            customer=package.owner,
            package=package,
            extra_msg=extra_msg
        )

    def send_customer_notification(self, extra_msg=None):
        #check if package contains prohibited items
        if self.creating and self.object.is_contain_prohibited_items:
            #change status to trigger the notification email
            self.object.status = 'contains_prohibited_items'
            self.send_product_status_change_alert(self.object, extra_msg)
            #change back to pending to let the customer return it back to the sender
            self.object.status = 'pending'
        elif self.creating and self.object.status == 'pre_pending':
            self.send_product_status_change_alert(self.object)
        #set initial package state to pending
        elif self.creating and not self.is_create_new_consolidation_package():
            if not self.object.status:
                #check if this package is waiting for consolidation based on user request
                if self.object.owner.get_profile().is_predefined_consolidation():
                    self.object.status = 'predefined_waiting_for_consolidation'
                else:
                    self.object.status = 'pending'
            #send alert on arrival of new package
            self.send_product_status_change_alert(self.object)
        #send consolidation done notification to customer
        elif self.object.status == 'consolidation_taking_place':
            #sent alert on consolidation ready package
            self.object.status = 'consolidation_done'
            self.send_product_status_change_alert(self.object)
            #change status to pending so the package will be shown under customer's account
            self.object.status = 'pending'
        #send take measure done notification to customer
        #elif self.object.status == 'take_measures':
        #    self.object.status = 'take_measures_done'
        #    self.send_product_status_change_alert(self.object)
        #    #change status to pending so the package will be shown under customer's account
        #    self.object.status = 'pending_return_to_store'
        #    self.object.save()
        #send completed special requests notification to customer
        #if we got here it means that there are no special requests
        #or all special requests completed
        #therefore checking if we were dealing with special requests is enough
        elif self.object.status == 'handling_special_requests':
            #notify user that photos is ready under his account
            self.object.status = 'handling_special_requests_done'
            #send photos alert to customer
            self.send_product_status_change_alert(self.object)
            #change status back to old status stored in cache
            # no notification will be sent
            key = "%s_status" % self.object.upc
            old_status = self.get_product_status(key=key)
            self.delete_product_status(key=key)
            self.object.status = old_status if old_status else 'pending'


class CustomProductDeleteView(ProductDeleteView):
    def get_queryset(self):
        """
        Filter products that the user doesn't have permission to update
        """
        return filter_products(Product.packages.all(), self.request.user)