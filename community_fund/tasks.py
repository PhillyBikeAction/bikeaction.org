from asgiref.sync import async_to_sync, sync_to_async
from celery import shared_task
from django.conf import settings
from interactions.models.discord.enums import AutoArchiveDuration

from community_fund.models import CommunityActionFundApplication
from pba_discord.bot import bot

DISCORD_MESSAGE_LIMIT = 1990


def split_discord_messages(markdown):
    messages = []
    message = ""
    for line in markdown.split("\n"):
        while len(line) > DISCORD_MESSAGE_LIMIT:
            if message:
                messages.append(message)
                message = ""
            messages.append(line[:DISCORD_MESSAGE_LIMIT])
            line = line[DISCORD_MESSAGE_LIMIT:]
        if len(message) + len(line) + 1 > DISCORD_MESSAGE_LIMIT:
            if message:
                messages.append(message)
            message = ""
        message += line + "\n"
    if message:
        messages.append(message)
    return messages


async def _add_new_community_action_fund_message_and_thread(application_id):
    application = await CommunityActionFundApplication.objects.filter(id=application_id).afirst()
    if application is None or application.draft or application.thread_id:
        return

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.DISCORD_GUILD_ID)
    channel = await guild.fetch_channel(settings.COMMUNITY_ACTION_FUND_REVIEW_DISCORD_CHANNEL_ID)
    thread = await channel.create_thread(
        name=f"Community Fund: {application.data['project_title']['value']}"[:100],
        reason="Community Action Fund application submitted",
        auto_archive_duration=AutoArchiveDuration.ONE_WEEK,
    )

    if not application.markdown:
        await sync_to_async(application.render_markdown)()
    for message in split_discord_messages(application.markdown):
        await thread.send(message)

    review_message = "Please review this Community Action Fund application."
    if settings.COMMUNITY_ACTION_FUND_REVIEW_DISCORD_ROLE_MENTION_ID:
        role = await guild.fetch_role(settings.COMMUNITY_ACTION_FUND_REVIEW_DISCORD_ROLE_MENTION_ID)
        review_message = f"{role.mention} {review_message}"
    await thread.send(
        f"{review_message}\n\nUse `/community-fund decide` in this thread to approve or decline it."
    )
    application.thread_id = thread.id
    await application.asave()


@shared_task
def add_new_community_action_fund_message_and_thread(application_id):
    async_to_sync(_add_new_community_action_fund_message_and_thread)(application_id)
