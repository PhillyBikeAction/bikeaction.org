from asgiref.sync import async_to_sync
from celery import shared_task
from django.conf import settings
from django.contrib.gis.geos import Point

from facets.utils import geocode_address
from pba_discord.bot import bot
from pbaabp.integrations.mailjet import Mailjet


async def _add_user_to_connected_role(uid):
    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.DISCORD_GUILD_ID)
    role = await guild.fetch_role(settings.DISCORD_CONNECTED_ROLE_ID)
    member = await guild.fetch_member(uid)
    await member.add_role(role.id)


@shared_task
def add_user_to_connected_role(uid):
    async_to_sync(_add_user_to_connected_role)(uid)


async def _remove_user_from_connected_role(uid):
    await bot.login(settings.DISCORD_BOT_TOKEN)
    guild = await bot.fetch_guild(settings.DISCORD_GUILD_ID)
    role = await guild.fetch_role(settings.DISCORD_CONNECTED_ROLE_ID)
    member = await guild.fetch_member(uid)
    await member.remove_role(role.id)


@shared_task
def remove_user_from_connected_role(uid):
    async_to_sync(_remove_user_from_connected_role)(uid)


@shared_task
def geocode_profile(profile_id):
    from profiles.models import Profile

    profile = Profile.objects.get(id=profile_id)

    if profile.street_address is not None:
        print(f"Geocoding {profile}")
        address = async_to_sync(geocode_address)(profile.street_address + " " + profile.zip_code)
        if address.address is not None and not address.address.startswith("Philadelphia"):
            print(f"Address found {address}")
            Profile.objects.filter(id=profile_id).update(
                location=Point(address.longitude, address.latitude)
            )
        else:
            print(f"No address found for {profile.street_address} {profile.zip_code}")
            Profile.objects.filter(id=profile_id).update(location=None)


@shared_task
def sync_to_mailjet(profile_id):
    from profiles.models import Profile

    profile = Profile.objects.get(id=profile_id)
    mailjet = Mailjet()

    response = mailjet.fetch_contact(profile.user.email)
    mailjet.update_contact_data(
        profile.user.email,
        {
            "apps": True,
            "apps_connected": profile.apps_connected,
            "first_name": profile.user.first_name,
            "last_name": profile.user.last_name,
            "name": profile.user.first_name + " " + profile.user.last_name,
        },
    )
    mailjet.add_contact_to_list(profile.user.email, subscribed=profile.newsletter_opt_in)
    profile.mailjet_contact_id = response["ID"]
    profile.save()


@shared_task
def add_mailjet_subscriber(email, first_name, last_name, name):
    mailjet = Mailjet()

    mailjet.fetch_contact(email)
    mailjet.update_contact_data(
        email,
        {
            "newsletter_form": True,
            "first_name": first_name,
            "last_name": last_name,
            "name": name,
        },
    )
    mailjet.add_contact_to_list(email, subscribed=True)


@shared_task
def unsubscribe_mailjet_email(list_id, email):
    if int(list_id) == int(settings.MAILJET_CONTACT_LIST_ID):
        from profiles.models import Profile

        Profile.objects.filter(user__email=email).update(newsletter_opt_in=False)
