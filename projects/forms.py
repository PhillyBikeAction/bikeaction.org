from django import forms


class ProjectApplicationForm(forms.Form):
    required_css_class = "required"

    def to_json(self):
        return {field.name: {"label": field.label, "value": field.value()} for field in self}

    shortname = forms.CharField(
        label="Shortname", max_length=256, help_text="A short name for your project", required=True
    )
    quick_summary = forms.CharField(
        label="Quick Summary",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Briefly describe your project. <i>This will be public.</i>",
        required=True,
    )

    # Project leader information

    leader_phone_number = forms.CharField(label="Phone number", max_length=128, required=True)
    leader_preferred_contact_method = forms.ChoiceField(
        label="Preferred contact method",
        choices=[
            ("discord", "Discord"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("text/sms", "Text/SMS"),
        ],
        required=True,
    )
    leader_past_experience = forms.CharField(
        label="Please describe any past experience relevant to this project",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )

    # high level
    mission_relevance = forms.CharField(
        label=(
            "How does this project advance PBA's mission "
            "to improve the bicycle infrastructure of Philadelphia?"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    success_criteria = forms.CharField(
        label="What are the success criteria for this project? How will we know it's done?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    name_use = forms.CharField(
        label="Will this project be branded and marketed under PBA's name?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    recruitment = forms.CharField(
        label=(
            "Have you already recruited anyone in PBA to help you with this project?If so, who?"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    external_orgs = forms.CharField(
        label="Will any external organizations be collaborating on this project?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )

    # logistics
    time_and_date = forms.CharField(
        label="Time and date (if applicable)", max_length=256, required=False
    )
    recurring = forms.BooleanField(
        label="Is this a recurring event?",
        help_text=(
            "Check this box if your event is recurring, "
            "describe recurrence schedule in the Time and date"
        ),
        required=False,
    )
    location = forms.CharField(
        label="Location (if applicable)",
        max_length=256,
        required=False,
    )

    # scope
    potential_broader_campaign = forms.CharField(
        label=(
            "If you expect this project to lead into a broader campaign, "
            "please specify possible next steps:"
        ),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    # resources
    equipment_needed = forms.CharField(
        label="Describe equipment needed (tables, banners, trailers, etc.)",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    volunteers_needed = forms.CharField(
        label="Describe volunteer resources needed",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    promotion_needed = forms.CharField(
        label="Describe promotional needs (Instagram, mailing list, etc.)",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    finances_needed = forms.CharField(
        label="What is the budget for this project?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )
    others_needed = forms.CharField(
        label="Describe other needs",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    # anything else
    anything_else = forms.CharField(
        label="Anything else you want to include in your application?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
