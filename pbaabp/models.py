import cmarkgfm
import nh3
from cmarkgfm.cmark import Options as cmarkgfmOptions
from django import forms
from django.contrib.postgres.fields import ArrayField
from markdownfield.models import MarkdownField as _MarkdownField
from markdownfield.util import process_links

_CLEAN_CONTENT_TAGS = {"script", "style", "iframe"}


class ChoiceArrayField(ArrayField):
    """
    A field that allows us to store an array of choices.

    Uses Django 1.9's postgres ArrayField
    and a MultipleChoiceField for its formfield.

    Usage:

        choices = ChoiceArrayField(models.CharField(max_length=..., choices=(...,)), default=[...])
    """

    def formfield(self, **kwargs):
        defaults = {
            "form_class": forms.MultipleChoiceField,
            "choices": self.base_field.choices,
            "widget": forms.CheckboxSelectMultiple,
        }
        defaults.update(kwargs)
        return super(ArrayField, self).formfield(**defaults)


class MarkdownField(_MarkdownField):
    def pre_save(self, model_instance, add):
        value = super().pre_save(model_instance, add)

        if not self.rendered_field:
            return value

        options = cmarkgfmOptions.CMARK_OPT_UNSAFE | cmarkgfmOptions.CMARK_OPT_GITHUB_PRE_LANG

        dirty = cmarkgfm.github_flavored_markdown_to_html(value, options=options)

        if self.validator.sanitize:
            clean = nh3.clean(
                dirty,
                tags=self.validator.allowed_tags,
                attributes=self.validator.allowed_attrs,
                clean_content_tags=_CLEAN_CONTENT_TAGS - self.validator.allowed_tags,
                link_rel="nofollow noopener noreferrer",
                filter_style_properties=self.validator.filter_style_properties,
                generic_attribute_prefixes=self.validator.generic_attribute_prefixes,
                url_schemes=self.validator.url_schemes,
            )
            clean = process_links(clean)
            setattr(model_instance, self.rendered_field, clean)
        else:
            # danger!
            setattr(model_instance, self.rendered_field, dirty)

        return value
