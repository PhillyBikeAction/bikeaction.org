from allauth.account.forms import SignupForm as BaseSignupForm
from django import forms
from django.core.validators import RegexValidator
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Invisible

from pbaabp.forms import validate_is_checked
from profiles.models import Profile


class PronounsWidget(forms.TextInput):
    """Text input with datalist for common pronoun suggestions"""

    def __init__(self, attrs=None):
        default_attrs = {"list": "pronouns-list"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def render(self, name, value, attrs=None, renderer=None):
        text_input = super().render(name, value, attrs, renderer)
        datalist = """
        <datalist id="pronouns-list">
          <option value="she/her">
          <option value="he/him">
          <option value="they/them">
          <option value="she/they">
          <option value="he/they">
          <option value="any">
        </datalist>
        """
        return mark_safe(text_input + datalist)


class BaseProfileSignupForm(BaseSignupForm):
    first_name = forms.CharField(required=True, label=_("First Name"))
    last_name = forms.CharField(required=True, label=_("Last Name"))
    pronouns = forms.CharField(
        required=False,
        label=_("Pronouns"),
        widget=PronounsWidget(),
        help_text=Profile._meta.get_field("pronouns").help_text,
    )
    street_address = forms.CharField(
        max_length=256,
        required=True,
        label=_("Street Address"),
        help_text=Profile._meta.get_field("street_address").help_text,
    )
    zip_code = forms.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^(^[0-9]{5}(?:-[0-9]{4})?$|^$)",
                message="Must be a valid zipcode in formats 19107 or 19107-3200",
            )
        ],
        label=_("Zip Code"),
    )

    account_emails = forms.BooleanField(
        disabled=True,
        required=True,
        initial=True,
        help_text=Profile._meta.get_field("account_emails").help_text,
    )

    newsletter_opt_in = forms.BooleanField(
        required=False,
        initial=True,
        help_text=Profile._meta.get_field("newsletter_opt_in").help_text,
    )

    volunteer_opt_in = forms.BooleanField(
        required=False,
        initial=False,
        help_text=Profile._meta.get_field("volunteer_opt_in").help_text,
    )

    def save(self, request):
        user = super().save(request)
        user.username = user.email
        user.save()
        profile = Profile(
            user=user,
            street_address=self.cleaned_data["street_address"],
            zip_code=self.cleaned_data["zip_code"],
            newsletter_opt_in=self.cleaned_data["newsletter_opt_in"],
            pronouns=self.cleaned_data["pronouns"],
        )
        profile.save()
        return user


class ProfileSignupForm(BaseProfileSignupForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Invisible)

    code_of_conduct = forms.BooleanField(
        label="Code of Conduct",
        help_text=(
            'I have read the <a target="_blank" '
            'href="https://apps.bikeaction.org/policies/code-of-conduct/">'
            "Philly Bike Action Code of Conduct</a>."
        ),
        required=True,
        validators=[validate_is_checked],
    )

    privacy_and_data = forms.BooleanField(
        label="Privacy and Data",
        help_text=(
            'I have read the <a target="_blank" '
            'href="https://apps.bikeaction.org/policies/privacy-and-data/">'
            "Privacy and Data Statement</a>."
        ),
        required=True,
        validators=[validate_is_checked],
    )

    field_order = [
        "first_name",
        "last_name",
        "pronouns",
        "street_address",
        "zip_code",
        "email",
        "account_emails",
        "newsletter_opt_in",
        "volunteer_opt_in",
        "password1",
        "password2",
        "captcha",
    ]

    class Meta:
        help_texts = {}


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "first_name",
            "last_name",
            "pronouns",
            "email",
            "street_address",
            "zip_code",
            "newsletter_opt_in",
        ]
        help_texts = {}

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

    first_name = forms.CharField(required=True, label=_("First Name"))
    last_name = forms.CharField(required=True, label=_("Last Name"))
    pronouns = forms.CharField(
        required=False,
        label=_("Pronouns"),
        widget=PronounsWidget(),
        help_text=Profile._meta.get_field("pronouns").help_text,
    )
    email = forms.EmailField(
        disabled=True,
        required=True,
        help_text=mark_safe('Update your email address <a href="/accounts/email/">here</a>'),
        label=_("Email"),
    )
