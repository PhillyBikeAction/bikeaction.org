from django.contrib import admin
from django_tuieditor.widgets import MarkdownEditorWidget

from pbaabp.models import MarkdownField
from release.models import Release, ReleaseSignature


class ReleaseAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("css/tui-editor.css",)}

    formfield_overrides = {MarkdownField: {"widget": MarkdownEditorWidget}}


class ReleaseSignatureAdmin(admin.ModelAdmin):
    readonly_fields = [
        "release",
        "created_at",
        "nickname",
        "legal_name",
        "email",
        "dob",
    ]


admin.site.register(Release, ReleaseAdmin)
admin.site.register(ReleaseSignature, ReleaseSignatureAdmin)
