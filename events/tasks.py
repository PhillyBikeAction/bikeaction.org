from celery import shared_task

from pbaabp.integrations.mailjet import Mailjet


@shared_task
def sync_to_mailjet(event_signin_id):
    from events.models import EventSignIn

    event_sign_in = EventSignIn.objects.get(id=event_signin_id)

    print(event_sign_in, event_sign_in.newsletter_opt_in)
    if event_sign_in.newsletter_opt_in:
        mailjet = Mailjet()
        if event_sign_in.mailjet_contact_id is None:
            print("creating contact...")
            mailjet.fetch_contact(event_sign_in.email)
            response = mailjet.update_contact_data(
                event_sign_in.email,
                {
                    "newsletter_form": True,
                    "first_name": event_sign_in.first_name,
                    "last_name": event_sign_in.last_name,
                    "name": f"{event_sign_in.first_name} {event_sign_in.last_name}",
                },
            )
            mailjet.add_contact_to_list(event_sign_in.email, subscribed=True)
            event_sign_in.mailjet_contact_id = response["ID"]
            event_sign_in.save()
