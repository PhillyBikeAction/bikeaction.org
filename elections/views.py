from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from elections.forms import NominationForm, NomineeProfileForm
from elections.models import (
    Ballot,
    Election,
    Nomination,
    Nominee,
    Question,
    QuestionVote,
    Vote,
    get_user_display_name,
)


@login_required
def nomination_form(request, election_slug, pk=None):
    """Create or edit a nomination for an election."""
    election = get_object_or_404(Election, slug=election_slug)

    # Check if user profile is complete
    if not request.user.profile.complete:
        messages.error(
            request,
            "Your profile must be complete to submit a nomination. Please complete your profile.",
        )
        return redirect("profile")

    # Check if user was a member in good standing at the cutoff
    eligibility = request.user.profile.eligible_as_of(election.membership_eligibility_deadline)
    if not eligibility["eligible"]:
        messages.error(
            request,
            f"You must have been a member in good standing as of "
            f"{election.membership_eligibility_deadline.strftime('%B %d, %Y')} "
            f"to submit nominations.",
        )
        return redirect("election_detail", election_slug=election.slug)

    # Check if nominations are open
    if not election.is_nominations_open():
        if timezone.now() < election.nominations_open:
            messages.error(request, "Nominations are not yet open for this election.")
        else:
            messages.error(request, "Nominations have closed for this election.")
        return redirect("election_detail", election_slug=election.slug)

    # If editing, load the existing nomination
    nomination = None
    if pk:
        nomination = get_object_or_404(
            Nomination, id=pk, nominator=request.user, nominee__election=election
        )
        # Can only edit drafts or self-nominations (while nominations are still open)
        # Self-nominations can be edited even if accepted
        if not nomination.draft:
            is_self_nomination = nomination.nominator == nomination.nominee.user
            if not is_self_nomination:
                messages.error(request, "You cannot edit a submitted nomination.")
                return redirect("nomination_view", election_slug=election.slug, pk=nomination.id)
            # Self-nominations that are declined (withdrawn) cannot be edited
            if nomination.acceptance_status == Nomination.AcceptanceStatus.DECLINED:
                messages.error(request, "You cannot edit a withdrawn nomination.")
                return redirect("nomination_view", election_slug=election.slug, pk=nomination.id)

    # Handle form submission
    if request.method == "POST":
        form = NominationForm(
            request.POST,
            instance=nomination,
            election=election,
            nominator=request.user,
            nomination_id=nomination.id if nomination else None,
            label_suffix="",
        )

        # Save draft
        if "save-draft" in request.POST:
            # Get nominee user if provided
            nominee_user_id = request.POST.get("nominee")
            nominee_user = None
            if nominee_user_id:
                try:
                    nominee_user = User.objects.get(id=nominee_user_id)
                except (User.DoesNotExist, ValueError):
                    pass

            if not nominee_user:
                messages.error(request, "Please select a nominee before saving draft.")
                return redirect("nomination_form", election_slug=election.slug)

            # Get or create nominee record
            nominee_record, _ = Nominee.objects.get_or_create(election=election, user=nominee_user)

            if nomination:
                nomination.nominee = nominee_record
                nomination.nomination_statement = request.POST.get("nomination_statement", "")
                nomination.save()
            else:
                nomination = Nomination(
                    nominee=nominee_record,
                    nominator=request.user,
                    draft=True,
                    nomination_statement=request.POST.get("nomination_statement", ""),
                )
                nomination.save()
            messages.success(request, "Nomination draft saved.")
            return redirect("profile")

        # Submit nomination
        elif "submit-nomination" in request.POST:
            if form.is_valid():
                nominee_user = form.cleaned_data["nominee"]
                is_self_nomination = nominee_user == request.user

                # Get or create nominee record
                nominee_record, _ = Nominee.objects.get_or_create(
                    election=election, user=nominee_user
                )

                # Check if nominee profile is complete for self-nominations
                if is_self_nomination and not nominee_record.is_profile_complete():
                    # Save as draft first
                    if nomination:
                        nomination.nominee = nominee_record
                        nomination.nomination_statement = form.cleaned_data["nomination_statement"]
                        nomination.draft = True
                        nomination.save()
                    else:
                        nomination = Nomination(
                            nominee=nominee_record,
                            nominator=request.user,
                            draft=True,
                            nomination_statement=form.cleaned_data["nomination_statement"],
                        )
                        nomination.save()

                    messages.info(
                        request,
                        "Please complete your nominee profile before submitting "
                        "your self-nomination.",
                    )
                    profile_url = reverse(
                        "nominee_profile_edit",
                        kwargs={
                            "election_slug": election.slug,
                            "nominee_id": nominee_record.id,
                        },
                    )
                    return redirect(f"{profile_url}?self_nomination_id={nomination.id}")

                if nomination:
                    # Update existing nomination (could be draft or submitted self-nomination)
                    nomination.nominee = nominee_record
                    nomination.nomination_statement = form.cleaned_data["nomination_statement"]
                    nomination.draft = False
                    nomination.save()
                else:
                    # Create new nomination
                    nomination = Nomination(
                        nominee=nominee_record,
                        nominator=request.user,
                        draft=False,
                        nomination_statement=form.cleaned_data["nomination_statement"],
                    )
                    nomination.save()

                display_name = get_user_display_name(nominee_user)
                messages.success(
                    request,
                    (
                        f"Nomination updated for {display_name}!"
                        if pk
                        else f"Nomination submitted for {display_name}!"
                    ),
                )
                return redirect("profile")
    else:
        # Load form with initial data if editing
        if nomination:
            form = NominationForm(
                instance=nomination,
                initial={"nominee": nomination.nominee.user.id},
                election=election,
                nominator=request.user,
                nomination_id=nomination.id,
                label_suffix="",
            )
        else:
            form = NominationForm(election=election, nominator=request.user, label_suffix="")

    return render(
        request,
        "elections/nomination_form.html",
        {"form": form, "election": election, "nomination": nomination},
    )


@login_required
def nomination_view(request, election_slug, pk):
    """View a submitted nomination."""
    election = get_object_or_404(Election, slug=election_slug)
    nomination = get_object_or_404(Nomination, id=pk, nominee__election=election)

    # Only allow viewing if user is the nominator, nominee, or staff
    if not (
        request.user == nomination.nominator
        or request.user == nomination.nominee.user
        or request.user.is_staff
    ):
        messages.error(request, "You do not have permission to view this nomination.")
        return redirect("election_detail", election_slug=election.slug)

    return render(
        request,
        "elections/nomination_view.html",
        {"nomination": nomination, "election": election},
    )


def election_detail(request, election_slug):
    """View election details and nomination status."""
    election = get_object_or_404(Election, slug=election_slug)

    # Get user's nominations if logged in
    user_nominations = []
    can_vote = False
    voting_closed = timezone.now() >= election.voting_closes

    if request.user.is_authenticated:
        user_nominations = Nomination.objects.filter(
            nominee__election=election, nominator=request.user
        ).select_related("nominee")

        # Check if user is eligible to vote
        if election.is_voting_open() and hasattr(request.user, "profile"):
            eligible_voters = election.get_eligible_voters()
            can_vote = request.user.profile in eligible_voters

    return render(
        request,
        "elections/election_detail.html",
        {
            "election": election,
            "user_nominations": user_nominations,
            "can_nominate": request.user.is_authenticated and election.is_nominations_open(),
            "can_vote": can_vote,
            "voting_closed": voting_closed,
        },
    )


def election_nominees(request, election_slug):
    """Public view of all nominees who have accepted at least one nomination."""
    election = get_object_or_404(Election, slug=election_slug)

    # Don't show nominees until nominations have closed
    if not election.is_nominations_closed():
        messages.info(request, "Nominees will be visible after nominations close.")
        return redirect("election_detail", election_slug=election.slug)

    # Get nominee IDs who have accepted at least one nomination
    nominee_ids = (
        Nominee.objects.filter(
            election=election,
            nominations__acceptance_status=Nomination.AcceptanceStatus.ACCEPTED,
            nominations__draft=False,
        )
        .values_list("id", flat=True)
        .distinct()
    )

    # Fetch the nominees in random order
    nominees = (
        Nominee.objects.filter(id__in=nominee_ids)
        .select_related("user", "user__profile")
        .prefetch_related("nominations__nominator")
        .order_by("?")  # Random order
    )

    # Filter to get only accepted nominations for each nominee
    # Sort so self-nominations appear first
    for nominee in nominees:
        accepted = nominee.nominations.filter(
            acceptance_status=Nomination.AcceptanceStatus.ACCEPTED, draft=False
        ).select_related("nominator")

        # Separate self-nominations and other nominations
        self_noms = [n for n in accepted if n.nominator == nominee.user]
        other_noms = [n for n in accepted if n.nominator != nominee.user]

        # Combine with self-nominations first
        nominee.accepted_nominations = self_noms + other_noms

    return render(
        request,
        "elections/election_nominees.html",
        {"election": election, "nominees": nominees},
    )


def nominee_detail(request, election_slug, nominee_slug):
    """Public view of an individual nominee with their nomination statements."""
    election = get_object_or_404(Election, slug=election_slug)

    # Don't show nominees until nominations have closed
    if not election.is_nominations_closed():
        messages.info(request, "Nominees will be visible after nominations close.")
        return redirect("election_detail", election_slug=election.slug)

    # Find the nominee by matching the slug
    # We need to check all nominees with accepted nominations
    nominees = (
        Nominee.objects.filter(
            election=election,
            nominations__acceptance_status=Nomination.AcceptanceStatus.ACCEPTED,
            nominations__draft=False,
        )
        .distinct()
        .select_related("user", "user__profile")
        .prefetch_related("nominations__nominator")
    )

    nominee = None
    for n in nominees:
        if n.get_slug() == nominee_slug:
            nominee = n
            break

    if not nominee:
        messages.error(request, "Nominee not found.")
        return redirect("election_nominees", election_slug=election.slug)

    # Get accepted nominations, sorted with self-nominations first
    accepted = nominee.nominations.filter(
        acceptance_status=Nomination.AcceptanceStatus.ACCEPTED, draft=False
    ).select_related("nominator")

    self_noms = [n for n in accepted if n.nominator == nominee.user]
    other_noms = [n for n in accepted if n.nominator != nominee.user]
    nominee.accepted_nominations = self_noms + other_noms

    return render(
        request,
        "elections/nominee_detail.html",
        {"election": election, "nominee": nominee},
    )


def election_list(request):
    """List all elections."""
    elections = Election.objects.all().order_by("-created_at")
    upcoming_election = Election.get_upcoming()

    return render(
        request,
        "elections/election_list.html",
        {"elections": elections, "upcoming_election": upcoming_election},
    )


@login_required
def nomination_respond(request, election_slug, pk):
    """Accept or decline a nomination."""
    election = get_object_or_404(Election, slug=election_slug)
    nomination = get_object_or_404(
        Nomination, id=pk, nominee__election=election, nominee__user=request.user, draft=False
    )

    is_self_nomination = nomination.nominator == nomination.nominee.user

    # Check if acceptance period has closed (7 days after nominations close)
    if election.is_acceptance_period_closed():
        messages.error(
            request,
            "The acceptance period has closed. You can no longer change your response.",
        )
        return redirect("profile")

    # Check if nominee profile is complete before allowing acceptance
    if request.method == "POST" and request.POST.get("action") == "accept":
        if not nomination.nominee.is_profile_complete():
            messages.info(
                request,
                "Please complete your nominee profile before accepting this nomination.",
            )
            profile_url = reverse(
                "nominee_profile_edit",
                kwargs={
                    "election_slug": election.slug,
                    "nominee_id": nomination.nominee.id,
                },
            )
            respond_url = reverse(
                "nomination_respond",
                kwargs={"election_slug": election.slug, "pk": nomination.id},
            )
            return redirect(f"{profile_url}?next={respond_url}")

    if request.method == "POST":
        action = request.POST.get("action")
        note = request.POST.get("acceptance_note", "").strip()

        if is_self_nomination:
            # For self-nominations, only allow withdrawal (decline)
            if action == "withdraw":
                nomination.acceptance_status = Nomination.AcceptanceStatus.DECLINED
                nomination.acceptance_date = timezone.now()
                nomination.save()
                messages.success(
                    request, f"You have withdrawn your nomination for {election.title}."
                )
            else:
                messages.error(request, "Invalid action.")
        else:
            # For nominations from others
            if action == "accept":
                nomination.acceptance_status = Nomination.AcceptanceStatus.ACCEPTED
                nomination.acceptance_date = timezone.now()
                nomination.acceptance_note = note
                nomination.save()
                nominator_name = get_user_display_name(nomination.nominator)
                messages.success(
                    request,
                    f"You have accepted the nomination from {nominator_name} "
                    f"for {election.title}. Good luck!",
                )
            elif action == "decline":
                nomination.acceptance_status = Nomination.AcceptanceStatus.DECLINED
                nomination.acceptance_date = timezone.now()
                nomination.acceptance_note = note
                nomination.save()
                nominator_name = get_user_display_name(nomination.nominator)
                messages.success(
                    request,
                    f"You have declined the nomination from {nominator_name} for {election.title}.",
                )
            else:
                messages.error(request, "Invalid action.")

        return redirect("profile")

    return render(
        request,
        "elections/nomination_respond.html",
        {"nomination": nomination, "election": election, "is_self_nomination": is_self_nomination},
    )


@login_required
def nominee_search(request):
    """HTMX endpoint for typeahead search of eligible nominees."""
    query = request.GET.get("q", "").strip()

    # Strip @ from the beginning if present (for Discord handle searches)
    if query.startswith("@"):
        query = query[1:]

    if not query or len(query) < 2:
        return render(request, "elections/nominee_search_results.html", {"users": []})

    # Search by name or Discord username (not email for privacy)
    users = (
        User.objects.filter(profile__isnull=False)
        .filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(socialaccount__extra_data__username__icontains=query)
        )
        .distinct()
        .select_related("profile")[:10]
    )

    # Filter to only members and create sanitized data structure
    eligible_users = []
    for user in users:
        if user.profile.membership():
            # Include Discord handle if available (OK in authenticated context)
            discord = user.socialaccount_set.filter(provider="discord").first()
            discord_handle = discord.extra_data.get("username") if discord else None

            # Only send necessary data to frontend (no email, first name + last initial + discord)
            eligible_users.append(
                {
                    "id": user.id,
                    "display_name": get_user_display_name(user),
                    "discord_handle": discord_handle,
                }
            )

    return render(request, "elections/nominee_search_results.html", {"users": eligible_users})


@login_required
def nominee_profile_edit(request, election_slug, nominee_id):
    """Allow nominees to update their public profile information."""
    election = get_object_or_404(Election, slug=election_slug)
    nominee = get_object_or_404(Nominee, id=nominee_id, election=election, user=request.user)

    # Check if acceptance period has closed (allow profile edits during acceptance period)
    if election.is_acceptance_period_closed():
        messages.error(
            request,
            "The acceptance period has closed. You can no longer update your profile.",
        )
        return redirect("profile")

    # Get the next URL from query params (for redirecting back after completion)
    next_url = request.GET.get("next") or request.POST.get("next")
    # Get self-nomination ID if this profile edit is part of a self-nomination flow
    self_nomination_id = request.GET.get("self_nomination_id") or request.POST.get(
        "self_nomination_id"
    )

    if request.method == "POST":
        form = NomineeProfileForm(request.POST, request.FILES, instance=nominee, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your nominee profile has been updated.")

            # If this was part of a self-nomination flow, auto-submit the draft nomination
            if self_nomination_id:
                try:
                    nomination = Nomination.objects.get(
                        id=self_nomination_id, nominee=nominee, nominator=request.user, draft=True
                    )
                    # Submit the nomination (this will auto-accept it via the model's save method)
                    nomination.draft = False
                    nomination.save()
                    messages.success(request, "Your self-nomination has been submitted!")
                except Nomination.DoesNotExist:
                    # Nomination not found or already submitted, just continue
                    pass

            # Redirect back to the nomination response page if next_url is provided
            if next_url:
                return redirect(next_url)
            return redirect("profile")
    else:
        form = NomineeProfileForm(instance=nominee, user=request.user)

    return render(
        request,
        "elections/nominee_profile_edit.html",
        {
            "form": form,
            "nominee": nominee,
            "election": election,
            "next_url": next_url,
            "self_nomination_id": self_nomination_id,
        },
    )


@login_required
def vote(request, election_slug):
    """Cast or update ballot for an election."""
    election = get_object_or_404(Election, slug=election_slug)

    # Check if user profile is complete
    if not request.user.profile.complete:
        messages.error(
            request,
            "Your profile must be complete to vote. Please complete your profile.",
        )
        return redirect("profile")

    # Check if user was eligible as of the membership eligibility deadline
    eligible_voters = election.get_eligible_voters()
    if request.user.profile not in eligible_voters:
        messages.error(
            request,
            f"You must have been a member in good standing as of "
            f"{election.membership_eligibility_deadline.strftime('%B %d, %Y')} "
            f"to vote in this election.",
        )
        return redirect("profile")

    # Check if this is a preview request (eligible voters only)
    preview_mode = request.GET.get("preview") == "true"

    if not preview_mode:
        # Check if voting is open
        if not election.is_voting_open():
            if timezone.now() < election.voting_opens:
                messages.error(request, "Voting has not yet opened for this election.")
            else:
                messages.error(request, "Voting has closed for this election.")
            return redirect("profile")

    # Get eligible nominees (accepted at least one nomination)
    # First get the IDs of nominees with accepted nominations
    eligible_nominee_ids = (
        Nominee.objects.filter(
            election=election,
            nominations__acceptance_status=Nomination.AcceptanceStatus.ACCEPTED,
            nominations__draft=False,
        )
        .values_list("id", flat=True)
        .distinct()
    )
    # Then get the full nominee objects and randomize order
    nominees = (
        Nominee.objects.filter(id__in=eligible_nominee_ids)
        .select_related("user__profile")
        .order_by("?")  # Random order
    )

    # Get questions for this election
    questions = Question.objects.filter(election=election).order_by("order")

    # Calculate available seats (district seats only count if district has enough voters)
    # Use the already-fetched eligible_voters from above
    eligible_voters_qs = eligible_voters

    # Count voters per district (districts 1-10)
    from collections import Counter

    district_voter_counts = Counter()
    for profile in eligible_voters_qs:
        district = profile.district
        if district:
            # Extract district number from name (e.g., "District 5" -> 5)
            import re

            match = re.search(r"\d+", district.name)
            if match:
                district_num = int(match.group())
                district_voter_counts[district_num] += 1

    # Get list of activated districts
    activated_districts = sorted(
        [
            district_num
            for district_num, count in district_voter_counts.items()
            if count >= election.district_seat_min_voters
        ]
    )
    activated_district_seats = len(activated_districts)
    total_available_seats = activated_district_seats + election.at_large_seats_count

    # Get or create ballot (unless in preview mode)
    ballot = None
    ballot_created = True
    existing_nominee_ids = set()
    existing_question_votes = {}

    if preview_mode:
        # In preview mode, don't create or retrieve a ballot
        if request.method == "POST":
            messages.warning(
                request,
                "This is a preview - your ballot was not saved. Voting is not yet open.",
            )
            return redirect(request.path + "?preview=true")
    else:
        # Normal voting mode
        ballot, ballot_created = Ballot.objects.get_or_create(election=election, voter=request.user)

        if request.method == "POST":
            # Clear existing votes (allow changes)
            ballot.candidate_votes.all().delete()
            ballot.question_votes.all().delete()

            # Process candidate votes
            nominee_ids = request.POST.getlist("nominees")
            for nominee_id in nominee_ids:
                try:
                    nominee = nominees.get(id=nominee_id)
                    Vote.objects.create(ballot=ballot, nominee=nominee)
                except Nominee.DoesNotExist:
                    pass

            # Process question votes
            for question in questions:
                answer_value = request.POST.get(f"question_{question.id}")
                if answer_value in ["yes", "no"]:
                    QuestionVote.objects.create(
                        ballot=ballot, question=question, answer=(answer_value == "yes")
                    )

            messages.success(
                request,
                "Your ballot has been saved! You can change your votes until voting closes.",
            )
            return redirect("profile")

        # Get existing votes for this ballot
        existing_nominee_ids = set(ballot.candidate_votes.values_list("nominee_id", flat=True))
        existing_question_votes = {qv.question_id: qv.answer for qv in ballot.question_votes.all()}

    return render(
        request,
        "elections/vote.html",
        {
            "election": election,
            "nominees": nominees,
            "questions": questions,
            "ballot": ballot,
            "existing_nominee_ids": existing_nominee_ids,
            "existing_question_votes": existing_question_votes,
            "ballot_created": ballot_created,
            "preview_mode": preview_mode,
            "total_available_seats": total_available_seats,
            "activated_district_seats": activated_district_seats,
            "activated_districts": activated_districts,
        },
    )


@login_required
def election_results(request, election_slug):
    """View election results (only after voting closes)."""
    election = get_object_or_404(Election, slug=election_slug)

    # Only show results after voting closes
    if timezone.now() < election.voting_closes:
        messages.error(request, "Results will be available after voting closes.")
        return redirect("profile")

    # Calculate results
    results = calculate_election_results(election)

    return render(
        request,
        "elections/results.html",
        {
            "election": election,
            "district_seats": results["district_seats"],
            "at_large_seats": results["at_large_seats"],
            "all_candidates": results["all_candidates"],
            "question_results": results["question_results"],
            "total_ballots": results["total_ballots"],
            "eligible_voters_count": results["eligible_voters_count"],
            "district_turnout": results["district_turnout"],
        },
    )


def calculate_election_results(election):
    """
    Calculate election results using district-reserved + at-large seat allocation.

    If election has been closed (final_vote_count is set), uses stored results.
    Otherwise calculates from live Vote/QuestionVote records.

    Returns:
        dict with keys:
            - district_seats: list of tuples (district_num, nominee, votes_from_district)
            - at_large_seats: list of tuples (nominee, total_votes)
            - question_results: list of tuples (question, yes_count, no_count)
            - total_ballots: int
    """
    import re
    from collections import Counter, defaultdict

    from django.db.models import Count, Q

    # Compile regex once for reuse
    DISTRICT_NUM_REGEX = re.compile(r"\d+")

    # Check if election has been closed (anonymized)
    election_closed = Nominee.objects.filter(
        election=election, final_vote_count__isnull=False
    ).exists()

    if election_closed:
        # Use stored results from closed election
        ballots = Ballot.objects.filter(election=election, had_votes=True).select_related(
            "voter__profile"
        )
        total_ballots = ballots.count()

        # Get nominee votes from stored data
        nominee_votes = {}
        nominee_district_votes = defaultdict(lambda: defaultdict(int))

        for nominee in Nominee.objects.filter(election=election).select_related("user__profile"):
            nominee_votes[nominee] = nominee.final_vote_count or 0

            # Get nominee's district number
            nominee_district = nominee.user.profile.district
            if nominee_district:
                match = DISTRICT_NUM_REGEX.search(nominee_district.name)
                if match:
                    nominee_district_num = int(match.group())
                    nominee_district_votes[nominee][nominee_district_num] = (
                        nominee.final_district_vote_count or 0
                    )
    else:
        # Calculate from live Vote records
        # Get all ballots with optimized queries
        # Only count ballots that have at least one answer (candidate vote OR question vote)
        ballots = (
            Ballot.objects.filter(election=election)
            .select_related("voter__profile")
            .prefetch_related("candidate_votes__nominee__user__profile", "question_votes")
            .annotate(
                num_candidate_votes=Count("candidate_votes"),
                num_question_votes=Count("question_votes"),
            )
            .filter(Q(num_candidate_votes__gt=0) | Q(num_question_votes__gt=0))
        )
        total_ballots = ballots.count()

        # Count votes for each nominee
        nominee_votes = Counter()
        # Track votes by district for each nominee
        nominee_district_votes = defaultdict(lambda: defaultdict(int))

        for ballot in ballots:
            voter_profile = ballot.voter.profile
            voter_district = voter_profile.district

            # Get district number (extract from "District 5" -> 5)
            voter_district_num = None
            if voter_district:
                match = DISTRICT_NUM_REGEX.search(voter_district.name)
                if match:
                    voter_district_num = int(match.group())

            # Count votes for each nominee (using prefetched data)
            for vote in ballot.candidate_votes.all():
                nominee = vote.nominee
                nominee_votes[nominee] += 1

                # Track district-specific votes if voter has a district
                if voter_district_num:
                    nominee_district_votes[nominee][voter_district_num] += 1

    # Calculate district seats
    district_seats = []
    district_winners = set()

    # Get all district numbers from DistrictFacet
    from facets.models import District as DistrictFacet

    district_numbers = []
    for district_facet in DistrictFacet.objects.all():
        match = DISTRICT_NUM_REGEX.search(district_facet.name)
        if match:
            district_numbers.append(int(match.group()))
    district_numbers = sorted(set(district_numbers))  # Remove duplicates and sort

    # Pre-calculate district info for ballots and nominees to avoid repeated iterations
    ballot_districts = {}
    for ballot in ballots:
        voter_district = ballot.voter.profile.district
        if voter_district:
            match = DISTRICT_NUM_REGEX.search(voter_district.name)
            if match:
                ballot_districts[ballot.id] = int(match.group())

    nominee_home_districts = {}
    for nominee in nominee_votes:
        nominee_district = nominee.user.profile.district
        if nominee_district:
            match = DISTRICT_NUM_REGEX.search(nominee_district.name)
            if match:
                nominee_home_districts[nominee.id] = int(match.group())

    # Count voters by district
    voters_by_district = Counter(ballot_districts.values())

    for district_num in district_numbers:
        voters_in_district = voters_by_district.get(district_num, 0)

        # Only allocate district seat if enough voters
        if voters_in_district >= election.district_seat_min_voters:
            # Find candidates from this district who meet minimum vote threshold
            candidates_for_district = []
            for nominee in nominee_votes:
                # Check if nominee is from this district
                if nominee_home_districts.get(nominee.id) == district_num:
                    district_vote_count = nominee_district_votes[nominee][district_num]
                    # Must meet threshold of votes FROM district
                    if district_vote_count >= election.district_seat_min_votes:
                        # But winner determined by TOTAL votes (from all voters)
                        total_votes = nominee_votes[nominee]
                        candidates_for_district.append((nominee, total_votes, district_vote_count))

            # Select winner (most TOTAL votes, among those who met district threshold)
            if candidates_for_district:
                winner, total_votes, district_votes = max(
                    candidates_for_district, key=lambda x: x[1]
                )
                district_seats.append(
                    {
                        "district_num": district_num,
                        "winner": winner,
                        "total_votes": total_votes,
                        "district_votes": district_votes,
                    }
                )
                district_winners.add(winner)

    # Calculate at-large seats (from remaining candidates)
    remaining_candidates = [
        (nominee, count)
        for nominee, count in nominee_votes.items()
        if nominee not in district_winners
    ]
    remaining_candidates.sort(key=lambda x: x[1], reverse=True)
    at_large_seats = remaining_candidates[: election.at_large_seats_count]
    at_large_winners = {nominee for nominee, _ in at_large_seats}

    # Compile all candidates with results
    all_candidates = []
    for nominee, total_votes in nominee_votes.items():
        # Use pre-calculated district number
        district_num = nominee_home_districts.get(nominee.id)

        # Determine seat type (if won)
        seat_type = None
        if nominee in district_winners:
            seat_type = "district"
        elif nominee in at_large_winners:
            seat_type = "at_large"

        all_candidates.append(
            {
                "nominee": nominee,
                "total_votes": total_votes,
                "district_num": district_num,
                "district_votes": (
                    nominee_district_votes[nominee].get(district_num, 0) if district_num else 0
                ),
                "seat_type": seat_type,
            }
        )

    # Sort: district seats (by district number),
    # at-large seats (alphabetically),
    # then losers (alphabetically)
    def sort_key(candidate):
        if candidate["seat_type"] == "district":
            # District winners first, sorted by district number
            return (0, candidate["district_num"] or 999, "")
        elif candidate["seat_type"] == "at_large":
            # At-large winners second, sorted alphabetically
            return (1, 0, candidate["nominee"].get_display_name().lower())
        else:
            # Non-winners last, sorted alphabetically
            return (2, 0, candidate["nominee"].get_display_name().lower())

    all_candidates.sort(key=sort_key)

    # Calculate question results
    question_results = []
    if election_closed:
        # Use stored results
        for question in Question.objects.filter(election=election).order_by("order"):
            yes_count = question.final_yes_votes or 0
            no_count = question.final_no_votes or 0
            question_results.append((question, yes_count, no_count))
    else:
        # Calculate from live votes - use aggregation to get both counts
        # in single query per question
        from django.db.models import Case, IntegerField, Sum, When

        for question in Question.objects.filter(election=election).order_by("order"):
            vote_counts = QuestionVote.objects.filter(question=question).aggregate(
                yes_count=Sum(
                    Case(When(answer=True, then=1), default=0, output_field=IntegerField())
                ),
                no_count=Sum(
                    Case(When(answer=False, then=1), default=0, output_field=IntegerField())
                ),
            )
            yes_count = vote_counts["yes_count"] or 0
            no_count = vote_counts["no_count"] or 0
            question_results.append((question, yes_count, no_count))

    # Get eligible voters - call once and cache
    eligible_voters = election.get_eligible_voters()
    eligible_voters_count = eligible_voters.count()

    # Calculate district-level turnout statistics
    # Count eligible voters by district
    eligible_voters_by_district = Counter()
    for profile in eligible_voters:
        district = profile.district
        if district:
            match = DISTRICT_NUM_REGEX.search(district.name)
            if match:
                district_num = int(match.group())
                eligible_voters_by_district[district_num] += 1
            else:
                eligible_voters_by_district[None] += 1
        else:
            eligible_voters_by_district[None] += 1

    # Count ballots cast by district - use pre-calculated ballot_districts
    ballots_by_district = Counter()
    for ballot in ballots:
        district_num = ballot_districts.get(ballot.id)
        if district_num:
            ballots_by_district[district_num] += 1
        else:
            ballots_by_district[None] += 1

    # Build district turnout list (districts 1-10 plus "No District")
    district_turnout = []
    for district_num in range(1, 11):
        eligible = eligible_voters_by_district.get(district_num, 0)
        ballots_cast = ballots_by_district.get(district_num, 0)
        turnout_rate = (ballots_cast / eligible * 100) if eligible > 0 else None
        district_turnout.append(
            {
                "district_num": district_num,
                "eligible_voters": eligible,
                "ballots_cast": ballots_cast,
                "turnout_rate": turnout_rate,
            }
        )

    # Add "No District" row
    eligible_no_district = eligible_voters_by_district.get(None, 0)
    ballots_no_district = ballots_by_district.get(None, 0)
    turnout_no_district = (
        (ballots_no_district / eligible_no_district * 100) if eligible_no_district > 0 else None
    )
    district_turnout.append(
        {
            "district_num": None,
            "eligible_voters": eligible_no_district,
            "ballots_cast": ballots_no_district,
            "turnout_rate": turnout_no_district,
        }
    )

    return {
        "district_seats": district_seats,
        "at_large_seats": at_large_seats,
        "all_candidates": all_candidates,
        "question_results": question_results,
        "total_ballots": total_ballots,
        "eligible_voters_count": eligible_voters_count,
        "district_turnout": district_turnout,
    }
