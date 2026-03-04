import datetime

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.gis.geos import Point as GEOPoint
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.html import mark_safe
from email_log.models import Email

from facets.models import (
    CongressionalDistrict,
    District,
    Division,
    RegisteredCommunityOrganization,
    StateHouseDistrict,
    StateSenateDistrict,
    Ward,
)
from facets.utils import geocode_address
from profiles.models import Profile


def index(request):
    return render(
        request, "rcosearch.html", context={"GOOGLE": settings.GOOGLE_MAPS_API_KEY is not None}
    )


@transaction.non_atomic_requests
async def query_address(request):
    submission = request.POST.get("street_address")
    search_address = f"{submission} Philadelphia, PA"

    try:
        address = await geocode_address(search_address)
    except Exception:
        raise
        return HttpResponse('<p style="color: red;">Backend API failure, try again?</p>')

    if address is None:
        error = (
            f"Failed to find address ({submission}) be sure to include your entire street address"
        )
        return HttpResponse(f'<p style="color: red;">{error}</p>')

    geopoint = GEOPoint(address.longitude, address.latitude)

    rcos = []
    rcos_geojson = []
    other = []
    wards = []
    primary_rco = None
    async for rco in RegisteredCommunityOrganization.objects.filter(mpoly__contains=geopoint):
        if rco.targetable:
            primary_rco = rco
        rcos_geojson.append(mark_safe(rco.mpoly.geojson))
        if rco.properties["org_type"] == "Ward":
            wards.append(rco)
        elif rco.properties["org_type"] in ["NID", "SSD", None]:
            other.append(rco)
        else:
            rcos.append(rco)

    district = await District.objects.filter(mpoly__contains=geopoint).aget()
    district_geojson = mark_safe(district.mpoly.geojson)

    ward, division_num, polling_place = None, None, None
    division_obj = (
        await Division.objects.filter(mpoly__contains=geopoint).select_related("ward").afirst()
    )
    if division_obj:
        ward_obj = division_obj.ward
        if ward_obj:
            ward_num = ward_obj.properties.get("ward_num") or ward_obj.properties.get("ward_number")
            if ward_num is not None:
                ward = int(ward_num)
        division_num = int(division_obj.properties.get("DIVISION_NUM", "0")[2:])
        if division_obj.polling_place_name:
            polling_place = (
                f"{division_obj.polling_place_name} - {division_obj.polling_place_address}"
            )

    state_house = await StateHouseDistrict.objects.filter(mpoly__contains=geopoint).afirst()
    state_senate = await StateSenateDistrict.objects.filter(mpoly__contains=geopoint).afirst()
    congressional = await CongressionalDistrict.objects.filter(mpoly__contains=geopoint).afirst()

    return render(
        request,
        "rco_partial.html",
        context={
            "DISTRICT": district,
            "DISTRICT_GEOJSON": district_geojson,
            "RCOS": rcos,
            "RCOS_GEOJSON": rcos_geojson,
            "primary_rco": primary_rco,
            "OTHER": other,
            "WARDS": wards,
            "WARD": ward,
            "DIVISION": division_num,
            "POLLING_PLACE": polling_place,
            "STATE_HOUSE": state_house,
            "STATE_SENATE": state_senate,
            "CONGRESSIONAL": congressional,
            "address": address,
            "address_lat": address.latitude,
            "address_long": address.longitude,
        },
    )


def report(request):
    districts = District.objects.annotate(Count("contained_profiles"))
    rcos = RegisteredCommunityOrganization.objects.annotate(Count("contained_profiles"))
    wards = Ward.objects.annotate(Count("contained_profiles")).order_by(
        "-contained_profiles__count"
    )
    context = {"districts": districts, "rcos": rcos, "wards": wards}
    return render(request, "facets_report.html", context=context)


@staff_member_required
def email_report(request):
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)

    all_profiles = Profile.objects.filter(
        user__email__isnull=False, location__isnull=False
    ).select_related("user")

    email_to_profile = {profile.user.email.lower(): profile for profile in all_profiles}

    email_counts = {}

    recent_emails = Email.objects.filter(date_sent__gte=thirty_days_ago).values_list(
        "recipients", flat=True
    )

    for recipients_field in recent_emails:
        if recipients_field:
            recipients_lower = recipients_field.lower()
            for email_addr in email_to_profile.keys():
                if email_addr in recipients_lower:
                    email_counts[email_addr] = email_counts.get(email_addr, 0) + 1

    districts_data = []
    for district in District.objects.all():
        profiles_in_district = all_profiles.filter(location__within=district.mpoly)
        profile_count = profiles_in_district.count()

        if profile_count > 0:
            total_emails = sum(
                email_counts.get(profile.user.email.lower(), 0) for profile in profiles_in_district
            )

            avg_emails = total_emails / profile_count if profile_count > 0 else 0

            districts_data.append(
                {
                    "name": district.name,
                    "profile_count": profile_count,
                    "total_emails": total_emails,
                    "avg_emails": round(avg_emails, 2),
                }
            )

    districts_data.sort(key=lambda x: x["avg_emails"], reverse=True)

    rcos_data = []
    for rco in RegisteredCommunityOrganization.objects.filter(targetable=True):
        profiles_in_rco = all_profiles.filter(location__within=rco.mpoly)
        profile_count = profiles_in_rco.count()

        if profile_count > 0:
            total_emails = sum(
                email_counts.get(profile.user.email.lower(), 0) for profile in profiles_in_rco
            )

            avg_emails = total_emails / profile_count if profile_count > 0 else 0

            rcos_data.append(
                {
                    "name": rco.name,
                    "profile_count": profile_count,
                    "total_emails": total_emails,
                    "avg_emails": round(avg_emails, 2),
                }
            )

    rcos_data.sort(key=lambda x: x["avg_emails"], reverse=True)

    context = {
        "districts": districts_data,
        "rcos": rcos_data,
        "date_range": f"Last 30 days (since {thirty_days_ago.date()})",
    }

    return render(request, "facets_email_report.html", context=context)


def rco_list(request):
    rcos = RegisteredCommunityOrganization.objects.all
    return render(request, "facets_rco_list.html", context={"rcos": rcos})


def rco(request, rco_id):
    rco = RegisteredCommunityOrganization.objects.get(id=rco_id)
    context = {"rco": rco}
    return render(request, "facets_rco.html", context=context)
