from oscar.apps.dashboard.reports.reports import ReportGenerator as CoreReportGenerator


class ReportGenerator(CoreReportGenerator):
    def __init__(self, **kwargs):
        """
        Save user instance to support multiplepartners
        """
        super(ReportGenerator, self).__init__(**kwargs)
        if 'user' in kwargs:
            self.user = kwargs['user']

    def report_message(self):
        return getattr(self, 'message', "")

    def report_context_data(self, qs):
        return {}
