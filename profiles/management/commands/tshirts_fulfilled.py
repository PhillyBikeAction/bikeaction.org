from collections import defaultdict

from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import ShirtOrder

TEMPLATE = """
Hello {{first_name}},

Your PBA T-Shirt pre-order of:

{% for order in orders %}
- {{order.get_fit_display}} - {{order.get_size_display}} -
    {{order.get_print_color_display}}{% endfor %}

Has been fulfilled! You should have already received your order by {{orders.0.shipping_method}}.

{% if orders.0.shipping_method == "usps" %}For those of you outside of Philly,
it should arrive via usps today!{% endif %}

If you didn't receive it, please reply to this email and we'll work to figure out what happened!

**Philly Bike Action Robot**
"""


class Command(BaseCommand):
    def handle(self, *args, **options):
        orders_by_email = defaultdict(list)
        emails = set()

        for order in ShirtOrder.objects.all():
            emails.add(order.user.email)
            orders_by_email[order.user.email].append(order)

        for email, orders in orders_by_email.items():
            for order in orders:
                order.fulfilled = True
                order.save()

            send_email_message(
                None,
                "Philly Bike Action <apps@bikeaction.org>",
                [email],
                {"first_name": orders[0].user.first_name, "orders": orders},
                subject="Your PBA T-Shirt Pre-Order has been fulfilled!",
                message=TEMPLATE,
            )
