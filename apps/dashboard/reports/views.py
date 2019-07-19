from oscar.apps.dashboard.reports.views import IndexView as CoreIndexView
from django.http import HttpResponseForbidden
from django.template.response import TemplateResponse
from django.contrib import messages
from django.utils.translation import ugettext as _
from django.http import Http404

class IndexView(CoreIndexView):
    def _get_generator(self, form):
        """
        We overwrite Oscar's function to pass user to the report to
        support multiple partners
        """
        code = form.cleaned_data['report_type']

        repo = self.generator_repository(user=self.request.user)
        generator_cls = repo.get_generator(code)
        if not generator_cls:
            raise Http404()

        download = form.cleaned_data['download']
        formatter = 'CSV' if download else 'HTML'

        return generator_cls(start_date=form.cleaned_data['date_from'],
                             end_date=form.cleaned_data['date_to'],
                             formatter=formatter,
                             user=self.request.user)

    def sort_queryset(self, request):
        """ Sorts the queryset by one of allowed_sorts based on parameters
        'sort' and 'dir' from request """
        sort = request.GET.get('sort', None)
        if sort:
            direction = request.GET.get('dir', 'asc')
            sort = ('-' if direction == 'desc' else '') + sort
            self.queryset = self.queryset.order_by(sort)

    def get(self, request, *args, **kwargs):
        """
        Set referer to report and not to dashboard catalogue page
        load only relevant reports based on user permissions
        """
        if 'report_type' in request.GET:
            form = self.report_form_class(request.GET, request.user)
            if form.is_valid():
                generator = self._get_generator(form)
                if not generator.is_available_to(request.user):
                    return HttpResponseForbidden(_("You do not have access to"
                                                   " this report"))

                request.session['REPORT_REFERER'] = request.get_full_path()
                report = generator.generate()

                if form.cleaned_data['download']:
                    return report
                else:
                    self.set_list_view_attrs(generator, report)
                    self.sort_queryset(request)
                    context = self.get_context_data(object_list=self.queryset)
                    context['form'] = form
                    context['description'] = generator.report_description()
                    context.update(generator.report_context_data(self.queryset))
                    messages.success(request, generator.report_message(), extra_tags='safe')
                    return self.render_to_response(context)
        else:
            form = self.report_form_class(user=request.user)
        return TemplateResponse(request, self.template_name, {'form': form})
