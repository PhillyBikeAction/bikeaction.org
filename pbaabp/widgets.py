from django_recaptcha.widgets import ReCaptchaBase


class ReCaptchaV2Explicit(ReCaptchaBase):
    input_type = "hidden"
    template_name = "widget_v2_explicit.html"

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        del attrs["data-callback"]
        attrs["data-size"] = "invisible"
        attrs["class"] = "g-recaptcha g-recaptcha-explicit"
        return attrs
