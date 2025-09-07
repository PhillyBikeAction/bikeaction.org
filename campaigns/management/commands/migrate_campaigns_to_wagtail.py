from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.contrib.redirects.models import Redirect
from wagtail.images.models import Image
from wagtail.models import Page

from campaigns.models import Campaign
from campaigns.wagtail_models import CampaignEvent, CampaignPage, CampaignsIndexPage


class Command(BaseCommand):
    help = "Migrate existing campaigns and petitions to Wagtail"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the migration without saving to database",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be saved"))

        with transaction.atomic():
            # Get or create campaigns index page
            index_page = self.get_or_create_index_page()

            # Migrate each campaign
            campaigns = Campaign.objects.all()
            self.stdout.write(f"Found {campaigns.count()} campaigns to migrate")

            for campaign in campaigns:
                self.migrate_campaign(campaign, index_page)

            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN COMPLETE - Rolling back changes"))
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS("Migration completed successfully"))

    def get_or_create_index_page(self):
        """Get or create the campaigns index page"""
        # Try to find existing campaigns index
        index_pages = CampaignsIndexPage.objects.all()
        if index_pages.exists():
            return index_pages.first()

        # Find the HomePage to add campaigns under
        from cms.models import HomePage

        home_pages = HomePage.objects.all()
        if not home_pages.exists():
            # If no home page, use root as fallback
            parent_page = Page.objects.get(id=1)
            self.stdout.write(self.style.WARNING("No HomePage found, using root page"))
        else:
            parent_page = home_pages.first()
            self.stdout.write(f"Using HomePage: {parent_page.title}")

        # Create new index page
        index_page = CampaignsIndexPage(
            title="Campaigns",
            slug="campaigns",
            show_in_menus=True,
        )
        parent_page.add_child(instance=index_page)

        self.stdout.write(self.style.SUCCESS("Created campaigns index page"))
        return index_page

    def migrate_campaign(self, campaign, parent_page):
        """Migrate a single campaign to Wagtail"""
        self.stdout.write(f"Migrating campaign: {campaign.title}")

        # Check if already migrated
        existing = CampaignPage.objects.filter(legacy_campaign_id=campaign.id).first()
        if existing:
            self.stdout.write(f"  Campaign already migrated: {campaign.title}")
            return existing

        # Create campaign page
        campaign_page = CampaignPage(
            title=campaign.title,
            slug=campaign.slug,
            status=campaign.status,
            visible=campaign.visible,
            description=campaign.description,
            call_to_action=campaign.call_to_action,
            call_to_action_header=campaign.call_to_action_header,
            donation_action=campaign.donation_action,
            donation_product=campaign.donation_product,
            donation_goal=campaign.donation_goal,
            donation_goal_show_numbers=campaign.donation_goal_show_numbers,
            subscription_action=campaign.subscription_action,
            social_shares=campaign.social_shares,
            legacy_campaign_id=campaign.id,
        )

        # Convert markdown content to StreamField
        body_content = []

        # Add main content as raw HTML to avoid parsing issues with malformed HTML
        if campaign.content_rendered:
            # Use html block type for raw HTML content
            body_content.append(
                {
                    "type": "html",
                    "value": campaign.content_rendered,  # Using pre-rendered HTML
                }
            )

        # Add petitions as blocks
        for petition in campaign.petitions.all():
            self.stdout.write(f"  Adding petition: {petition.title}")
            body_content.append(
                {
                    "type": "petition",
                    "value": {
                        "petition": str(petition.id),  # Store as string for JSON
                        "override_display": False,
                        "display_on_campaign_page": petition.display_on_campaign_page,
                    },
                }
            )

        # Set the body StreamField
        campaign_page.body = body_content

        # Handle cover image
        if campaign.cover:
            # Try to find or create Wagtail image
            wagtail_image = self.get_or_create_wagtail_image(campaign.cover)
            if wagtail_image:
                campaign_page.cover = wagtail_image

        # Add as child of index page
        parent_page.add_child(instance=campaign_page)

        # Add events
        for event in campaign.events.all():
            CampaignEvent.objects.create(campaign=campaign_page, event=event)

        # Create redirect from old URL
        old_path = f"/campaigns/{campaign.slug}/"
        Redirect.objects.get_or_create(
            old_path=old_path, defaults={"redirect_page": campaign_page}
        )

        self.stdout.write(self.style.SUCCESS(f"  Migrated campaign: {campaign.title}"))
        return campaign_page

    def get_or_create_wagtail_image(self, django_image_field):
        """Convert Django ImageField to Wagtail Image"""
        if not django_image_field:
            return None

        try:
            # Check if image already exists in Wagtail
            wagtail_images = Image.objects.filter(title=django_image_field.name)
            if wagtail_images.exists():
                return wagtail_images.first()

            # Create new Wagtail image
            wagtail_image = Image(
                title=django_image_field.name,
                file=django_image_field.file,
            )
            wagtail_image.save()
            return wagtail_image
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Could not migrate image: {e}"))
            return None
