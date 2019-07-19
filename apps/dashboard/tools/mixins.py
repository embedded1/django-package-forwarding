from django.views.generic import RedirectView
from django.core.urlresolvers import reverse
from django.contrib import messages
from apps.customer.alerts import senders
import functools

class VerificationStatusUpdateView(RedirectView):
    permanent = False
    model = None
    notify_cb_name = None
    user_field_name = None
    obj = None

    def rgetattr(self, obj, attr):
        return functools.reduce(getattr, [obj]+attr.split('.'))


    def get_redirect_url(self, **kwargs):
        action = self.request.GET.get('action', '')
        next = self.request.session.get('REPORT_REFERER', reverse('dashboard:reports-index'))
        more_documents = is_verified = False

        try:
            self.obj = self.model.objects.get(pk=kwargs['pk'])
        except self.model.DoesNotExist:
            messages.error(self.request, "Failed, object not found")
            return next

        if action == 'accept':
           self.obj.verification_status = self.model.VERIFIED
           is_verified = True
        elif action == 'deny':
            self.obj.verification_status = self.model.VERIFICATION_FAILED
        elif action == 'more_documents':
            self.obj.verification_status = self.model.WAITING_FOR_MORE_DOCUMENTS
            more_documents = True
        else:
            messages.error(self.request, "Unknown action")
            return next

        #save changes and send email to customer with our decision
        self.obj.save()
        notify_cb = getattr(senders, self.notify_cb_name)
        notify_cb(
            user=self.rgetattr(self.obj, self.user_field_name),
            is_verified=is_verified,
            more_documents=more_documents,
            obj=self.obj)

        messages.success(self.request, "Operation succeeded")
        return next
