from drip.drips import DripMessage
from django.template import loader

class BodyTemplateDrip(DripMessage):
    @property
    def body(self):
        if not self._body:
            self._body = loader.get_template(self.drip_base.body_template.strip()).render(self.context)
        return self._body
