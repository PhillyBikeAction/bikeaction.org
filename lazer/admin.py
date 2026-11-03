import asyncio
import csv

from admin_extra_buttons.api import ExtraButtonsMixin, button
from django.contrib import admin
from django.contrib.admin.helpers import AdminForm
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from campaigns.admin import randomize_lat_long
from facets.utils import reverse_geocode_point
from lazer.models import Banner, ViolationReport, ViolationSubmission
from lazer.report_forms import ReportAreaForm, ReportComparisonForm
from lazer.reports import filter_violation_reports, generate_html_report
from lazer.tasks import submit_violation_report_to_ppa
from pbaabp.admin import ReadOnlyLeafletGeoAdminMixin


class ViolationSubmissionAdmin(ReadOnlyLeafletGeoAdminMixin, admin.ModelAdmin):
    list_display = (
        "image_tag_no_href",
        "captured_at",
        "created_by",
        "location",
        "violation_report_link",
    )
    readonly_fields = ("image_tag", "reverse_geocode_results")
    search_fields = (
        "created_by__email",
        "created_by__first_name",
        "created_by__last_name",
    )

    def violation_report_link(self, obj):
        try:
            report = ViolationReport.objects.get(submission=obj)
            url = reverse("admin:lazer_violationreport_change", args=[report.id])
            return format_html('<a href="{}">View Report</a>', url)
        except ViolationReport.DoesNotExist:
            return "-"

    violation_report_link.short_description = "Report"

    def reverse_geocode_results(self, obj):
        if not obj.location:
            return "No location data available"

        try:
            # Run the async function in a sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            coordinates = f"{obj.location.y}, {obj.location.x}"
            addresses = loop.run_until_complete(
                reverse_geocode_point(coordinates, exactly_one=False)
            )

            if not addresses:
                return "No addresses found"

            # Format the results as HTML
            html_parts = ["<div style='margin-top: 10px;'>"]
            html_parts.append(f"<strong>Coordinates:</strong> {coordinates}<br><br>")
            html_parts.append("<strong>Possible Addresses:</strong><br>")
            html_parts.append("<ul>")

            for i, address in enumerate(addresses):
                html_parts.append(f"<li>{address.address}</li>")

            html_parts.append("</ul>")
            html_parts.append("</div>")

            return mark_safe("".join(html_parts))

        except Exception as e:
            return f"Error retrieving addresses: {str(e)}"
        finally:
            loop.close()

    reverse_geocode_results.short_description = "Reverse Geocode Results"


class IsSubmittedFilter(admin.SimpleListFilter):
    title = "is submitted"
    parameter_name = "submitted"

    def lookups(self, request, model_admin):
        return ((True, "Yes"), (False, "No"))

    def queryset(self, request, queryset):
        if self.value() == "True":
            return queryset.filter(
                submitted__isnull=False,
            )
        elif self.value() == "False":
            return queryset.filter(Q(submitted__isnull=True))
        return queryset


class ViolationReportAdmin(ExtraButtonsMixin, admin.ModelAdmin):
    list_display = (
        "image_tag_violation_no_href",
        "violation_observed_short",
        "is_submitted",
        "created_by",
        "date_observed",
        "time_observed",
    )
    list_filter = ("violation_observed", IsSubmittedFilter)
    list_select_related = True
    search_fields = (
        "submission__created_by__email",
        "submission__created_by__first_name",
        "submission__created_by__last_name",
    )
    readonly_fields = (
        "image_tag_violation",
        "image_tag_redacted",
        "image_tag_before_submit",
        "image_tag_after_submit",
        "image_tag_success",
        "image_tag_error",
        "image_tag_final",
    )
    exclude = ("redacted_image",)
    actions = ["bulk_resubmit_violations", "export_locations_csv"]
    raw_id_fields = ("submission",)  # Use raw ID field instead of dropdown

    def get_queryset(self, request):
        """Optimize queries by prefetching related submission and user."""
        qs = super().get_queryset(request)
        return qs.select_related("submission", "submission__created_by")

    @button(
        label="Generate Lazer Vision report",
        change_list=True,
        change_form=False,
        permission=lambda request, obj, handler: (
            handler.model_admin.admin_site.has_permission(request)
            and handler.model_admin.has_view_permission(request)
        ),
        decorators=[never_cache, csrf_protect],
    )
    def generate_report(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        queryset = self.get_queryset(request)

        step = request.POST.get("report_step", "area")
        area_form = ReportAreaForm(request.POST if step != "area" else None)
        comparison_form = ReportComparisonForm(
            request.POST if step in ("review", "download") else None
        )
        # Preserve values when returning to an earlier step.
        if step == "area" and "filter_mode" in request.POST:
            area_form = ReportAreaForm(request.POST)
            comparison_form = ReportComparisonForm(request.POST)
        if step == "comparison":
            comparison_form = ReportComparisonForm(
                initial={
                    "comparison_date": request.POST.get("comparison_date", ""),
                    "start_date": request.POST.get("start_date", ""),
                    "end_date": request.POST.get("end_date", ""),
                    "timezone": request.POST.get("timezone", "America/New_York"),
                }
            )

        matching_count = before_count = after_count = None
        if step not in ("area", "comparison", "review", "download"):
            step = "area"
        if step != "area":
            if not area_form.is_valid():
                step = "area"
            elif step in ("review", "download"):
                if not comparison_form.is_valid():
                    step = "comparison"
                else:
                    data = area_form.cleaned_data
                    violations = filter_violation_reports(
                        queryset,
                        polygon=area_form.polygon,
                        street_name=data["street_name"],
                        block_range=data["block_range"],
                        start_date=comparison_form.cleaned_data["start_date"],
                        end_date=comparison_form.cleaned_data["end_date"],
                        timezone_name=comparison_form.cleaned_data["timezone"],
                    )
                    comparison_date = comparison_form.comparison_datetime()
                    matching_count = violations.count()
                    before_count = (
                        violations.filter(submission__captured_at__lt=comparison_date).count()
                        if comparison_date
                        else 0
                    )
                    after_count = matching_count - before_count
                    if step == "download":
                        html = generate_html_report(
                            violations,
                            area_form.polygon,
                            comparison_date,
                            comparison_date.strftime("%Y-%m-%d") if comparison_date else None,
                            before_count,
                            after_count,
                            data["geojson"],
                            data["filter_mode"],
                            data["street_name"],
                            data["block_range"],
                            start_date=comparison_form.cleaned_data["start_date"],
                            end_date=comparison_form.cleaned_data["end_date"],
                            timezone_name=comparison_form.cleaned_data["timezone"],
                        )
                        response = HttpResponse(html, content_type="text/html; charset=utf-8")
                        response["Content-Disposition"] = (
                            'attachment; filename="lazer-vision-report.html"'
                        )
                        return response

        context = {
            **self.admin_site.each_context(request),
            "title": "Generate Lazer Vision report",
            "opts": self.model._meta,
            "step": step,
            "area_form": area_form,
            "comparison_form": comparison_form,
            "area_admin_form": AdminForm(
                area_form, [(None, {"fields": list(area_form.fields)})], {}
            ),
            "comparison_admin_form": AdminForm(
                comparison_form, [(None, {"fields": list(comparison_form.fields)})], {}
            ),
            "matching_count": matching_count,
            "before_count": before_count,
            "after_count": after_count,
            "changelist_url": reverse("admin:lazer_violationreport_changelist"),
            "media": self.media + area_form.media + comparison_form.media,
        }
        return TemplateResponse(
            request, "admin/lazer/violationreport/generate_report.html", context
        )

    @button(
        label="Resubmit",
        change_form=True,
        change_list=True,
        permission=lambda request, obj, **kw: bool(obj.screenshot_error) or obj.submitted is None,
    )
    def resubmit(self, request, object_id):
        report = ViolationReport.objects.get(pk=object_id)
        submit_violation_report_to_ppa.delay(report.id)

    @admin.action(description="Re-submit selected violations to PPA")
    def bulk_resubmit_violations(self, request, queryset):
        """Bulk action to re-submit multiple violation reports to the PPA."""
        count = 0
        for report in queryset:
            # Queue each report for submission
            submit_violation_report_to_ppa.delay(report.id)
            count += 1

        self.message_user(
            request,
            f"Successfully queued {count} violation report(s) for re-submission to the PPA. "
            f"Check the Celery worker logs for progress.",
        )

    @admin.action(description="Export selected violations as CSV with lat/long")
    def export_locations_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="violation_reports_locations.csv"'

        writer = csv.writer(response)
        writer.writerow(["date", "time", "violation_type", "latitude", "longitude"])

        reports = queryset.select_related("submission")

        for report in reports:
            lat, lng = randomize_lat_long(
                report.id, report.submission.location.y, report.submission.location.x
            )
            writer.writerow(
                [
                    report.date_observed,
                    report.time_observed,
                    report.violation_observed_short(),
                    lat,
                    lng,
                ]
            )

        return response


class BannerAdmin(admin.ModelAdmin):
    list_display = ("content_preview", "color", "is_active", "updated_at")
    list_filter = ("is_active", "color")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at")

    def content_preview(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content

    content_preview.short_description = "Content"

    def save_model(self, request, obj, form, change):
        # Ensure only one banner is active at a time
        if obj.is_active:
            Banner.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


admin.site.register(ViolationSubmission, ViolationSubmissionAdmin)
admin.site.register(ViolationReport, ViolationReportAdmin)
admin.site.register(Banner, BannerAdmin)
