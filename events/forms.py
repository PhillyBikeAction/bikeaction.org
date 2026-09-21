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


# https://docs.djangoproject.com/en/6.1/topics/forms/modelforms/
class EventSignInForm(forms.ModelForm):
    class Meta:
        model = EventSignIn
        fields = [
            "first_name",
            "last_name",
            "email",
            "newsletter_opt_in",
            "volunteer_opt_in",
        ]
        labels = {
            "newsletter_opt_in": "Newsletter opt in:",
            "volunteer_opt_in": "Volunteer opt in:",
        }
        help_texts = {
            "newsletter_opt_in": "Subscribe to Philly Bike Action's monthly newsletter.",
            "volunteer_opt_in": "Receive news about volunteer opportunities with Philly Bike Action.",
        }
        
