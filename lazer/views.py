import asyncio
import base64
import datetime
import json
import secrets
from functools import wraps
from importlib import import_module

import pytz
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, logout
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt

from campaigns.admin import randomize_lat_long
from facets.utils import reverse_geocode_point
from lazer.forms import ReportForm, SubmissionForm
from lazer.integrations.platerecognizer import read_plate
from lazer.integrations.submit_form import MobilityAccessViolation
from lazer.models import Banner, LazerWrapped, ViolationReport, ViolationSubmission
from lazer.session_backend import SessionStore as LazerSessionStore

# Keep the default session store for backwards compatibility with existing sessions
DjangoSessionStore = import_module(settings.SESSION_ENGINE).SessionStore
User = get_user_model()


def get_image_from_data_url(data_url):
    _format, _dataurl = data_url.split(";base64,")
    _filename, _extension = secrets.token_hex(20), _format.split("/")[-1]

    file = ContentFile(base64.b64decode(_dataurl), name=f"{_filename}.{_extension}")

    return file, (_filename, _extension)


@sync_to_async
def get_user_from_request(request):
    return request.user if bool(request.user) else None


def api_auth(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        if "Authorization" in request.headers and request.headers["Authorization"].startswith(
            "Session: "
        ):
            session_key = request.headers["Authorization"].split("Session: ")[1]
            # Try LazerSessionStore first, then fall back to Django's session store
            for store_class in (LazerSessionStore, DjangoSessionStore):
                session = store_class(session_key=session_key)
                user_id = session.get("_auth_user_id")
                if user_id:
                    try:
                        request.user = User.objects.get(id=user_id)
                        request.session = session
                        return view_func(request, *args, **kwargs)
                    except User.DoesNotExist:
                        pass
        return JsonResponse({"error": "invalid auth"}, status=403)

    return _wrapped_view


def aapi_auth(view_func):
    @wraps(view_func)
    async def _wrapped_view(request, *args, **kwargs):
        _user = await request.auser()
        if _user.is_authenticated:
            return await view_func(request, *args, **kwargs)
        if "Authorization" in request.headers and request.headers["Authorization"].startswith(
            "Session: "
        ):
            session_key = request.headers["Authorization"].split("Session: ")[1]
            # Try LazerSessionStore first, then fall back to Django's session store
            for store_class in (LazerSessionStore, DjangoSessionStore):
                session = store_class(session_key=session_key)
                user_id = await session.aget("_auth_user_id")
                if user_id:
                    try:
                        request.user = await User.objects.aget(id=user_id)
                        request.session = session
                        return await view_func(request, *args, **kwargs)
                    except User.DoesNotExist:
                        pass
        return JsonResponse({"error": "invalid auth"}, status=403)

    return _wrapped_view


@aapi_auth
@csrf_exempt
@transaction.non_atomic_requests
async def submission_api(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST)
        if form.is_valid():
            image, _ = get_image_from_data_url(form.cleaned_data["image"])
            user = await get_user_from_request(request)

            submission = ViolationSubmission(
                image=image,
                location=Point(
                    float(form.cleaned_data["longitude"]), float(form.cleaned_data["latitude"])
                ),
                captured_at=form.cleaned_data["datetime"],
                created_by=user,
            )
            await submission.asave()
            await submission.arefresh_from_db()

            data, addresses = await asyncio.gather(
                read_plate(
                    form.cleaned_data["image"].split(";base64,")[1],
                    datetime.datetime.now(datetime.timezone.utc),
                ),
                reverse_geocode_point(
                    f"{form.cleaned_data['latitude']}, {form.cleaned_data['longitude']}",
                    exactly_one=False,
                ),
            )

            # Store the Plate Recognizer response for later use (e.g., redacting plates)
            submission.plate_recognizer_response = data
            await submission.asave()

            vehicles = data.get("results", [])
            return JsonResponse(
                {
                    "vehicles": (
                        sorted(
                            [v for v in vehicles if v.get("vehicle") is not None],
                            key=lambda x: x.get("vehicle", {}).get("score", 0),
                            reverse=True,
                        )[:4]
                    ),
                    "addresses": [address.address for address in addresses],
                    "address": addresses[0].address,
                    "timestamp": form.cleaned_data["datetime"],
                    "submissionId": submission.submission_id,
                },
                status=200,
            )
        else:
            return JsonResponse({}, status=400)


@aapi_auth
@csrf_exempt
@transaction.non_atomic_requests
async def report_api(request):
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            submission = await ViolationSubmission.objects.filter(
                submission_id=form.cleaned_data["submission_id"]
            ).afirst()
            if submission is None:
                return JsonResponse(
                    {"submitted": False, "error": "Reports must have a valid submission_id"},
                    status=400,
                )

            mobility_access_violation = MobilityAccessViolation(
                make=form.cleaned_data["make"],
                model=form.cleaned_data["model"],
                body_style=form.cleaned_data["body_style"],
                vehicle_color=form.cleaned_data["vehicle_color"],
                violation_observed=form.cleaned_data["violation_observed"],
                occurrence_frequency=form.cleaned_data["occurrence_frequency"],
                additional_information=form.cleaned_data["additional_information"],
                date_time_observed=None,
                _date_observed=form.cleaned_data["date_observed"],
                _time_observed=form.cleaned_data["time_observed"],
                address=None,
                _block_number=form.cleaned_data["block_number"],
                _street_name=form.cleaned_data["street_name"],
                _zip_code=form.cleaned_data["zip_code"],
            )

            violation_report = ViolationReport(
                submission=submission,
                date_observed=mobility_access_violation.date_observed,
                time_observed=mobility_access_violation.time_observed,
                make=mobility_access_violation.make,
                model=mobility_access_violation.model,
                body_style=mobility_access_violation.body_style,
                vehicle_color=mobility_access_violation.vehicle_color,
                violation_observed=mobility_access_violation.violation_observed,
                occurrence_frequency=mobility_access_violation.occurrence_frequency,
                block_number=mobility_access_violation.block_number,
                street_name=mobility_access_violation.street_name,
                zip_code=mobility_access_violation.zip_code,
                additional_information=mobility_access_violation.additional_information,
            )

            await violation_report.asave()

            return JsonResponse(
                {
                    "submitted": True,
                },
                status=200,
            )
        else:
            return JsonResponse({"submitted": False}, status=400)


@cache_page(30)
def map_data(request):
    violation_filter = request.GET.get("violation", None)
    date_gte = request.GET.get("date_gte", None)
    date_lte = request.GET.get("date_lte", None)
    date = request.GET.get("date", None)

    pins = []
    queryset = ViolationReport.objects.filter(submitted__isnull=False).select_related("submission")
    if violation_filter:
        queryset = queryset.filter(violation_observed__startswith=violation_filter).filter(
            submission__captured_at__lt=timezone.now() - datetime.timedelta(minutes=15)
        )

    if date:
        queryset = queryset.filter(
            submission__captured_at__date=datetime.datetime.strptime(date, "%Y-%m-%d")
            .astimezone(pytz.timezone("America/New_York"))
            .date()
        )
    else:
        if date_gte:
            queryset = queryset.filter(
                submission__captured_at__gte=datetime.datetime.strptime(date_gte, "%Y-%m-%d")
                .astimezone(pytz.timezone("America/New_York"))
                .date()
            )
        if date_lte:
            queryset = queryset.filter(
                submission__captured_at__lte=datetime.datetime.strptime(date_lte, "%Y-%m-%d")
                .astimezone(pytz.timezone("America/New_York"))
                .date()
            )

    # Count unique users who submitted violations
    unique_users = set()
    for report in queryset.only("submission__location", "submission__created_by").all():
        if report.submission.created_by_id:
            unique_users.add(report.submission.created_by_id)
        lat, lng = randomize_lat_long(
            report.id, *(report.submission.location.y, report.submission.location.x)
        )
        pins.append([lat, lng, 1])

    return JsonResponse({"pins": pins, "unique_users_count": len(unique_users)}, safe=False)


def map(request):
    return render(request, "heatmap.html")


def list(request):
    queryset = (
        ViolationReport.objects.filter(submitted__isnull=False)
        .select_related("submission")
        .order_by("-submission__captured_at")
        .all()
    )
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "list.html", {"page_obj": page_obj})


def get_wrapped_info(user):
    """Get wrapped info for a user if one exists."""
    year = datetime.datetime.now().year
    wrapped = LazerWrapped.objects.filter(user=user, year=year).first()
    if wrapped:
        return {
            "available": True,
            "share_url": wrapped.get_share_url(),
            "year": wrapped.year,
        }
    return {"available": False}


@csrf_exempt
def login_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode())
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid JSON"}, status=400)

        username = data.get("username")
        password = data.get("password")

        errors = []
        if username is None:
            errors.append("username required")
        if password is None:
            errors.append("password required")

        if errors:
            return JsonResponse({"error": ",".join(errors)}, status=400)
    else:
        return JsonResponse({"error": "POST only"}, status=400)

    user = authenticate(username=username, password=password)
    if user is not None:
        # Create a LazerSession (separate from Django sessions, 1-year expiry)
        session = LazerSessionStore()
        session["_auth_user_id"] = str(user.pk)
        session["_auth_user_backend"] = user.backend
        session.set_expiry(365 * 24 * 60 * 60)  # 1 year
        session.create()
        return JsonResponse(
            {
                "success": "ok",
                "username": user.email,
                "first_name": user.first_name,
                "session_key": session.session_key,
                "expiry_date": session.get_expiry_date(),
                "donor": user.profile.donor(),
                "wrapped": get_wrapped_info(user),
            },
            status=200,
        )
    return JsonResponse({"error": "invalid auth"}, status=403)


@api_auth
def check_login(request):
    return JsonResponse(
        {
            "success": "ok",
            "username": request.user.email,
            "first_name": request.user.first_name,
            "donor": request.user.profile.donor(),
            "wrapped": get_wrapped_info(request.user),
        },
        status=200,
    )


def logout_api(request):
    logout(request)
    return JsonResponse({"success": "ok"}, status=200)


@cache_page(60)
def banner_api(request):
    """Return the active banner if one exists."""
    banner = Banner.objects.filter(is_active=True).first()
    if banner is None:
        return JsonResponse({})
    return JsonResponse(
        {
            "content_html": banner.content_html(),
            "color": banner.color,
        }
    )


def calculate_wrapped_stats(user, year):
    """Calculate all wrapped statistics for a user and year."""
    from collections import Counter

    from django.db.models import Count

    # Get all submitted reports for this user in the given year
    reports = ViolationReport.objects.filter(
        submission__created_by=user,
        submitted__isnull=False,
        submission__captured_at__year=year,
    ).select_related("submission")

    total_reports = reports.count()
    if total_reports == 0:
        return None

    # Calculate community stats for comparison
    user_report_counts = (
        ViolationReport.objects.filter(
            submitted__isnull=False,
            submission__captured_at__year=year,
            submission__created_by__isnull=False,
        )
        .values("submission__created_by")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    all_counts = [u["count"] for u in user_report_counts]
    total_users = len(all_counts)
    total_community_reports = sum(all_counts)
    avg_reports = total_community_reports / total_users if total_users > 0 else 0

    # Find user's rank
    rank = 1
    for u in user_report_counts:
        if u["submission__created_by"] == user.id:
            break
        rank += 1

    # Calculate percentile (what percentage of users they beat)
    percentile = int(((total_users - rank) / total_users) * 100) if total_users > 0 else 0

    # Calculate what percentage of total reports this user contributed
    percent_of_total = (
        round((total_reports / total_community_reports) * 100, 1)
        if total_community_reports > 0
        else 0
    )

    # Total submissions (unique images submitted)
    total_submissions = (
        ViolationSubmission.objects.filter(created_by=user, captured_at__year=year)
        .distinct()
        .count()
    )

    # Violations by type
    violation_counts = Counter()
    street_counts = Counter()
    zip_counts = Counter()
    month_counts = Counter()
    first_date = None

    day_counts = Counter()

    for report in reports:
        # Count violation types (use short form)
        violation_type = report.violation_observed.split(" (")[0]
        violation_counts[violation_type] += 1

        # Count streets
        street_counts[report.street_name] += 1

        # Count zip codes
        zip_counts[report.zip_code] += 1

        # Count by month
        month = report.submission.captured_at.month
        month_counts[month] += 1

        # Count by day
        report_date = report.submission.captured_at.date()
        day_counts[report_date] += 1

        # Track first report date
        if first_date is None or report_date < first_date:
            first_date = report_date

    # Calculate longest streak
    sorted_days = sorted(day_counts.keys())
    longest_streak = 0
    longest_streak_start = None
    longest_streak_end = None
    longest_streak_reports = 0

    current_streak = 1
    current_streak_start = sorted_days[0] if sorted_days else None
    current_streak_reports = day_counts[sorted_days[0]] if sorted_days else 0

    for i in range(1, len(sorted_days)):
        if (sorted_days[i] - sorted_days[i - 1]).days == 1:
            current_streak += 1
            current_streak_reports += day_counts[sorted_days[i]]
        else:
            if current_streak > longest_streak:
                longest_streak = current_streak
                longest_streak_start = current_streak_start
                longest_streak_end = sorted_days[i - 1]
                longest_streak_reports = current_streak_reports
            current_streak = 1
            current_streak_start = sorted_days[i]
            current_streak_reports = day_counts[sorted_days[i]]

    # Check final streak
    if current_streak > longest_streak:
        longest_streak = current_streak
        longest_streak_start = current_streak_start
        longest_streak_end = sorted_days[-1] if sorted_days else None
        longest_streak_reports = current_streak_reports

    # Find top day
    top_day_date = None
    top_day_count = 0
    if day_counts:
        top_day_date, top_day_count = day_counts.most_common(1)[0]

    # Calculate top 3 reported car make/models for this user
    user_make_model_counts = Counter()
    for report in reports:
        if report.make:
            # Combine make and model, handle cases where model is None/blank
            make_model = f"{report.make} {report.model}".strip() if report.model else report.make
            # Add descriptor for Genesis Unknown (box trucks)
            if make_model == "Genesis Unknown":
                make_model = "Genesis Unknown (Box truck)"
            user_make_model_counts[make_model] += 1

    top_user_vehicles = [
        {"vehicle": vehicle, "count": count}
        for vehicle, count in user_make_model_counts.most_common(3)
    ]

    # Calculate top 3 reported car make/models across all users for this year
    community_reports = ViolationReport.objects.filter(
        submitted__isnull=False,
        submission__captured_at__year=year,
    ).select_related("submission")

    community_make_model_counts = Counter()
    for report in community_reports:
        if report.make:
            make_model = f"{report.make} {report.model}".strip() if report.model else report.make
            # Add descriptor for Genesis Unknown (box trucks)
            if make_model == "Genesis Unknown":
                make_model = "Genesis Unknown (Box truck)"
            community_make_model_counts[make_model] += 1

    top_community_vehicles = [
        {"vehicle": vehicle, "count": count}
        for vehicle, count in community_make_model_counts.most_common(3)
    ]

    return {
        "total_submissions": total_submissions,
        "total_reports": total_reports,
        "violations_by_type": dict(violation_counts.most_common()),
        "top_streets": [{"street": s, "count": c} for s, c in street_counts.most_common(5)],
        "top_zip_codes": [{"zip": z, "count": c} for z, c in zip_counts.most_common(5)],
        "reports_by_month": dict(month_counts),
        "first_report_date": first_date,
        "longest_streak": longest_streak,
        "longest_streak_start": longest_streak_start,
        "longest_streak_end": longest_streak_end,
        "longest_streak_reports": longest_streak_reports,
        "top_day_date": top_day_date,
        "top_day_count": top_day_count,
        "top_user_vehicles": top_user_vehicles,
        "top_community_vehicles": top_community_vehicles,
        "rank": rank,
        "total_users": total_users,
        "percentile": percentile,
        "avg_reports": round(avg_reports, 1),
        "total_community_reports": total_community_reports,
        "percent_of_total": percent_of_total,
    }


@api_auth
@csrf_exempt
def generate_wrapped_api(request):
    """Generate or retrieve wrapped stats for the authenticated user."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=400)

    try:
        data = json.loads(request.body.decode())
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    year = data.get("year", datetime.datetime.now().year)

    # Check if wrapped already exists for this user/year
    wrapped = LazerWrapped.objects.filter(user=request.user, year=year).first()

    if wrapped and not data.get("regenerate", False):
        return JsonResponse(
            {
                "success": True,
                "share_url": wrapped.get_share_url(),
                "share_token": wrapped.share_token,
                "stats": {
                    "total_submissions": wrapped.total_submissions,
                    "total_reports": wrapped.total_reports,
                    "violations_by_type": wrapped.violations_by_type,
                    "top_streets": wrapped.top_streets,
                    "top_zip_codes": wrapped.top_zip_codes,
                    "reports_by_month": wrapped.reports_by_month,
                    "first_report_date": (
                        wrapped.first_report_date.isoformat() if wrapped.first_report_date else None
                    ),
                    "year": wrapped.year,
                    "longest_streak": wrapped.longest_streak,
                    "top_day_date": (
                        wrapped.top_day_date.isoformat() if wrapped.top_day_date else None
                    ),
                    "top_day_count": wrapped.top_day_count,
                },
            }
        )

    # Calculate stats
    stats = calculate_wrapped_stats(request.user, year)
    if stats is None:
        return JsonResponse({"success": False, "error": f"No reports found for {year}"}, status=404)

    # Create or update wrapped
    if wrapped:
        # Update existing
        wrapped.total_submissions = stats["total_submissions"]
        wrapped.total_reports = stats["total_reports"]
        wrapped.violations_by_type = stats["violations_by_type"]
        wrapped.top_streets = stats["top_streets"]
        wrapped.top_zip_codes = stats["top_zip_codes"]
        wrapped.reports_by_month = stats["reports_by_month"]
        wrapped.first_report_date = stats["first_report_date"]
        wrapped.longest_streak = stats["longest_streak"]
        wrapped.longest_streak_start = stats["longest_streak_start"]
        wrapped.longest_streak_end = stats["longest_streak_end"]
        wrapped.longest_streak_reports = stats["longest_streak_reports"]
        wrapped.top_day_date = stats["top_day_date"]
        wrapped.top_day_count = stats["top_day_count"]
        wrapped.top_user_vehicles = stats["top_user_vehicles"]
        wrapped.top_community_vehicles = stats["top_community_vehicles"]
        wrapped.rank = stats["rank"]
        wrapped.total_users = stats["total_users"]
        wrapped.percentile = stats["percentile"]
        wrapped.avg_reports = stats["avg_reports"]
        wrapped.total_community_reports = stats["total_community_reports"]
        wrapped.percent_of_total = stats["percent_of_total"]
        wrapped.save()
    else:
        # Create new
        wrapped = LazerWrapped.objects.create(
            user=request.user,
            year=year,
            total_submissions=stats["total_submissions"],
            total_reports=stats["total_reports"],
            violations_by_type=stats["violations_by_type"],
            top_streets=stats["top_streets"],
            top_zip_codes=stats["top_zip_codes"],
            reports_by_month=stats["reports_by_month"],
            first_report_date=stats["first_report_date"],
            longest_streak=stats["longest_streak"],
            longest_streak_start=stats["longest_streak_start"],
            longest_streak_end=stats["longest_streak_end"],
            longest_streak_reports=stats["longest_streak_reports"],
            top_day_date=stats["top_day_date"],
            top_day_count=stats["top_day_count"],
            top_user_vehicles=stats["top_user_vehicles"],
            top_community_vehicles=stats["top_community_vehicles"],
            rank=stats["rank"],
            total_users=stats["total_users"],
            percentile=stats["percentile"],
            avg_reports=stats["avg_reports"],
            total_community_reports=stats["total_community_reports"],
            percent_of_total=stats["percent_of_total"],
        )

    return JsonResponse(
        {
            "success": True,
            "share_url": wrapped.get_share_url(),
            "share_token": wrapped.share_token,
            "stats": {
                "total_submissions": wrapped.total_submissions,
                "total_reports": wrapped.total_reports,
                "violations_by_type": wrapped.violations_by_type,
                "top_streets": wrapped.top_streets,
                "top_zip_codes": wrapped.top_zip_codes,
                "reports_by_month": wrapped.reports_by_month,
                "first_report_date": (
                    wrapped.first_report_date.isoformat() if wrapped.first_report_date else None
                ),
                "year": wrapped.year,
                "longest_streak": wrapped.longest_streak,
                "top_day_date": (
                    wrapped.top_day_date.isoformat() if wrapped.top_day_date else None
                ),
                "top_day_count": wrapped.top_day_count,
            },
        }
    )


def my_wrapped(request):
    """Generate/view wrapped for logged-in user."""
    if not request.user.is_authenticated:
        from django.shortcuts import redirect

        return redirect(f"/accounts/login/?next={request.path}")

    year = int(request.GET.get("year", datetime.datetime.now().year))
    regenerate = request.GET.get("regenerate") == "1"

    wrapped = LazerWrapped.objects.filter(user=request.user, year=year).first()

    if wrapped is None or regenerate:
        stats = calculate_wrapped_stats(request.user, year)
        if stats is None:
            return render(request, "wrapped_no_data.html", {"year": year})

        if wrapped:
            wrapped.total_submissions = stats["total_submissions"]
            wrapped.total_reports = stats["total_reports"]
            wrapped.violations_by_type = stats["violations_by_type"]
            wrapped.top_streets = stats["top_streets"]
            wrapped.top_zip_codes = stats["top_zip_codes"]
            wrapped.reports_by_month = stats["reports_by_month"]
            wrapped.first_report_date = stats["first_report_date"]
            wrapped.longest_streak = stats["longest_streak"]
            wrapped.longest_streak_start = stats["longest_streak_start"]
            wrapped.longest_streak_end = stats["longest_streak_end"]
            wrapped.longest_streak_reports = stats["longest_streak_reports"]
            wrapped.top_day_date = stats["top_day_date"]
            wrapped.top_day_count = stats["top_day_count"]
            wrapped.top_user_vehicles = stats["top_user_vehicles"]
            wrapped.top_community_vehicles = stats["top_community_vehicles"]
            wrapped.rank = stats["rank"]
            wrapped.total_users = stats["total_users"]
            wrapped.percentile = stats["percentile"]
            wrapped.avg_reports = stats["avg_reports"]
            wrapped.total_community_reports = stats["total_community_reports"]
            wrapped.percent_of_total = stats["percent_of_total"]
            wrapped.save()
        else:
            wrapped = LazerWrapped.objects.create(
                user=request.user,
                year=year,
                total_submissions=stats["total_submissions"],
                total_reports=stats["total_reports"],
                violations_by_type=stats["violations_by_type"],
                top_streets=stats["top_streets"],
                top_zip_codes=stats["top_zip_codes"],
                reports_by_month=stats["reports_by_month"],
                first_report_date=stats["first_report_date"],
                longest_streak=stats["longest_streak"],
                longest_streak_start=stats["longest_streak_start"],
                longest_streak_end=stats["longest_streak_end"],
                longest_streak_reports=stats["longest_streak_reports"],
                top_day_date=stats["top_day_date"],
                top_day_count=stats["top_day_count"],
                top_user_vehicles=stats["top_user_vehicles"],
                top_community_vehicles=stats["top_community_vehicles"],
                rank=stats["rank"],
                total_users=stats["total_users"],
                percentile=stats["percentile"],
                avg_reports=stats["avg_reports"],
                total_community_reports=stats["total_community_reports"],
                percent_of_total=stats["percent_of_total"],
            )

    # Redirect to the shareable URL
    from django.shortcuts import redirect

    return redirect("laser_wrapped", share_token=wrapped.share_token)


def wrapped(request, share_token):
    """Public view for a shared wrapped report."""
    wrapped_obj = LazerWrapped.objects.filter(share_token=share_token).first()
    if wrapped_obj is None:
        return render(request, "wrapped_404.html", status=404)

    # Check if this is the owner viewing their own wrapped
    is_owner = request.user.is_authenticated and request.user == wrapped_obj.user

    # Month names for display
    month_names = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec",
    }

    # Prepare monthly data for chart (Laser Vision launched in June)
    monthly_data = []
    max_count = 0
    for month in range(6, 13):
        count = wrapped_obj.reports_by_month.get(str(month), 0)
        if count > max_count:
            max_count = count
        monthly_data.append({"month": month_names[month], "count": count})

    # Calculate bar heights as percentages (max height = 100px)
    for data in monthly_data:
        if max_count > 0:
            data["height"] = int((data["count"] / max_count) * 100) if data["count"] > 0 else 4
        else:
            data["height"] = 4

    # Calculate top percentage for display
    top_percent = 100 - wrapped_obj.percentile if wrapped_obj.percentile else None

    context = {
        "wrapped": wrapped_obj,
        "monthly_data": monthly_data,
        "month_names": month_names,
        "is_owner": is_owner,
        "top_percent": top_percent,
    }
    return render(request, "wrapped.html", context)
