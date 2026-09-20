from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Invisible

from events.models import EventRSVP, EventSignIn


class EventRSVPForm(forms.ModelForm):
    class Meta:
        model = EventRSVP
        fields = [
            "first_name",
            "last_name",
            "email",
        ]

    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True, max_length=100)

    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)


class EventSignInForm(forms.ModelForm):
    class Meta:
        model = EventSignIn
        fields = [
            "first_name",
            "last_name",
            "email",
            "newsletter_opt_in",
            "zip_code",
        ]
        labels = {
            "newsletter_opt_in": "Receive our Newsletter?",
        }
        help_texts = {
            "zip_code": (
                "Optionally provide your Postal / Zip Code "
                "If you're unsure of your district, "
                "or just to help us get a better idea of "
                "the distribution of our attendees throughout the city."
            ),
        }
