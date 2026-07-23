from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from organizers.forms import OrganizerApplicationForm
from organizers.models import OrganizerApplication
from profiles.models import Profile
from projects.forms import ProjectApplicationForm
from projects.models import ProjectApplication
from projects.tasks import (
    build_project_archive_message,
    build_project_approved_channel_message,
    build_project_lead_cheat_sheet_dm_message,
    format_project_application_discord_messages,
    get_project_archive_mention_role_id,
)


class ProjectApplicationDiscordMarkdownTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="projectuser",
            email="project@example.com",
            password="password",
            first_name="Project",
            last_name="User",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            street_address="123 Market St",
            zip_code="19107",
        )
        SocialAccount.objects.create(
            user=self.user,
            provider="discord",
            uid="discord-projectuser",
            extra_data={"username": "projectuser"},
        )

    def project_data(self):
        form = ProjectApplicationForm()
        data = {
            field.name: {"label": field.label, "value": f"{field.name} value"} for field in form
        }
        data["shortname"]["value"] = "Project Details"
        data["quick_summary"]["value"] = "Indego & SEPTA coordination <@123>"
        return data

    def test_discord_messages_decode_ampersands_after_markdown_rendering_only(self):
        application = ProjectApplication(
            submitter=self.user,
            data=self.project_data(),
        )

        application.render_markdown()
        messages = format_project_application_discord_messages(application.markdown)
        message = "".join(messages)

        self.assertIn("Indego &amp; SEPTA coordination", application.markdown)
        self.assertIn("&lt;@123&gt;", application.markdown)
        self.assertIn("Indego & SEPTA coordination", message)
        self.assertNotIn("Indego &amp; SEPTA coordination", message)
        self.assertIn("&lt;@123&gt;", message)


class ProjectApprovalMessageTests(SimpleTestCase):
    @override_settings(PROJECT_LEAD_CHEAT_SHEET_URL="https://example.com/cheat-sheet")
    def test_approved_channel_message_includes_project_lead_cheat_sheet(self):
        message = build_project_approved_channel_message(
            guild_id="guild-123",
            application_thread_id="thread-456",
            project_lead_mention="<@789>",
        )

        self.assertIn("✅ This project has been approved!", message)
        self.assertIn("https://discord.com/channels/guild-123/thread-456", message)
        self.assertIn("Project Lead: <@789>.", message)
        self.assertIn(
            "Need to be reimbursed for an approved project expense? Fill out this form: https://forms.gle/tex8Pm7j1dSad6Xu9",
            message,
        )
        self.assertIn(
            "ℹ️ For the basics on PBA resources, reimbursements, promotion, events, "
            "volunteer support, and wrapping up your project, read the "
            "[Project Lead Cheat Sheet](<https://example.com/cheat-sheet>).",
            message,
        )

    @override_settings(PROJECT_LEAD_CHEAT_SHEET_URL="https://example.com/cheat-sheet")
    def test_approved_channel_message_includes_project_mentor_when_present(self):
        message = build_project_approved_channel_message(
            guild_id="guild-123",
            application_thread_id="thread-456",
            project_lead_mention="<@789>",
            mentor_mention="<@101>",
        )

        self.assertIn(
            "<@101> has volunteered to support this project by answering any questions.",
            message,
        )

    @override_settings(PROJECT_LEAD_CHEAT_SHEET_URL=None)
    def test_approved_channel_message_omits_cheat_sheet_when_url_is_not_configured(self):
        message = build_project_approved_channel_message(
            guild_id="guild-123",
            application_thread_id="thread-456",
            project_lead_mention="<@789>",
        )

        self.assertIn("✅ This project has been approved!", message)
        self.assertIn("Project Lead: <@789>.", message)
        self.assertIn(
            "Need to be reimbursed for an approved project expense? Fill out this form: https://forms.gle/tex8Pm7j1dSad6Xu9",
            message,
        )
        self.assertNotIn("Project Lead Cheat Sheet", message)
        self.assertNotIn("For the basics on PBA resources", message)

    @override_settings(PROJECT_LEAD_CHEAT_SHEET_URL="https://example.com/cheat-sheet")
    def test_project_lead_dm_message_includes_cheat_sheet(self):
        message = build_project_lead_cheat_sheet_dm_message(
            project_name="Better Bike Lanes",
        )

        self.assertIn('✅ Your project "Better Bike Lanes" has been approved!', message)
        self.assertNotIn("discord.com/channels", message)
        self.assertIn(
            "ℹ️ For the basics on PBA resources, reimbursements, promotion, events, "
            "volunteer support, and wrapping up your project, read the "
            "[Project Lead Cheat Sheet](<https://example.com/cheat-sheet>).",
            message,
        )

    @override_settings(PROJECT_LEAD_CHEAT_SHEET_URL=None)
    def test_project_lead_dm_message_omits_cheat_sheet_when_url_is_not_configured(self):
        message = build_project_lead_cheat_sheet_dm_message(
            project_name="Better Bike Lanes",
        )

        self.assertIn('✅ Your project "Better Bike Lanes" has been approved!', message)
        self.assertNotIn("Project Lead Cheat Sheet", message)
        self.assertNotIn("For the basics on PBA resources", message)

    @override_settings(PROJECT_LEAD_CHEAT_SHEET_URL="https://example.com/cheat-sheet")
    def test_project_lead_dm_message_includes_project_mentor_when_present(self):
        message = build_project_lead_cheat_sheet_dm_message(
            project_name="Better Bike Lanes",
            mentor_mention="<@101>",
        )

        self.assertIn(
            "<@101> has volunteered to support this project by answering any questions.",
            message,
        )


class ProjectArchiveMessageTests(SimpleTestCase):
    @override_settings(BOARD_ROLE_ID="board-role-123")
    def test_archive_mention_role_prefers_board_role_id(self):
        self.assertEqual(get_project_archive_mention_role_id(), "board-role-123")

    @override_settings(
        BOARD_ROLE_ID=None,
        NEW_PROJECT_REVIEW_DISCORD_ROLE_MENTION_ID="project-review-role-123",
    )
    def test_archive_mention_role_falls_back_to_project_review_role(self):
        self.assertEqual(get_project_archive_mention_role_id(), "project-review-role-123")

    @override_settings(PROJECT_LOG_CHANNEL_ID="project-log-123")
    def test_archive_message_mentions_board_role(self):
        message = build_project_archive_message(
            guild_id="guild-123",
            archived_by="Archive User",
            board_role_mention="<@&board-role-456>",
        )

        self.assertIn("This project has been marked complete by Archive User", message)
        self.assertIn(
            "<@&board-role-456> please update the project information",
            message,
        )
        self.assertIn(
            "https://discord.com/channels/guild-123/project-log-123",
            message,
        )


class DraftApplicationProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="draftuser",
            email="draft@example.com",
            password="password",
            first_name="Draft",
            last_name="User",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            street_address="123 Market St",
            zip_code="19107",
        )
        SocialAccount.objects.create(
            user=self.user,
            provider="discord",
            uid="discord-draftuser",
            extra_data={"username": "draftuser"},
        )
        self.client.force_login(self.user)

    def project_data(self, shortname="Project Draft"):
        form = ProjectApplicationForm()
        data = {
            field.name: {"label": field.label, "value": f"{field.name} value"} for field in form
        }
        data["shortname"]["value"] = shortname
        data["quick_summary"]["value"] = "A draft project summary"
        return data

    def organizer_data(self):
        form = OrganizerApplicationForm()
        return {
            field.name: {"label": field.label, "value": f"{field.name} value"} for field in form
        }

    def test_profile_links_project_and_organizer_drafts_to_their_own_forms(self):
        project_draft = ProjectApplication.objects.create(
            submitter=self.user,
            draft=True,
            data=self.project_data(),
        )
        organizer_draft = OrganizerApplication.objects.create(
            submitter=self.user,
            draft=True,
            data=self.organizer_data(),
        )

        response = self.client.get(reverse("profile"))

        self.assertContains(response, "Project Application Drafts")
        self.assertContains(response, "Organizer Application Drafts")
        self.assertContains(
            response,
            reverse("project_application_edit", kwargs={"pk": project_draft.id}),
        )
        self.assertContains(
            response,
            reverse("organizer_application_edit", kwargs={"pk": organizer_draft.id}),
        )
        self.assertContains(
            response,
            reverse("project_application_delete", kwargs={"pk": project_draft.id}),
        )
        self.assertContains(
            response,
            reverse("organizer_application_delete", kwargs={"pk": organizer_draft.id}),
        )

    def test_project_draft_can_be_deleted_from_profile(self):
        project_draft = ProjectApplication.objects.create(
            submitter=self.user,
            draft=True,
            data=self.project_data(),
        )

        response = self.client.post(
            reverse("project_application_delete", kwargs={"pk": project_draft.id})
        )

        self.assertRedirects(response, reverse("profile"))
        self.assertFalse(ProjectApplication.objects.filter(id=project_draft.id).exists())

    def test_organizer_draft_can_be_deleted_from_profile(self):
        organizer_draft = OrganizerApplication.objects.create(
            submitter=self.user,
            draft=True,
            data=self.organizer_data(),
        )

        response = self.client.post(
            reverse("organizer_application_delete", kwargs={"pk": organizer_draft.id})
        )

        self.assertRedirects(response, reverse("profile"))
        self.assertFalse(OrganizerApplication.objects.filter(id=organizer_draft.id).exists())

    def test_other_users_drafts_cannot_be_deleted(self):
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="password",
        )
        other_draft = ProjectApplication.objects.create(
            submitter=other_user,
            draft=True,
            data=self.project_data("Other Project Draft"),
        )

        response = self.client.post(
            reverse("project_application_delete", kwargs={"pk": other_draft.id})
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProjectApplication.objects.filter(id=other_draft.id).exists())
