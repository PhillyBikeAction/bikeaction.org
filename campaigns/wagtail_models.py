from django.contrib.gis.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.blocks import (
    BooleanBlock,
    CharBlock,
    ChoiceBlock,
    ListBlock,
    RawHTMLBlock,
    RichTextBlock,
    StructBlock,
    TextBlock,
)
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageBlock
from wagtail.models import Orderable, Page
from wagtail.snippets.models import register_snippet

# Register the existing Petition model directly as a Wagtail snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from campaigns.models import Petition
from events.models import ScheduledEvent
from membership.models import DonationProduct


class PetitionViewSet(SnippetViewSet):
    model = Petition
    icon = "form"
    list_display = ["title", "active", "display_on_campaign_page", "signature_goal"]
    list_filter = ["active", "display_on_campaign_page"]
    search_fields = ["title", "letter"]


register_snippet(Petition, viewset=PetitionViewSet)


class PetitionChooserBlock(ChoiceBlock):
    """Simple chooser block for Petition that works with UUID primary keys"""

    def __init__(self, **kwargs):
        # Don't pass choices to parent __init__, we'll set them dynamically
        self._kwargs = kwargs.copy()
        if "choices" in self._kwargs:
            del self._kwargs["choices"]
        super().__init__(**self._kwargs)

    @property
    def choices(self):
        """Dynamically generate choices from active petitions"""
        from campaigns.models import Petition

        return [
            (str(p.id), f"{p.title}" + (" (inactive)" if not p.active else ""))
            for p in Petition.objects.all().order_by("-active", "title")
        ]

    @choices.setter
    def choices(self, value):
        """Allow choices to be set (required by parent class)"""
        pass

    def to_python(self, value):
        """Convert stored UUID string to Petition instance"""
        from campaigns.models import Petition

        if not value:
            return None

        if isinstance(value, Petition):
            return value

        # Load petition by UUID string
        try:
            return Petition.objects.get(id=value)
        except (Petition.DoesNotExist, ValueError):
            return None

    def get_prep_value(self, value):
        """Convert petition to UUID string for storage"""
        from campaigns.models import Petition

        if value is None:
            return None

        if isinstance(value, Petition):
            return str(value.id)

        # Already a string UUID
        return str(value)

    def value_from_datadict(self, data, files, prefix):
        """Get value from form submission"""
        value = super().value_from_datadict(data, files, prefix)
        # The form will return the UUID string, convert to Petition instance
        return self.to_python(value)

    def value_for_form(self, value):
        """Convert value for form display"""
        # Return the UUID string for the form
        return self.get_prep_value(value)

    class Meta:
        icon = "form"


class PetitionFieldsBlock(StructBlock):
    """Configuration for petition form fields"""

    FIELD_CHOICES = [
        ("first_name", "First Name"),
        ("last_name", "Last Name"),
        ("email", "E-mail"),
        ("phone_number", "Phone Number"),
        ("postal_address_line_1", "Street Address"),
        ("postal_address_line_2", "Address Line 2"),
        ("city", "City"),
        ("state", "State"),
        ("zip_code", "Zip Code"),
        ("comment", "Comment"),
    ]

    enabled_fields = ListBlock(
        ChoiceBlock(choices=FIELD_CHOICES),
        help_text="Select which fields to show on the petition form",
    )


class PetitionEmailSettingsBlock(StructBlock):
    """Email configuration for petitions"""

    send_email = BooleanBlock(default=False, required=False, help_text="Send email on signature")
    mailto_send = BooleanBlock(default=False, required=False, help_text="Use mailto link instead")
    email_subject = CharBlock(max_length=988, required=False)
    email_body = TextBlock(required=False)
    email_to = TextBlock(required=False, help_text="One email per line")
    email_cc = TextBlock(required=False, help_text="One email per line")
    email_include_comment = BooleanBlock(default=False, required=False)


class PetitionBlock(StructBlock):
    """Petition block for StreamField using Wagtail snippets"""

    petition = PetitionChooserBlock(required=True, help_text="Select a petition to display")

    # Override display settings
    override_display = BooleanBlock(
        default=False,
        required=False,
        help_text="Override the petition's display settings for this campaign",
    )
    display_on_campaign_page = BooleanBlock(
        default=True,
        required=False,
        help_text="Display this petition on the campaign page (only used if override is checked)",
    )

    def bulk_to_python(self, values):
        """Override to properly load petition instances from UUIDs"""
        # First call parent to get the base conversion
        results = super().bulk_to_python(values)

        # Now ensure petition is loaded for each result
        from campaigns.models import Petition

        for result in results:
            if result and "petition" in result:
                petition_value = result.get("petition")
                # If it's a string UUID, load the actual petition
                if isinstance(petition_value, str):
                    try:
                        petition = Petition.objects.get(id=petition_value)
                        result["petition"] = petition
                    except (Petition.DoesNotExist, ValueError):
                        pass

        return results

    def get_context(self, value, parent_context=None):
        """Add context for rendering, especially for previews"""
        import uuid

        from campaigns.models import Petition

        context = super().get_context(value, parent_context)

        # Ensure petition is loaded if we have a value
        if value and "petition" in value:
            petition = value.get("petition")
            # If it's not a Petition instance, try to load it
            if not isinstance(petition, Petition):
                if isinstance(petition, (str, uuid.UUID)):
                    loaded_petition = Petition.objects.filter(id=str(petition)).first()
                    if loaded_petition:
                        # Update the value with the loaded petition
                        value["petition"] = loaded_petition
                        context["value"] = value

        # Pass the page context for preview
        if parent_context:
            context["page"] = parent_context.get("page")
            context["request"] = parent_context.get("request")

        return context

    def render(self, value, context=None):
        """Custom render that ensures petition is loaded"""
        import uuid

        from campaigns.models import Petition

        # Ensure petition is loaded
        if value and "petition" in value:
            petition = value.get("petition")
            if not isinstance(petition, Petition):
                if isinstance(petition, (str, uuid.UUID)):
                    loaded_petition = Petition.objects.filter(id=str(petition)).first()
                    if loaded_petition:
                        # Create a mutable copy of value
                        from copy import deepcopy

                        value = deepcopy(value)
                        value["petition"] = loaded_petition

        # Always use parent's render which will use the template specified in Meta
        return super().render(value, context)

    class Meta:
        template = "campaigns/blocks/petition_simple.html"
        icon = "form"
        label = "Petition Form"


# Removed CampaignStreamBlock class - no longer needed with simplified approach


class CampaignPage(RoutablePageMixin, Page):
    """Wagtail page model for campaigns"""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"
        SUSPENDED = "suspended", "Suspended"

    # Core fields from original Campaign model
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    visible = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)

    # Call to action
    call_to_action = models.CharField(max_length=64, null=True, blank=True)
    call_to_action_header = models.BooleanField(default=True)

    # Donation settings
    donation_action = models.BooleanField(default=False)
    donation_product = models.ForeignKey(
        DonationProduct,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="wagtail_campaigns",
    )
    donation_goal = models.IntegerField(default=None, null=True, blank=True)
    donation_goal_show_numbers = models.BooleanField(default=True)

    # Other actions
    subscription_action = models.BooleanField(default=False)
    social_shares = models.BooleanField(default=True)

    # Content - using StreamField for flexibility
    body = StreamField(
        [
            ("paragraph", RichTextBlock()),
            ("petition", PetitionBlock()),
            ("image", ImageBlock()),
            ("html", RawHTMLBlock()),  # Use RawHTMLBlock for raw HTML content
        ],
        use_json_field=True,
        blank=True,
    )

    # Cover image
    cover = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Legacy ID for migration
    legacy_campaign_id = models.UUIDField(null=True, blank=True, editable=False)

    # Page hierarchy restrictions
    parent_page_types = [
        "campaigns.CampaignsIndexPage"
    ]  # Can only be created under CampaignsIndexPage
    subpage_types = []  # Cannot have any child pages

    # Admin panels
    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("status"),
                FieldPanel("visible"),
                FieldPanel("description"),
            ],
            heading="Campaign Settings",
        ),
        FieldPanel("cover"),
        MultiFieldPanel(
            [
                FieldPanel("call_to_action"),
                FieldPanel("call_to_action_header"),
            ],
            heading="Call to Action",
        ),
        MultiFieldPanel(
            [
                FieldPanel("donation_action"),
                FieldPanel("donation_product"),
                FieldPanel("donation_goal"),
                FieldPanel("donation_goal_show_numbers"),
            ],
            heading="Donation Settings",
        ),
        MultiFieldPanel(
            [
                FieldPanel("subscription_action"),
                FieldPanel("social_shares"),
            ],
            heading="Other Actions",
        ),
        FieldPanel("body"),
        InlinePanel("campaign_events", label="Events"),
    ]

    @property
    def has_actions(self):
        """Check if campaign has any actions"""
        has_petitions = any(block.block_type == "petition" for block in self.body)
        return (
            has_petitions
            or self.campaign_events.count()
            or self.donation_action
            or self.subscription_action
        )

    @property
    def donation_total(self):
        """Calculate total donations"""
        if self.donation_product:
            from membership.models import Donation

            return Donation.objects.filter(donation_product=self.donation_product).aggregate(
                models.Sum("amount", default=0)
            )["amount__sum"]
        return None

    @property
    def donation_progress(self):
        """Calculate donation progress percentage"""
        if self.donation_goal and self.donation_total:
            if self.donation_total > self.donation_goal:
                return 100
            return int(100 * (self.donation_total / self.donation_goal))
        return 100 if self.donation_goal else 0

    def future_events(self):
        """Get future events for this campaign"""
        from django.utils import timezone

        return self.campaign_events.filter(
            event__start_datetime__gt=timezone.now()
        ).select_related("event")

    @path("petition/<slug:petition_id>/sign/", name="sign_petition")
    def sign_petition_route(self, request, petition_id):
        """Handle petition signature submission"""
        from campaigns.wagtail_views import sign_petition_wagtail

        return sign_petition_wagtail(request, self, petition_id)

    @path("petition/<slug:petition_id>/_signatures/", name="petition_signatures")
    def petition_signatures_route(self, request, petition_id):
        """Get petition signatures for HTMX updates"""
        from campaigns.wagtail_views import petition_signatures_wagtail

        return petition_signatures_wagtail(request, self, petition_id)

    def get_status_display_formatted(self):
        """Get formatted status display with color for admin"""
        from django.utils.html import format_html

        status_colors = {
            "draft": "#999",
            "active": "#28a745",
            "completed": "#007bff",
            "canceled": "#dc3545",
            "suspended": "#ffc107",
        }

        color = status_colors.get(self.status, "#000")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            self.get_status_display(),
        )

    class Meta:
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"


class CampaignEvent(Orderable):
    """Through model for Campaign-Event relationship"""

    campaign = ParentalKey(CampaignPage, on_delete=models.CASCADE, related_name="campaign_events")
    event = models.ForeignKey(ScheduledEvent, on_delete=models.CASCADE)

    panels = [
        FieldPanel("event"),
    ]


class CampaignsIndexPage(Page):
    """Index page for listing all campaigns"""

    # Page hierarchy restrictions
    parent_page_types = ["cms.HomePage"]  # Can only be created under HomePage
    subpage_types = ["campaigns.CampaignPage"]  # Can only have CampaignPage children
    max_count = 1  # Only one campaigns index page should exist

    def get_children(self):
        """Override to return campaigns ordered by status then default page tree order"""
        # Get the default children queryset which already has page tree ordering
        children = super().get_children()
        # Add status ordering first, keeping the default page tree order as secondary
        return children.type(CampaignPage).order_by("campaignpage__status")

    def get_context(self, request):
        context = super().get_context(request)
        campaigns = CampaignPage.objects.live().descendant_of(self)

        # Filter by status if needed
        status_filter = request.GET.get("status")
        if status_filter:
            campaigns = campaigns.filter(status=status_filter)

        # Only show visible campaigns
        campaigns = campaigns.filter(visible=True)

        context["campaigns"] = campaigns.order_by("-first_published_at")
        return context

    class Meta:
        verbose_name = "Campaigns Index"
        verbose_name_plural = "Campaigns Indexes"

    # Admin panels
    content_panels = Page.content_panels
