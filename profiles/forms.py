from allauth.account.forms import SignupForm as BaseSignupForm
from django import forms
from django.core.validators import RegexValidator
from django.utils.html import mark_safe
from django_recaptcha.fields import ReCaptchaField

from pbaabp.widgets import ReCaptchaV2Explicit
from profiles.models import NewsletterSignup, Profile


class BaseProfileSignupForm(BaseSignupForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    council_district = forms.ChoiceField(choices=Profile.District.choices)
    zip_code = forms.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^(^[0-9]{5}(?:-[0-9]{4})?$|^$)",
                message="Must be a valid zipcode in formats 19107 or 19107-3200",
            )
        ],
    )
    newsletter_opt_in = forms.BooleanField(required=False)

    def save(self, request):
        user = super().save(request)
        user.username = user.email
        user.save()
        profile = Profile(
            user=user,
            council_district=self.cleaned_data["council_district"],
            zip_code=self.cleaned_data["zip_code"],
            newsletter_opt_in=self.cleaned_data["newsletter_opt_in"],
        )
        profile.save()
        return user


class ProfileSignupForm(BaseProfileSignupForm):
    captcha = ReCaptchaField()

    field_order = [
        "first_name",
        "last_name",
        "council_district",
        "zip_code",
        "email",
        "newsletter_opt_in",
        "password1",
        "password2",
        "captcha",
    ]


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "first_name",
            "last_name",
            "email",
            "council_district",
            "zip_code",
            "newsletter_opt_in",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["first_name"].initial = kwargs["instance"].user.first_name
        self.fields["last_name"].initial = kwargs["instance"].user.last_name
        self.fields["email"].initial = kwargs["instance"].user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.first_name = self.cleaned_data["first_name"]
        profile.user.last_name = self.cleaned_data["last_name"]
        if commit:
            profile.save()
            profile.user.save()
        return profile

    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(
        disabled=True,
        required=True,
        help_text=mark_safe('Update your email address <a href="/accounts/email/">here</a>'),
    )


class NewsletterSignupForm(forms.ModelForm):
    class Meta:
        model = NewsletterSignup
        fields = ["first_name", "last_name", "email"]

    first_name = forms.CharField(
        label="",
        help_text="",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "First Name"}),
    )
    last_name = forms.CharField(
        label="",
        help_text="",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Last Name"}),
    )
    email = forms.EmailField(
        label="",
        help_text="",
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Email"}),
    )

    newsletter_captcha = ReCaptchaField(widget=ReCaptchaV2Explicit())
