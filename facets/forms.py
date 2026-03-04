from django import forms

COLUMN_CHOICES = [
    ("first_name", "First Name"),
    ("last_name", "Last Name"),
    ("email", "Email"),
    ("pronouns", "Pronouns"),
    ("street_address", "Street Address"),
    ("zip_code", "Zip Code"),
    ("newsletter_opt_in", "Newsletter Opt-In"),
    ("created_at", "Created At"),
    ("district", "District"),
    ("membership", "Membership"),
    ("donor", "Donor"),
    ("discord_active", "Discord Active"),
    ("discord_messages_last_30", "Discord Messages (Last 30 Days)"),
    ("is_organizer", "Is Organizer"),
]

DEFAULT_COLUMNS = ["first_name", "last_name", "email"]


class CSVColumnSelectForm(forms.Form):
    columns = forms.MultipleChoiceField(
        choices=COLUMN_CHOICES,
        initial=DEFAULT_COLUMNS,
        widget=forms.CheckboxSelectMultiple,
        label="Columns to include",
    )
