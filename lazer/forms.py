from django import forms


class SubmissionForm(forms.Form):
    latitude = forms.CharField()
    longitude = forms.CharField()
    datetime = forms.DateTimeField()
    image = forms.CharField()


class ReportForm(forms.Form):
    submission_id = forms.UUIDField()

    date_observed = forms.CharField()
    time_observed = forms.CharField()

    make = forms.CharField()
    model = forms.CharField()
    body_style = forms.CharField()
    vehicle_color = forms.CharField()

    violation_observed = forms.CharField()
    occurrence_frequency = forms.CharField()

    block_number = forms.CharField()
    street_name = forms.CharField()
    zip_code = forms.CharField()

    additional_information = forms.CharField()
