from django.views.generic import DetailView
from oscar.core.loading import get_model
from apps.customer.mixins import AjaxTemplateMixin
from django.http import Http404

Product = get_model('catalogue', 'product')


class ProductDetailView(AjaxTemplateMixin, DetailView):
    context_object_name = 'product'
    model = Product
    ajax_template_name = "catalogue/partials/product_details_inner.html"

    def get(self, request, **kwargs):
        if request.is_ajax():
            self.object = self.get_object()
            context = self.get_context_data(object=self.object)
            return self.render_to_response(context)
        raise Http404

    def get_object(self, queryset=None):
        # Check if self.object is already set to prevent unnecessary DB calls
        if hasattr(self, 'object'):
            return self.object
        else:
            return super(ProductDetailView, self).get_object(queryset)

    def get_queryset(self):
        """
        Limit only to user's packages
        """
        return self.model._default_manager.filter(
            owner=self.request.user, product_class__name='package')
