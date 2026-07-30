from decimal import Decimal

from django import forms


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        single_file_clean = super().clean
        return [single_file_clean(file, initial) for file in data]


class CommunityActionFundApplicationForm(forms.Form):
    required_css_class = "required"

    def to_json(self):
        return {
            field.name: {"label": field.label, "value": field.value()}
            for field in self
            if field.name != "supporting_materials"
        }

    primary_contact_name = forms.CharField(label="Primary Contact Name", max_length=256)
    organization = forms.CharField(
        label="Organization (if applicable)", max_length=256, required=False
    )
    email = forms.EmailField(label="Email")
    phone = forms.CharField(label="Phone", max_length=128)
    project_title = forms.CharField(label="Project Title", max_length=256)
    project_description = forms.CharField(
        label="Describe your project",
        help_text="What are you hoping to build, improve, or accomplish? (300 words maximum)",
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    community_impact = forms.CharField(
        label="How will this project improve biking in Philadelphia?",
        help_text="Who will benefit, why is the project needed, and what impact do you hope it will have? (300 words maximum)",
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    project_readiness = forms.CharField(
        label="What is your plan for completing this project?",
        help_text="Include major steps, approximate timeline, and any anticipated permissions or permitting hurdles. (250 words maximum)",
        widget=forms.Textarea(attrs={"rows": 5}),
    )
    amount_requested = forms.DecimalField(
        label="Amount Requested", min_value=Decimal("0.01"), decimal_places=2, max_digits=8
    )
    estimated_total_project_cost = forms.DecimalField(
        label="Estimated Total Project Cost", min_value=0, decimal_places=2, max_digits=8
    )
    funding_preference = forms.ChoiceField(
        label="Which option would you prefer?",
        choices=[
            ("reimbursement", "Reimbursement"),
            ("upfront", "Upfront funding"),
            ("other", "I'd like to discuss another option"),
        ],
        widget=forms.RadioSelect,
    )
    funding_preference_explanation = forms.CharField(
        label="If you selected upfront funding or another option, please briefly explain",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    supporting_materials = MultipleFileField(
        label="Supporting Materials (Optional)",
        help_text="Upload photos, sketches, site plans, letters of support, or a budget worksheet.",
        required=False,
    )
    certification = forms.BooleanField(
        label=(
            "I certify that the information provided is accurate to the best of my knowledge. "
            "I understand this is a competitive funding opportunity and, if selected, I agree "
            "to provide a brief update to Philly Bike Action after completing the project."
        )
    )

    def clean(self):
        cleaned_data = super().clean()
        for field_name, limit in {
            "project_description": 300,
            "community_impact": 300,
            "project_readiness": 250,
        }.items():
            value = cleaned_data.get(field_name, "")
            if len(value.split()) > limit:
                self.add_error(field_name, f"Please limit your response to {limit} words.")
        if cleaned_data.get("funding_preference") in {"upfront", "other"} and not cleaned_data.get(
            "funding_preference_explanation"
        ):
            self.add_error(
                "funding_preference_explanation",
                "Please briefly explain your funding needs.",
            )
        return cleaned_data
