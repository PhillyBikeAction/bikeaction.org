from allauth.account.forms import ResetPasswordForm
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Invisible


def validate_is_checked(value):
    if not value:
        raise ValidationError(_("Please read, acknowledge, and confirm by clicking the box"))


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        help_text="The email address you used to sign up for your Philly Bike Action Account"
    )
    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)


class CaptchaResetPasswordForm(ResetPasswordForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)


class NewsletterSignupForm(forms.Form):
    def __init__(self, *args, form_name=None, show_header=True, **kwargs):
        self.auto_id = f"{form_name}_%s"
        self.form_name = form_name
        self.show_header = show_header
        super().__init__(*args, **kwargs)

    newsletter_signup_captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)

    newsletter_signup_name = forms.CharField(
        required=True,
        label=_("Your Name"),
        widget=forms.TextInput(attrs={"hx-validate": "true", "placeholder": "Your Name"}),
    )
    newsletter_signup_email = forms.EmailField(
        label=_("Email"),
        widget=forms.TextInput(
            attrs={"hx-validate": "true", "placeholder": "Email", "type": "email"}
        ),
    )


class EmailDraftForm(forms.Form):
    subject = forms.CharField(
        required=True,
        label=_("Subject"),
        widget=forms.TextInput(
            attrs={
                "placeholder": "Email subject",
                "autocomplete": "off",
                "autocorrect": "off",
                "autocapitalize": "off",
                "spellcheck": "false",
            }
        ),
    )
    body = forms.CharField(
        required=True,
        label=_("Body (Markdown)"),
        widget=forms.Textarea(
            attrs={
                "placeholder": "Email body in Markdown format",
                "rows": 15,
                "autocomplete": "off",
                "autocorrect": "off",
                "autocapitalize": "off",
                "spellcheck": "false",
            }
        ),
    )
