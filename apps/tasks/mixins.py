from celery.result import AsyncResult
from django.http import HttpResponse
from django.utils import simplejson as json
from django.utils.translation import ugettext as _
from oscar.core import ajax
import logging

logger = logging.getLogger("management_commands")

class CeleryTaskStatusMixin(object):
    def handle_celery_task_result(self, result):
        """
        This function is unique for every subclass
        """
        raise NotImplementedError

    def handle_celery_task_running(self, task_id=None):
        payload = {'status': 'RUNNING'}
        if task_id:
            payload['task_id'] = task_id
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def handle_celery_task_failure(self):
        logger.error("Celery task failure")
        flash_messages = ajax.FlashMessages()
        flash_messages.error(_("Something went terribly wrong, please try again shortly."))
        payload = {
            'messages': flash_messages.to_json(),
            'status': 'FAILURE'
        }
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def task_status(self, task_id):
        task = AsyncResult(task_id)
        if task and task.state != 'FAILURE':
            if task.state == 'SUCCESS':
                if isinstance(task.result, AsyncResult):
                    return self.handle_celery_task_running(task_id=task.result.id)
                return self.handle_celery_task_result(task.result)
            return self.handle_celery_task_running()
        return self.handle_celery_task_failure()

    def add_flash_messages(self, container, msgs):
        if msgs:
            for key, values in msgs.items():
                for val in values:
                    container.add_message(key, val)