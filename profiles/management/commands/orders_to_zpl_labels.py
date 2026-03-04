from collections import defaultdict

from django.core.management.base import BaseCommand

from profiles.models import ShirtOrder


class Command(BaseCommand):
    def handle(self, *args, **options):
        orders_by_email = defaultdict(list)
        emails = set()

        addresses = []

        for order in ShirtOrder.objects.all():
            emails.add(order.user.email)
            orders_by_email[order.user.email].append(order)

        for email, orders in orders_by_email.items():
            offset = 300
            print("^XA")
            print("^CFA,50")
            address_line = None
            one_liner = None
            for order in orders:
                if address_line is None:
                    shipping = order.shipping_details["address"]
                    address_line = f"^FO60,{offset}^FD{shipping['line1']}^FS" + "\n"
                    one_liner = f"{shipping['line1']}"
                    offset += 60
                    if shipping["line2"]:
                        address_line += f"^FO60,{offset}^FD{shipping['line2']}^FS" + "\n"
                        one_liner += ", " + f"{shipping['line2']}"
                        offset += 60
                    address_line += f"^FO60,{offset}^FD{shipping['city']}"
                    one_liner += ", " + f"{shipping['city']}"
                    address_line += ", " + shipping["state"]
                    one_liner += ", " + shipping["state"]
                    address_line += " " + shipping["postal_code"] + "^FS\n"
                    one_liner += " " + shipping["postal_code"]
                    offset += 60

            print(f"^FO60,240^FD{order.shipping_details['name']}^FS")
            print(address_line)
            addresses.append(one_liner)

            offset += 120

            for order in orders:
                print(
                    f"^FO60,{offset}^FD{order.get_fit_display()[:7].strip()} - "
                    f"{order.get_size_display()} - {order.get_print_color_display()}^FS"
                )
                offset += 60
            print("^XZ")

        # for address in addresses:
        #     print(address)
