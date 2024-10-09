import json
import pathlib

from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.html import mark_safe
from shapely.geometry import Point, shape

from facets.models import District, RegisteredCommunityOrganization, Custom
from facets.utils import geocode_address

with open(pathlib.Path(__file__).parent / "data" / "Zoning_RCO-2.geojson") as f:
    RCOS = json.load(f)

with open(pathlib.Path(__file__).parent / "data" / "Council_Districts_2024.geojson") as f:
    DISTRICTS = json.load(f)

with open(pathlib.Path(__file__).parent / "data" / "Political_Divisions.geojson") as f:
    DIVISIONS = json.load(f)

with open(pathlib.Path(__file__).parent / "data" / "polling_places.geojson") as f:
    POLLING_PLACES = json.load(f)


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
            f"Failed to find address ({submission}) "
            "be sure to include your entire street address"
        )
        return HttpResponse(f'<p style="color: red;">{error}</p>')

    point = Point(address.longitude, address.latitude)

    rcos = []
    rcos_geojson = []
    other = []
    wards = []
    for feature in RCOS["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            rcos_geojson.append(mark_safe(json.dumps(feature)))
            if feature["properties"]["ORG_TYPE"] == "Ward":
                wards.append(feature["properties"])
            elif feature["properties"]["ORG_TYPE"] in ["NID", "SSD", None]:
                other.append(feature["properties"])
            else:
                rcos.append(feature["properties"])

    district = None
    district_geojson = None
    for feature in DISTRICTS["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            district = feature["properties"]["DISTRICT"]
            district_geojson = mark_safe(json.dumps(feature))
            break

    ward, division = None, None
    for feature in DIVISIONS["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            dn = feature["properties"]["DIVISION_NUM"]
            ward, division = [int(dn[i : i + 2]) for i in range(0, len(dn), 2)]
            break

    polling_place = None
    for feature in POLLING_PLACES["features"]:
        if feature["properties"]["ward"] == ward and feature["properties"]["division"] == division:
            polling_place = (
                f"{feature['properties']['placename']} - {feature['properties']['street_address']}"
            )
            break

    return render(
        request,
        "rco_partial.html",
        context={
            "DISTRICT": district,
            "DISTRICT_GEOJSON": district_geojson,
            "RCOS": rcos,
            "RCOS_GEOJSON": rcos_geojson,
            "OTHER": other,
            "WARDS": wards,
            "WARD": ward,
            "DIVISION": division,
            "POLLING_PLACE": polling_place,
            "address": address,
            "address_lat": address.latitude,
            "address_long": address.longitude,
        },
    )


def report(request):
    districts = District.objects.annotate(Count("contained_profiles"))
    rcos = RegisteredCommunityOrganization.objects.annotate(Count("contained_profiles"))
    context = {"districts": districts, "rcos": rcos}
    return render(request, "facets_report.html", context=context)


def rco_list(request):
    rcos = RegisteredCommunityOrganization.objects.all
    return render(request, "facets_rco_list.html", context={"rcos": rcos})


def rco(request, rco_id):
    rco = RegisteredCommunityOrganization.objects.get(id=rco_id)
    context = {"rco": rco}
    return render(request, "facets_rco.html", context=context)

@staff_member_required
def rco_detail(request, rco_id):
    rco = RegisteredCommunityOrganization.objects.get(id=rco_id)
    context = {"rco": rco}
    return render(request, "facets_rco_detail.html", context=context)


@staff_member_required
def custom_list(request):
    custom = Custom.objects.all
    return render(request, "facets_custom_list.html", context={"custom": custom})

@staff_member_required
def custom_detail(request, custom_id):
    custom = Custom.objects.get(id=custom_id)
    context = {"custom": custom}
    return render(request, "facets_custom_detail.html", context=context)
