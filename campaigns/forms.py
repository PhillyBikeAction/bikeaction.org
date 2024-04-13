import copy

from django import forms
from django_recaptcha.fields import ReCaptchaField

from campaigns.models import Petition, PetitionSignature
from pbaabp.widgets import ReCaptchaV2Explicit


class PetitionSignatureForm(forms.ModelForm):
    class Meta:
        model = PetitionSignature
        fields = Petition.PetitionSignatureChoices.values
        help_texts = {
            "comment": "Your comment, which will be displayed on the petition page",
        }

    send_email = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Check this box to send an email when submitting your signature",
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Explicit)

    def __init__(self, *args, **kwargs):
        self.petition = kwargs.pop("petition", None)
        super().__init__(*args, *kwargs)
        required_fields = copy.deepcopy(self.petition.signature_fields)
        to_remove = []
        for field in self.fields.keys():
            if field not in self.petition.signature_fields:
                to_remove.append(field)
        if self.petition.send_email:
            required_fields.append("send_email")
            required_fields.append("first_name")
            required_fields.append("last_name")
            required_fields.append("email")
            if "send_email" in to_remove:
                to_remove.remove("send_email")
            if "first_name" in to_remove:
                to_remove.remove("first_name")
            if "last_name" in to_remove:
                to_remove.remove("last_name")
            if "email" in to_remove:
                to_remove.remove("email")
        to_remove.remove("captcha")
        for field in to_remove:
            del self.fields[field]
        for field in self.fields.keys():
            if field in required_fields and (
                field not in ["postal_address_line_2", "comment", "send_email"]
            ):
                self.fields[field].required = True

        if "comment" in self.fields.keys() and self.petition.email_include_comment:
            self.fields[
                "comment"
            ].help_text += (
                " and will be included if you choose to send an email along with your signature"
            )
