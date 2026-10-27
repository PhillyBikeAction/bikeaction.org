from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from elections.models import Nomination, Nominee


class NominationForm(forms.ModelForm):
    required_css_class = "required"

    # Override nominee field to use User queryset
    nominee = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__isnull=False).order_by("first_name", "last_name"),
        label="Who are you nominating?",
        help_text="Select a member to nominate for this election",
        required=True,
    )

    class Meta:
        model = Nomination
        fields = ["nomination_statement"]
        labels = {
            "nomination_statement": "Nomination Statement",
        }
        help_texts = {
            "nomination_statement": (
                "Please provide a statement explaining why you believe this person "
                "would be a good fit for this role. "
                "<b>Note</b> What you type here will be PUBLIC and linked from the ballot "
                "under the nominees name. "
                "If nominating someone besides yourself, "
                "they will have the opportunity to accept or decline your nomination."
            ),
        }
        widgets = {
            "nomination_statement": forms.Textarea(attrs={"rows": 8}),
        }

    def __init__(self, *args, election=None, nominator=None, nomination_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.election = election
        self.nominator = nominator
        self.nomination_id = nomination_id

        # Add nominee field to form (it's not in Meta.fields because we override it)
        if "nominee" not in self.fields:
            self.fields = {"nominee": self.fields.pop("nominee"), **self.fields}

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("nominee") == self.nominator and not cleaned_data.get(
            "nomination_statement"
        ):
            self.add_error("nomination_statement", "Please provide your own nomination statement.")
        return cleaned_data

    def clean_nominee(self):
        """Validate that the nominee is eligible."""
        nominee = self.cleaned_data.get("nominee")

        if not nominee:
            return nominee

        # Check if this nominator has already nominated this person for this election
        if self.election and self.nominator:
            # Get or check for nominee record
            try:
                nominee_record = Nominee.objects.get(election=self.election, user=nominee)
                # Check if this nominator already has a non-draft nomination for this nominee
                # Exclude the current nomination if we're editing
                existing_query = Nomination.objects.filter(
                    nominee=nominee_record, nominator=self.nominator, draft=False
                )
                if self.nomination_id:
                    existing_query = existing_query.exclude(id=self.nomination_id)

                if existing_query.exists():
                    raise ValidationError(
                        "You have already submitted a nomination for this person in this election."
                    )
            except Nominee.DoesNotExist:
                # No nominee record yet, this will be the first nomination
                pass

        return nominee


class NomineeProfileForm(forms.ModelForm):
    """Form for nominees to update their public profile information."""

    class Meta:
        model = Nominee
        fields = ["photo", "public_display_name", "board_responsibilities_acknowledged"]
        labels = {
            "photo": "Any photo of yourself for public display along side your nomination",
            "public_display_name": (
                "The name you would like publicly displayed along with your nomination"
            ),
            "board_responsibilities_acknowledged": "",
        }
        widgets = {
            "public_display_name": forms.TextInput(attrs={"placeholder": ""}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            # Update the label to include the user's actual name
            self.fields["public_display_name"].label = (
                f"The name you would like publicly displayed along with your nomination, "
                f"if different than {self.user.first_name} {self.user.last_name}"
            )
        # Make board responsibilities acknowledgment required
        self.fields["board_responsibilities_acknowledged"].required = True
