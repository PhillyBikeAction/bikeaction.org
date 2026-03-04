from asgiref.sync import async_to_sync
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.management.base import BaseCommand

from facets.utils import geocode_address
from profiles.models import ShirtOrder

GEOJSON = """
{
  "coordinates": [
    [
      [
        -75.2205066990683,
        39.927412223964296
      ],
      [
        -75.1947751263647,
        39.92064809822628
      ],
      [
        -75.193960241649,
        39.88290524968312
      ],
      [
        -75.14339814718224,
        39.88563452662345
      ],
      [
        -75.12836546587877,
        39.90681130402922
      ],
      [
        -75.13807552747046,
        39.92849343223966
      ],
      [
        -75.13879242474961,
        39.943771854466036
      ],
      [
        -75.13250780711282,
        39.95946206457555
      ],
      [
        -75.09390278099359,
        39.97666317102849
      ],
      [
        -75.11116493010216,
        39.99741885632497
      ],
      [
        -75.18866877786935,
        40.007013954622096
      ],
      [
        -75.19511987987558,
        39.975964904441724
      ],
      [
        -75.2166232879774,
        39.9746068877574
      ],
      [
        -75.24809357066887,
        39.985879918776476
      ],
      [
        -75.24626367804895,
        39.97259732732388
      ],
      [
        -75.2516100488404,
        39.94740576502545
      ],
      [
        -75.24737555552805,
        39.943220094339665
      ],
      [
        -75.23985550688849,
        39.94225873371337
      ],
      [
        -75.2205066990683,
        39.927412223964296
      ]
    ]
  ],
  "type": "Polygon"
}
"""

geom = GEOSGeometry(GEOJSON)


class Command(BaseCommand):
    def handle(self, *args, **options):
        for order in ShirtOrder.objects.all():
            if order.location is None:
                shipping = order.shipping_details["address"]
                one_liner = f"{shipping['line1']}"
                if shipping["line2"]:
                    one_liner += ", " + f"{shipping['line2']}"
                one_liner += ", " + f"{shipping['city']}"
                one_liner += ", " + shipping["state"]
                one_liner += " " + shipping["postal_code"]
                address = async_to_sync(geocode_address)(one_liner)

                if address.address is not None:
                    order.location = Point(address.longitude, address.latitude)

            if order.shipping_method is None and order.location is not None:
                if geom.contains(order.location):
                    order.shipping_method = "courier"
                else:
                    order.shipping_method = "usps"

            order.save()
