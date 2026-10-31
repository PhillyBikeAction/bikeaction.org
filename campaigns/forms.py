from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Invisible

from campaigns.models import Petition, PetitionSignature


class PetitionSignatureForm(forms.ModelForm):
    class Meta:
        model = PetitionSignature
        fields = Petition.PetitionSignatureChoices.values + [
            "newsletter_opt_in",
            "create_account_opt_in",
            "affiliations",
        ]
        help_texts = {
            "comment": "Your comment, which will be displayed on the campaign page",
            "newsletter_opt_in": "Subscribe to Philly Bike Action's monthly newsletter.",
            "create_account_opt_in": (
                "By creating a PBA account, you agree that you have read the "
                '<a target="_blank" href="https://apps.bikeaction.org/policies/code-of-conduct/">'
                "Philly Bike Action Code of Conduct</a>"
                " and "
                '<a target="_blank" href="https://apps.bikeaction.org/policies/privacy-and-data/">'
                "Privacy and Data Statement</a>."
            ),
        }
        labels = {
            "first_name": "First Name",
            "last_name": "Last Name",
            "zip_code": "Zip Code",
            "newsletter_opt_in": "Newsletter opt in",
            "create_account_opt_in": "Create PBA Account",
            "affiliations": "Are you affiliated with any of the following organizations:",
        }
        widgets = {"affiliations": forms.CheckboxSelectMultiple}

    send_email = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Check this box to send an email when submitting your signature",
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)

    def __init__(self, *args, **kwargs):
        self.petition = kwargs.pop("petition", None)
        retained_fields = ["newsletter_opt_in"]
        if self.petition.create_account_opt_in:
            retained_fields += ["create_account_opt_in"]
        super().__init__(*args, **kwargs)
        affiliation_options = self.petition.affiliation_options.all()
        if affiliation_options.exists():
            retained_fields.append("affiliations")
            field = self.fields["affiliations"]
            field.queryset = affiliation_options
            field.widget.attrs["id"] = f"id_affiliations_{self.petition.pk}"
        required_fields = list(self.petition.signature_fields or [])
        to_remove = []
        for field in self.fields.keys():
            if field not in required_fields:
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
        if self.petition.create_account_opt_in:
            required_fields.append("first_name")
            required_fields.append("last_name")
            required_fields.append("email")
            required_fields.append("postal_address_line_1")
            required_fields.append("zip_code")
            if "first_name" in to_remove:
                to_remove.remove("first_name")
            if "last_name" in to_remove:
                to_remove.remove("last_name")
            if "email" in to_remove:
                to_remove.remove("email")
            if "postal_address_line_1" in to_remove:
                to_remove.remove("postal_address_line_1")
            if "zip_code" in to_remove:
                to_remove.remove("zip_code")
        to_remove.remove("captcha")
        for field in to_remove:
            if field not in retained_fields:
                del self.fields[field]
        for field in self.fields.keys():
            if field in required_fields and (
                field not in ["postal_address_line_2", "phone_number", "comment", "send_email"]
            ):
                self.fields[field].required = True

        if (
            "comment" in self.fields.keys()
            and self.petition.email_include_comment
            and not self.petition.mailto_send
        ):
            self.fields[
                "comment"
            ].help_text += (
                " and will be included if you choose to send an email along with your signature"
            )

        for checkbox in self.petition.checkboxes.all():
            field_name = f"checkbox_{checkbox.id}"
            self.fields[field_name] = forms.BooleanField(
                label=checkbox.label,
                help_text=checkbox.help_text,
                required=checkbox.required,
            )

        self.fields["newsletter_opt_in"] = self.fields.pop("newsletter_opt_in")
