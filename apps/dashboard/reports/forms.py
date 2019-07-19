from oscar.apps.dashboard.reports.forms import ReportForm as CoreReportForm
from datetime import timedelta, datetime
from oscar.core.loading import get_class

GeneratorRepository = get_class('dashboard.reports.utils',
                                'GeneratorRepository')

class ReportForm(CoreReportForm):
    def __init__(self, data=None, user=None, **kwargs):
        super(ReportForm, self).__init__(data, **kwargs)
        self.fields['date_from'].required = False
        self.fields['date_to'].required = False
        self.generators = GeneratorRepository(user).get_report_generators()
        type_choices = []
        for generator in self.generators:
            type_choices.append((generator.code, generator.description))
        self.fields['report_type'].choices = type_choices

    def clean(self):
        cleaned_data = super(ReportForm, self).clean()
        now = datetime.now()
        FIVE_YEARS_IN_WEEKS = 52 * 5

        #set date_to value to now if not set before
        if 'date_to' in cleaned_data and not cleaned_data['date_to']:
            cleaned_data['date_to'] = now

        #set date_from value to 5 years back if not set before
        if 'date_from' in cleaned_data and not cleaned_data['date_from']:
                cleaned_data['date_from'] = now - timedelta(weeks=FIVE_YEARS_IN_WEEKS)

        return cleaned_data


