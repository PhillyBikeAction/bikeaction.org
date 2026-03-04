from django import forms
from django.core.exceptions import ValidationError

from pbaabp.forms import validate_is_checked


def validate_coc_email_value(value):
    if value.lower().strip() != "governance@bikeaction.org":
        raise ValidationError("Hmmmm, that's not quite right.")


class OrganizerApplicationForm(forms.Form):
    required_css_class = "required"

    def to_json(self):
        return {field.name: {"label": field.label, "value": field.value()} for field in self}

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("primary_role") == "other" and not cleaned_data.get(
            "primary_role_other"
        ):
            self.add_error(
                "primary_role_other", "You must describe your intended role when selecting Other."
            )
        if cleaned_data.get("current_contribution") == "yes" and not cleaned_data.get(
            "current_contribution_info"
        ):
            self.add_error(
                "current_contribution_info", "You must describe your current contributions."
            )
        if cleaned_data.get("not_gonna_try_to_name_this") == "yes" and not cleaned_data.get(
            "not_gonna_try_to_name_this_info"
        ):
            self.add_error("not_gonna_try_to_name_this_info", "Please explain.")

    # The Basics

    nominator = forms.CharField(
        label="Nominating Organizer/Board Member",
        help_text="Name a current Organizer with whom you have worked that can vouch for you.",
        max_length=256,
        required=True,
    )

    duties_and_expectations = forms.BooleanField(
        label="hidden",
        help_text=(
            'I have read the <a target="_blank" '
            'href="https://docs.google.com/document/d/'
            '1HnMdpw7VxJh4cAhaFb3hU3OLSw21wDxGGx7yJ8PgqFs/edit?usp=sharing">'
            "Organizer Duties & Expectations</a> document."
        ),
        required=True,
        validators=[validate_is_checked],
    )

    # Applicant information

    phone_number = forms.CharField(label="Phone number", max_length=128, required=True)
    preferred_contact_method = forms.ChoiceField(
        label="Preferred contact method",
        choices=[
            ("discord", "Discord"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("text/sms", "Text/SMS"),
        ],
        required=True,
    )

    primary_role = forms.ChoiceField(
        label="Primary Role",
        help_text="Which primary Organizer Role will you fulfill?",
        choices=[
            ("district-organizer", "District Organizer"),
            ("admin", "Admin"),
            ("team-leader", "Team Leader"),
            ("insider-strategy", "Insider/Strategy"),
            ("other", "Other"),
        ],
        required=True,
    )
    primary_role_other = forms.CharField(
        label="Other?",
        help_text="Please explain",
        max_length=512,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Please explain"}),
    )

    regular_duties = forms.CharField(
        label="What regular duties do you want to contribute to PBA?",
        help_text=(
            "Reference the Organizer Duties document for ideas. "
            "You are not expected to do everything, "
            "but you should have something specific in mind that you want to contribute!"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )

    teams = forms.MultipleChoiceField(
        label="Which, if any, Teams would you like to contribute to?",
        help_text=(
            'See <a href="https://apps.bikeaction.org/get-involved/teams">Teams</a>. '
            "You will be assigned this role in Discord and will receive notifications"
        ),
        widget=forms.CheckboxSelectMultiple,
        choices=[
            ("newsletter", "Newsletter"),
            ("citywides", "Citywide-planning"),
            ("outreach", "Outreach"),
            ("tech", "Tech"),
            ("copy-editing", "Copy editing"),
            ("graphic-design", "Graphic design"),
            ("press", "Press"),
            ("street-team", "Street team"),
            ("social-media", "Social media"),
            ("website", "Website"),
            ("comms", "Comms"),
            ("lawyer-team", "Lawyer-team"),
        ],
    )

    involvement = forms.CharField(
        label=(
            "How have you been involved in PBA thus far that demonstrates consistent engagement?"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    past_experience = forms.CharField(
        label=("Please list any past experience that could be relevant to PBA/the Organizer role"),
        help_text=(
            "social media management, legal expertise, administrative work, "
            "community organizing, etc"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    current_contribution = forms.ChoiceField(
        label=("Are you currently contributing to any Active or Pending PBA projects/campaigns?"),
        choices=[(None, "---"), ("yes", "Yes"), ("no", "No")],
    )
    current_contribution_info = forms.CharField(
        label="Which one(s)?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    online_availability = forms.CharField(
        label="Describe your online availability",
        help_text=(
            "hours online per day/week, evenings vs weekends, flexible daytime schedule etc"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    inperson_availability = forms.CharField(
        label="Describe your availability in-person",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )

    public_speaking = forms.CharField(
        label="Describe your comfort with public speaking",
        help_text=(
            "press spokesperson, public comment, presenting at PBA meetings, "
            "meetings with City Council, etc"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    support_needed = forms.CharField(
        label="What do you need from PBA in order to support you as an organizer?",
        help_text=(
            "Is there anything we should know about how you work or your preferences? "
            "(It’s ok to leave this question blank if you can’t think of anything.)"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    anything_else = forms.CharField(
        label="Any other relevant information or details?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    code_of_conduct = forms.BooleanField(
        label="hidden",
        help_text=(
            'I have read and agree to the <a target="_blank" '
            'href="https://apps.bikeaction.org/policies/code-of-conduct/">'
            "Philly Bike Action Code of Conduct</a>."
        ),
        required=True,
        validators=[validate_is_checked],
    )
    coc_what_email = forms.CharField(
        label="What email address should Code of Conduct issues be reported to?",
        max_length=128,
        required=True,
        validators=[validate_coc_email_value],
    )

    not_gonna_try_to_name_this = forms.ChoiceField(
        label=(
            "Have you ever faced discipline or entered into a settlement related to "
            "your actual or alleged sexual or physical harassment of another?"
        ),
        choices=[(None, "---"), ("yes", "Yes"), ("no", "No")],
    )
    not_gonna_try_to_name_this_info = forms.CharField(
        label="Please explain",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
