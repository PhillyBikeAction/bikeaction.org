# Generated migration for Wagtail campaign models

import django.db.models.deletion
import modelcluster.fields
import wagtail.blocks
import wagtail.fields
import wagtail.images.blocks
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailcore", "0094_alter_page_locale"),
        ("wagtailimages", "0025_alter_image_file_alter_rendition_file"),
        ("campaigns", "0027_petition_active"),
        ("events", "0001_initial"),
        ("membership", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CampaignsIndexPage",
            fields=[
                (
                    "page_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="wagtailcore.page",
                    ),
                ),
            ],
            options={
                "verbose_name": "Campaigns Index",
                "verbose_name_plural": "Campaigns Indexes",
            },
            bases=("wagtailcore.page",),
        ),
        migrations.CreateModel(
            name="CampaignPage",
            fields=[
                (
                    "page_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="wagtailcore.page",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("canceled", "Canceled"),
                            ("suspended", "Suspended"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("visible", models.BooleanField(default=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("call_to_action", models.CharField(blank=True, max_length=64, null=True)),
                ("call_to_action_header", models.BooleanField(default=True)),
                ("donation_action", models.BooleanField(default=False)),
                ("donation_goal", models.IntegerField(blank=True, default=None, null=True)),
                ("donation_goal_show_numbers", models.BooleanField(default=True)),
                ("subscription_action", models.BooleanField(default=False)),
                ("social_shares", models.BooleanField(default=True)),
                (
                    "body",
                    wagtail.fields.StreamField(
                        [
                            ("paragraph", wagtail.blocks.RichTextBlock()),
                            (
                                "petition",
                                wagtail.blocks.StructBlock(
                                    [
                                        (
                                            "petition_id",
                                            wagtail.blocks.CharBlock(
                                                help_text=(
                                                    "UUID of existing petition "
                                                    "or leave blank for new"
                                                ),
                                                max_length=36,
                                                required=False,
                                            ),
                                        ),
                                        ("title", wagtail.blocks.CharBlock(max_length=512)),
                                        (
                                            "letter",
                                            wagtail.blocks.TextBlock(
                                                help_text="Petition letter text", required=False
                                            ),
                                        ),
                                        (
                                            "call_to_action",
                                            wagtail.blocks.CharBlock(
                                                default=(
                                                    "Add your signature to the following message"
                                                ),
                                                max_length=64,
                                                required=False,
                                            ),
                                        ),
                                        (
                                            "call_to_action_header",
                                            wagtail.blocks.BooleanBlock(
                                                default=True, required=False
                                            ),
                                        ),
                                        (
                                            "display_on_campaign_page",
                                            wagtail.blocks.BooleanBlock(
                                                default=True, required=False
                                            ),
                                        ),
                                        (
                                            "signature_goal",
                                            wagtail.blocks.IntegerBlock(
                                                help_text="Target number of signatures",
                                                required=False,
                                            ),
                                        ),
                                        (
                                            "show_submissions",
                                            wagtail.blocks.BooleanBlock(
                                                default=True, required=False
                                            ),
                                        ),
                                        (
                                            "signature_fields",
                                            wagtail.blocks.StructBlock(
                                                [
                                                    (
                                                        "enabled_fields",
                                                        wagtail.blocks.ListBlock(
                                                            wagtail.blocks.ChoiceBlock(
                                                                choices=[
                                                                    ("first_name", "First Name"),
                                                                    ("last_name", "Last Name"),
                                                                    ("email", "E-mail"),
                                                                    (
                                                                        "phone_number",
                                                                        "Phone Number",
                                                                    ),
                                                                    (
                                                                        "postal_address_line_1",
                                                                        "Street Address",
                                                                    ),
                                                                    (
                                                                        "postal_address_line_2",
                                                                        "Address Line 2",
                                                                    ),
                                                                    ("city", "City"),
                                                                    ("state", "State"),
                                                                    ("zip_code", "Zip Code"),
                                                                    ("comment", "Comment"),
                                                                ]
                                                            ),
                                                            help_text=(
                                                                "Select which fields to show "
                                                                "on the petition form"
                                                            ),
                                                        ),
                                                    ),
                                                ],
                                                required=False,
                                            ),
                                        ),
                                        (
                                            "email_settings",
                                            wagtail.blocks.StructBlock(
                                                [
                                                    (
                                                        "send_email",
                                                        wagtail.blocks.BooleanBlock(
                                                            default=False,
                                                            help_text="Send email on signature",
                                                            required=False,
                                                        ),
                                                    ),
                                                    (
                                                        "mailto_send",
                                                        wagtail.blocks.BooleanBlock(
                                                            default=False,
                                                            help_text="Use mailto link instead",
                                                            required=False,
                                                        ),
                                                    ),
                                                    (
                                                        "email_subject",
                                                        wagtail.blocks.CharBlock(
                                                            max_length=988, required=False
                                                        ),
                                                    ),
                                                    (
                                                        "email_body",
                                                        wagtail.blocks.TextBlock(required=False),
                                                    ),
                                                    (
                                                        "email_to",
                                                        wagtail.blocks.TextBlock(
                                                            help_text="One email per line",
                                                            required=False,
                                                        ),
                                                    ),
                                                    (
                                                        "email_cc",
                                                        wagtail.blocks.TextBlock(
                                                            help_text="One email per line",
                                                            required=False,
                                                        ),
                                                    ),
                                                    (
                                                        "email_include_comment",
                                                        wagtail.blocks.BooleanBlock(
                                                            default=False, required=False
                                                        ),
                                                    ),
                                                ],
                                                required=False,
                                            ),
                                        ),
                                        (
                                            "create_account_opt_in",
                                            wagtail.blocks.BooleanBlock(
                                                default=False, required=False
                                            ),
                                        ),
                                        (
                                            "redirect_after",
                                            wagtail.blocks.CharBlock(
                                                help_text="URL to redirect after signing",
                                                required=False,
                                            ),
                                        ),
                                    ]
                                ),
                            ),
                            ("image", wagtail.images.blocks.ImageChooserBlock()),
                            (
                                "html",
                                wagtail.blocks.CharBlock(
                                    template="campaigns/blocks/raw_html.html"
                                ),
                            ),
                        ],
                        blank=True,
                        use_json_field=True,
                    ),
                ),
                ("legacy_campaign_id", models.UUIDField(blank=True, editable=False, null=True)),
                (
                    "cover",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="wagtailimages.image",
                    ),
                ),
                (
                    "donation_product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wagtail_campaigns",
                        to="membership.donationproduct",
                    ),
                ),
            ],
            options={
                "verbose_name": "Campaign",
                "verbose_name_plural": "Campaigns",
            },
            bases=("wagtailcore.page",),
        ),
        migrations.CreateModel(
            name="CampaignEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("sort_order", models.IntegerField(blank=True, editable=False, null=True)),
                (
                    "campaign",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="campaign_events",
                        to="campaigns.campaignpage",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="events.scheduledevent"
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order"],
                "abstract": False,
            },
        ),
    ]
