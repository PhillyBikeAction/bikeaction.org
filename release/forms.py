from django.forms import BooleanField, ModelForm
from django.forms.widgets import DateInput

from release.models import ReleaseSignature


class ReleaseSignatureForm(ModelForm):
    newsletter_opt_in = BooleanField(
        required=False,
        help_text="Check this box to receive our monthly newsletter",
        label="Subscribe to PBA newsletter",
        initial=True,
    )

    class Meta:
        model = ReleaseSignature
        fields = [
            "legal_name",
            "nickname",
            "dob",
            "email",
            "newsletter_opt_in",
        ]
        labels = {
            "dob": "Date of birth",
        }
        widgets = {"dob": DateInput(attrs={"type": "date"})}
        help_texts = {
            "legal_name": "Your legal name",
            "nickname": "How you would like us to address you, since legal names often differ",
            "dob": "Your date of birth",
            "email": "Your email, a copy of this release will be sent to you",
        }
