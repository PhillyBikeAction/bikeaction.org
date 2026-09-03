import datetime

import requests
from celery import shared_task
from django.conf import settings


@shared_task
def sync_alias_to_mailgun(alias_id):
    from aliases.models import Alias

    alias = Alias.objects.get(id=alias_id)
    recipients = ",".join([r.email_address for r in alias.recipients.all()])

    url = "https://api.mailgun.net/v3/routes"
    auth = ("api", settings.MAILGUN_API_KEY)
    data = {
        "priority": 0,
        "description": f"apps managed DO NOT EDIT - {alias.alias}@{alias.domain}",
        "expression": f'match_recipient("{alias.alias}@{alias.domain}")',
        "action": [f'forward("{recipients}")', "stop()"],
    }

    _mailgun_id = None
    if recipients:
        if alias.mailgun_id:
            url += f"/{alias.mailgun_id}"
            response = requests.put(url, data=data, auth=auth, timeout=30)
        else:
            response = requests.post(url, data=data, auth=auth, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        route = response_data.get("route", response_data)
        _mailgun_id = route["id"]

    _mailgun_smtp_password = None
    if alias.enable_smtp:
        if alias.mailgun_smtp_password:
            _mailgun_smtp_password = alias.mailgun_smtp_password
        else:
            url = f"https://api.mailgun.net/v3/domains/{alias.domain}/credentials"
            data = {"login": f"{alias.alias}@{alias.domain}"}
            response = requests.post(url, data=data, auth=auth, timeout=30)
            response.raise_for_status()
            data = response.json()
            _mailgun_smtp_password = data["credentials"][f"{alias.alias}@{alias.domain}"]
    else:
        if alias.mailgun_smtp_password:
            url = (
                "https://api.mailgun.net/v3/domains/"
                f"{alias.domain}/credentials/{alias.alias}@{alias.domain}"
            )
            response = requests.delete(url, auth=auth)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                pass
            data = response.json()
            _mailgun_smtp_password = None

    Alias.objects.filter(id=alias_id).update(
        mailgun_updated_at=datetime.datetime.now(datetime.UTC),
        mailgun_id=_mailgun_id,
        mailgun_smtp_password=_mailgun_smtp_password,
    )


@shared_task
def remove_alias_from_mailgun(alias, domain, mailgun_alias_id):
    url = f"https://api.mailgun.net/v3/routes/{mailgun_alias_id}"
    auth = ("api", settings.MAILGUN_API_KEY)
    response = requests.delete(url, auth=auth)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        pass

    url = f"https://api.mailgun.net/v3/domains/{domain}/credentials/{alias}@{domain}"
    response = requests.delete(url, auth=auth)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        pass
