from asgiref.sync import async_to_sync
from celery import shared_task
from django.conf import settings
from interactions import Permissions

from pba_discord.bot import bot
from pba_discord.components.neighborhood_selection import NeighborhoodSelection


async def aupdate_neighborhood_role_and_channel(neighborhood_id):
    from neighborhood_selection.models import Neighborhood

    neighborhood = await Neighborhood.objects.filter(id=neighborhood_id).afirst()
    if neighborhood is None or not neighborhood.approved:
        return

    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.NEIGHBORHOOD_SELECTION_DISCORD_GUILD_ID)
    selection_channel = await guild.fetch_channel(
        settings.NEIGHBORHOOD_SELECTION_DISCORD_CHANNEL_ID
    )
    channels = await guild.fetch_channels()
    roles = guild.roles

    role_name = f"neighborhood-{neighborhood.name.lower().replace(' ', '-')}"
    channel_name = f"{neighborhood.name.lower().replace(' ', '-')}"

    if neighborhood.discord_role_id is None:
        if role_name not in [r.name for r in roles]:
            print("Creating role...")
            role = await guild.create_role(role_name, permissions=Permissions.NONE)
            neighborhood.discord_role_id = role.id
            await neighborhood.asave()
    else:
        role = await guild.fetch_role(neighborhood.discord_role_id)

    if neighborhood.discord_channel_id is None:
        if channel_name not in [c.name for c in channels]:
            print("Creating channel...")
            channel = await guild.create_text_channel(
                channel_name, category=selection_channel.category
            )
            neighborhood.discord_channel_id = channel.id
            await neighborhood.asave()
    else:
        channel = await guild.fetch_channel(neighborhood.discord_channel_id)

    print("harmonizing permissions...")
    await channel.set_permission(
        role,
        send_messages=True,
        send_messages_in_threads=True,
        view_channel=True,
        use_application_commands=True,
        read_message_history=True,
        add_reactions=True,
    )
    await channel.set_permission(guild.default_role, view_channel=False, connect=False)

    if settings.NEIGHBORHOOD_SELECTION_NOTIFICATION_DISCORD_CHANNEL_ID:
        await bot.get_channel(settings.NEIGHBORHOOD_SELECTION_NOTIFICATION_DISCORD_CHANNEL_ID).send(
            f"Neighborhood `{neighborhood.name}` approved!"
        )

    await NeighborhoodSelection.update_buttons(
        bot, settings.NEIGHBORHOOD_SELECTION_DISCORD_CHANNEL_ID, None
    )


@shared_task
def update_neighborhood_role_and_channel(neighborhood_id):
    async_to_sync(aupdate_neighborhood_role_and_channel)(neighborhood_id)


async def adelete_neighborhood_role_and_channel(discord_role_id, discord_channel_id):
    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.NEIGHBORHOOD_SELECTION_DISCORD_GUILD_ID)

    if discord_channel_id is not None:
        channel = await guild.fetch_channel(discord_channel_id)
        await channel.delete()

    if discord_role_id is not None:
        role = await guild.fetch_role(discord_role_id)
        await role.delete()

    await NeighborhoodSelection.update_buttons(
        bot, settings.NEIGHBORHOOD_SELECTION_DISCORD_CHANNEL_ID, None
    )
    print("all tidied!")


@shared_task
def delete_neighborhood_role_and_channel(discord_role_id, discord_channel_id):
    async_to_sync(adelete_neighborhood_role_and_channel)(discord_role_id, discord_channel_id)
