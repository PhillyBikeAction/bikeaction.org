import html
import logging
import re

from asgiref.sync import async_to_sync, sync_to_async
from celery import shared_task
from django.conf import settings
from django.urls import reverse
from interactions.models.discord.enums import AutoArchiveDuration

from pba_discord.bot import bot
from projects.models import ProjectApplication

logger = logging.getLogger(__name__)

REIMBURSEMENT_FORM_URL = "https://forms.gle/tex8Pm7j1dSad6Xu9"
DISCORD_MESSAGE_CHARACTER_LIMIT = 1990
DISCORD_BROADCAST_MENTION_RE = re.compile(r"@(?=everyone\b|here\b)")
DISCORD_TAG_MENTION_RE = re.compile(r"<(@[!&]?\d+|#\d+)>")
ZERO_WIDTH_SPACE = "\u200b"


def get_project_lead_cheat_sheet_link_text():
    if not settings.PROJECT_LEAD_CHEAT_SHEET_URL:
        return None
    return f"[Project Lead Cheat Sheet](<{settings.PROJECT_LEAD_CHEAT_SHEET_URL}>)"


def get_project_lead_cheat_sheet_sentence():
    link_text = get_project_lead_cheat_sheet_link_text()
    if not link_text:
        return None
    return (
        "ℹ️ For the basics on PBA resources, reimbursements, promotion, events, "
        "volunteer support, and wrapping up your project, read the "
        f"{link_text}."
    )


def build_project_approved_channel_message(
    guild_id,
    application_thread_id,
    project_lead_mention,
    mentor_mention=None,
):
    msg = (
        "✅ This project has been approved!\n\n"
        "Project Application: "
        f"https://discord.com/channels/{guild_id}/{application_thread_id}\n\n"
        f"Project Lead: {project_lead_mention}.\n\n"
        f"Need to be reimbursed for an approved project expense? Fill out this form: {REIMBURSEMENT_FORM_URL}\n\n"
    )
    cheat_sheet_sentence = get_project_lead_cheat_sheet_sentence()
    if cheat_sheet_sentence:
        msg += f"\n\n{cheat_sheet_sentence}"
    if mentor_mention:
        msg += (
            f" {mentor_mention} has volunteered to support this project by answering any questions."
        )
    return msg


def build_project_lead_cheat_sheet_dm_message(
    project_name,
    mentor_mention=None,
):
    msg = f'✅ Your project "{project_name}" has been approved!'
    cheat_sheet_sentence = get_project_lead_cheat_sheet_sentence()
    if cheat_sheet_sentence:
        msg += f"\n\n{cheat_sheet_sentence}"
    if mentor_mention:
        msg += (
            f"\n\n{mentor_mention} has volunteered to support this project "
            "by answering any questions."
        )
    return msg


def neutralize_discord_mentions(text):
    def replace_tag(match):
        value = match.group(1)
        if value.startswith("@"):
            value = value.replace("@", f"@{ZERO_WIDTH_SPACE}", 1)
        elif value.startswith("#"):
            value = value.replace("#", f"#{ZERO_WIDTH_SPACE}", 1)
        return f"<{value}>"

    text = DISCORD_TAG_MENTION_RE.sub(replace_tag, text)
    return DISCORD_BROADCAST_MENTION_RE.sub(f"@{ZERO_WIDTH_SPACE}", text)


def format_project_application_discord_line(line):
    return neutralize_discord_mentions(html.unescape(line))


def format_project_application_discord_messages(markdown):
    messages = []
    msg = ""
    in_response = False
    for line in markdown.split("\n"):
        line = format_project_application_discord_line(line)
        if line == "```":
            if in_response:
                in_response = False
            else:
                in_response = True
        if len(msg) + len(line) >= DISCORD_MESSAGE_CHARACTER_LIMIT:
            if in_response:
                msg += "```\n"
            messages.append(msg)
            msg = ""
            if in_response:
                msg += "```\n"
        msg += line + "\n"
    messages.append(msg)
    return messages


def build_project_archive_message(guild_id, archived_by, board_role_mention):
    return (
        f"This project has been marked complete by {archived_by}, "
        "and archived.\n\n"
        f"{board_role_mention} please update the project information in "
        f"https://discord.com/channels/{guild_id}/{settings.PROJECT_LOG_CHANNEL_ID}, "
        "leave a :white_check_mark: when complete."
    )


def get_project_archive_mention_role_id():
    return settings.BOARD_ROLE_ID or settings.NEW_PROJECT_REVIEW_DISCORD_ROLE_MENTION_ID


async def _add_new_project_message_and_thread(project_application_id):
    application = await ProjectApplication.objects.filter(id=project_application_id).afirst()
    if application is None or application.draft or application.thread_id:
        return

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.DISCORD_GUILD_ID)
    channel = await guild.fetch_channel(settings.NEW_PROJECT_REVIEW_DISCORD_CHANNEL_ID)
    mention_role = await guild.fetch_role(settings.NEW_PROJECT_REVIEW_DISCORD_ROLE_MENTION_ID)
    submitter = await sync_to_async(lambda: application.submitter)()
    profile = await sync_to_async(lambda: submitter.profile)()
    discord = await sync_to_async(lambda: profile.discord)()
    discord_username = discord.extra_data["username"]
    thread = await channel.create_thread(
        name=f"{application.data['shortname']['value']}",
        reason=f"Project Application submitted by {discord_username}",
        auto_archive_duration=AutoArchiveDuration.ONE_WEEK,
    )
    if not application.markdown:
        await sync_to_async(application.render_markdown)()
    for msg in format_project_application_discord_messages(application.markdown):
        await thread.send(msg)
    link = reverse("project_application_view", kwargs={"pk": application.id})
    link = f"https://apps.bikeaction.org{link}"
    await thread.send(
        f"{mention_role.mention} please review!\n\n"
        f"You can view the application online [here](<{link}>) after logging in.\n\n"
        "When the project is ready for board review, use the `/project vote` command"
    )
    application.thread_id = thread.id
    await application.asave()


async def _add_new_project_voting_message_and_thread(project_application_id):
    application = await ProjectApplication.objects.filter(id=project_application_id).afirst()
    if application is None or application.approved or application.voting_thread_id:
        return

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.DISCORD_GUILD_ID)
    discussion_thread = await guild.fetch_channel(application.thread_id)
    channel = await guild.fetch_channel(settings.NEW_PROJECT_REVIEW_DISCORD_VOTE_CHANNEL_ID)
    mention_role = await guild.fetch_role(settings.NEW_PROJECT_REVIEW_DISCORD_ROLE_VOTE_MENTION_ID)
    submitter = await sync_to_async(lambda: application.submitter)()
    profile = await sync_to_async(lambda: submitter.profile)()
    discord = await sync_to_async(lambda: profile.discord)()
    discord_username = discord.extra_data["username"]
    thread = await channel.create_thread(
        name=f"Vote: Project - {application.data['shortname']['value']}",
        reason=f"Project Application by {discord_username}",
        auto_archive_duration=AutoArchiveDuration.ONE_WEEK,
    )
    link = reverse("project_application_view", kwargs={"pk": application.id})
    link = f"https://apps.bikeaction.org{link}"
    await thread.send(
        f'Project application "{application.data["shortname"]["value"]}" '
        f"from {discord_username} has been submitted for vote by {application.vote_initiator}\n\n"
        f"{mention_role.mention} please review and vote with :white_check_mark: or :x:.\n\n"
        f"See discussion at https://discord.com/channels/{guild.id}/{discussion_thread.id}\n\n"
        f"You can view the application online [here](<{link}>) after logging in.\n\n"
        "If the vote passes, the `/project approve` command can be used to "
        "optionally create a discord channel and/or assign a mentor, "
        f"and assign the project lead role to {discord_username}."
    )
    await discussion_thread.send(
        f"Project application has been submitted for vote by {application.vote_initiator}!"
    )
    application.voting_thread_id = thread.id
    await application.asave()


async def _approve_new_project(
    project_application_id,
    project_channel_name,
    project_mentor_id,
    project_lead_id,
):
    application = await ProjectApplication.objects.filter(id=project_application_id).afirst()

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.DISCORD_GUILD_ID)
    discussion_thread = await guild.fetch_channel(application.thread_id)
    voting_thread = await guild.fetch_channel(application.voting_thread_id)
    messages = await voting_thread.history(limit=0).flatten()
    for reaction in messages[-1].reactions:
        if reaction.emoji.name == "✅":
            users = await reaction.users().flatten()
            application.yay_votes = [u.id for u in users]
        if reaction.emoji.name == "❌":
            users = await reaction.users().flatten()
            application.nay_votes = [u.id for u in users]

    actions = []
    project_name = application.data["shortname"]["value"]
    project_lead = await guild.fetch_member(project_lead_id)
    mentor = None
    mentor_mention = None
    if project_mentor_id is not None:
        mentor = await guild.fetch_member(project_mentor_id)
        mentor_mention = mentor.mention

    if project_channel_name is not None:
        channel = await guild.create_text_channel(
            project_channel_name, category=settings.ACTIVE_PROJECT_CATEGORY_ID
        )
        application.channel_id = channel.id
        actions.append(f"Created channel https://discord.com/channels/{guild.id}/{channel.id}")

        msg = build_project_approved_channel_message(
            guild.id,
            application.thread_id,
            project_lead.mention,
            mentor_mention,
        )
        message = await channel.send(msg)
        try:
            await message.pin()
        except Exception:
            logger.exception(
                "Failed to pin approval message for project application %s",
                application.id,
            )
            actions.append("Could not pin approval message; please pin it manually")

    if project_mentor_id is not None:
        application.mentor_id = project_mentor_id
        actions.append(f"Assigned Mentor {mentor.mention}")

    role = await guild.fetch_role(settings.ACTIVE_PROJECT_LEAD_ROLE_ID)
    application.project_lead_id = project_lead.id
    await project_lead.add_role(role)
    actions.append(f"Assigned {role.name} role to {project_lead.mention}")

    if project_channel_name is None:
        try:
            await project_lead.send(
                build_project_lead_cheat_sheet_dm_message(
                    project_name,
                    mentor_mention,
                )
            )
            actions.append(f"Sent Project Lead Cheat Sheet to {project_lead.mention}")
        except Exception:
            logger.exception(
                "Failed to DM Project Lead Cheat Sheet for project application %s",
                application.id,
            )
            actions.append(
                "Could not DM Project Lead Cheat Sheet to "
                f"{project_lead.mention}; please send it manually"
            )

    msg = f'Project "{project_name}" Approved!'
    if actions:
        msg += "\n\nActions Taken:\n"
    for action in actions:
        msg += f"- {action}\n"

    await discussion_thread.send(msg)

    msg = f'Project "{project_name}" Approved by {application.approved_by}.'
    if actions:
        msg += "\n\nActions Taken:\n"
    for action in actions:
        msg += f"- {action}\n"

    if settings.PROJECT_LOG_CHANNEL_ID:
        msg += (
            "\nSomeone must add the project to the project log in "
            f"https://discord.com/channels/{guild.id}/{settings.PROJECT_LOG_CHANNEL_ID}, "
            "leave a :white_check_mark: when complete."
        )
    await voting_thread.send(msg)

    await application.asave()


async def _archive_project(project_application_id):
    application = await ProjectApplication.objects.filter(id=project_application_id).afirst()

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.DISCORD_GUILD_ID)

    channel = None
    if application.channel_id:
        channel = await guild.fetch_channel(application.channel_id)
        archive_mention_role_id = get_project_archive_mention_role_id()
        archive_mention_role = await guild.fetch_role(archive_mention_role_id)
        await channel.send(
            build_project_archive_message(
                guild.id,
                application.archived_by,
                archive_mention_role.mention,
            )
        )
        await bot.http.move_channel(
            guild_id=guild.id,
            channel_id=channel.id,
            new_pos=0,
            parent_id=settings.ARCHIVED_PROJECT_CATEGORY_ID,
            lock_perms=True,
            reason=f"Project marked as complete by {application.archived_by}",
        )


@shared_task
def add_new_project_message_and_thread(project_application_id):
    async_to_sync(_add_new_project_message_and_thread)(project_application_id)


@shared_task
def add_new_project_voting_message_and_thread(project_application_id):
    async_to_sync(_add_new_project_voting_message_and_thread)(project_application_id)


@shared_task
def approve_new_project(
    project_application_id,
    project_channel_name,
    project_mentor_id,
    project_lead_id,
):
    async_to_sync(_approve_new_project)(
        project_application_id,
        project_channel_name,
        project_mentor_id,
        project_lead_id,
    )


@shared_task
def archive_project(project_application_id):
    async_to_sync(_archive_project)(project_application_id)
