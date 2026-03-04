from asgiref.sync import async_to_sync, sync_to_async
from celery import shared_task
from django.conf import settings
from django.urls import reverse
from interactions.models.discord.enums import AutoArchiveDuration

from pba_discord.bot import bot
from projects.models import ProjectApplication


async def _add_new_project_message_and_thread(project_application_id):
    application = await ProjectApplication.objects.filter(id=project_application_id).afirst()
    if application is None or application.draft or application.thread_id:
        return

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.NEW_PROJECT_REVIEW_DISCORD_GUILD_ID)
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
    msg = ""
    in_response = False
    for line in application.markdown.split("\n"):
        if line == "```":
            if in_response:
                in_response = False
            else:
                in_response = True
        if len(msg) + len(line) >= 1990:
            if in_response:
                msg += "```\n"
            await thread.send(msg)
            msg = ""
            if in_response:
                msg += "```\n"
        msg += line + "\n"
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
    guild = await bot.fetch_guild(settings.NEW_PROJECT_REVIEW_DISCORD_GUILD_ID)
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
    guild = await bot.fetch_guild(settings.NEW_PROJECT_REVIEW_DISCORD_GUILD_ID)
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

    if project_channel_name is not None:
        channel = await guild.create_text_channel(
            project_channel_name, category=settings.ACTIVE_PROJECT_CATEGORY_ID
        )
        application.channel_id = channel.id
        actions.append(f"Created channel https://discord.com/channels/{guild.id}/{channel.id}")

        project_lead = await guild.fetch_member(project_lead_id)
        msg = (
            "This project has been approved!\n\n"
            "Project Application: "
            f"https://discord.com/channels/{guild.id}/{application.thread_id}\n\n"
            f"Project Lead is {project_lead.mention}."
        )
        if project_mentor_id:
            mentor = await guild.fetch_member(project_mentor_id)
            msg += (
                f" {mentor.mention} has volunteered to support this project "
                "by answering any questions."
            )
        message = await channel.send(msg)
        await message.pin()

    if project_mentor_id is not None:
        application.mentor_id = project_mentor_id
        mentor = await guild.fetch_member(project_mentor_id)
        actions.append(f"Assigned Mentor {mentor.mention}")

    role = await guild.fetch_role(settings.ACTIVE_PROJECT_LEAD_ROLE_ID)
    project_lead = await guild.fetch_member(project_lead_id)
    application.project_lead_id = project_lead.id
    await project_lead.add_role(role)
    actions.append(f"Assigned {role.name} role to {project_lead.mention}")

    msg = f'Project "{application.data["shortname"]["value"]}" Approved!'
    if actions:
        msg += "\n\nActions Taken:\n"
    for action in actions:
        msg += f"- {action}\n"

    await discussion_thread.send(msg)

    msg = (
        f'Project "{application.data["shortname"]["value"]}" Approved by {application.approved_by}.'
    )
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
    guild = await bot.fetch_guild(settings.NEW_PROJECT_REVIEW_DISCORD_GUILD_ID)

    channel = None
    if application.channel_id:
        channel = await guild.fetch_channel(application.channel_id)
        mention_role = await guild.fetch_role(settings.NEW_PROJECT_REVIEW_DISCORD_ROLE_MENTION_ID)
        await channel.send(
            f"This project has been marked complete by {application.archived_by}, "
            "and archived.\n\n"
            f"{mention_role.mention} please update the project information in "
            f"https://discord.com/channels/{guild.id}/{settings.PROJECT_LOG_CHANNEL_ID}, "
            "leave a :white_check_mark: when complete."
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
