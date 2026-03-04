import hashlib

from django.conf import settings
from django.core.management.base import BaseCommand

from pbaabp.email import send_email_message
from profiles.models import Profile

profiles = Profile.objects.all()

SENT = []

DONOTSEND = [
    "0747c131b2a6c57d3d997181730e5a6a03dee5621b9d0df92c8b652d8d1f4e2f",
    "3605a4011aa7b62384cb143da2ad4011e6a16cd0a59d4cf37bf62f885cc51b46",
    "239b9cc334fe305858a58af22d97063a07a5d704bb701590d711304ea42524b6",
    "747b63a42ed26ae1f99ddc14c3d9e2e11ab9a4e5aa8cc951a82ac277c139adeb",
    "15f256cdf8b51d656ff3723f8551175916fee5c97755ca59fbdcc68f3ad9a194",
    "274058d395e594414e0dab333daa02667e74604d98d22d699d285f233f300f91",
    "5acaf2d83cfde333df90e8bf41b0bbefdb1786793fd2f4e01b6452270fc04230",
    "cac3f50c5449445e3131add5d7f9f07d7ad623e6254183963fefec0076a7b58f",
    "298f3b2a21594b6b581031365b69cf8127a2d72cd3c41c33bdee282be0ffc50b",
    "8ba2f2736d08b50aa8e164924cc9c9eac88ac5a1a8bd36cda8a991d424c56588",
    "e6048ac2e7d7719e8e9b759349edc1424e2dbdd68842085328d0b93b4b3f48b8",
    "d2197b7cdee7c1f300f677553b40ca3f991db6c280053bc23f82f18aacf6a0e8",
    "491737e450cce35206eb7fc315b10e2bdca012f0eeb57e573242bd5f62c508ac",
    "93aecc266fc976ab5a7de905cbeaefaf9e3bf6ec410014c05423432aadf4f240",
    "ccda49c6054772fe7f6153b2ab48e76bd9f95391483463ff2133d527726ca00b",
    "f5a8183cf185d3a8b59b5fbd979f02c202f728f33bd387a7c43f7c658a0a8f92",
]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email_template", nargs="?", type=str)

    def handle(self, *args, **options):
        settings.EMAIL_SUBJECT_PREFIX = ""
        for profile in profiles:
            if hashlib.sha256(profile.user.email.encode()).hexdigest() in DONOTSEND:
                print(f"skipping {profile}")
                continue
            if profile.user.email not in SENT:
                send_email_message(
                    "penndot_broad_st_bike_lanes_2025_03_20",
                    "Philly Bike Action <noreply@bikeaction.org>",
                    [profile.user.email],
                    {"profile": profile},
                    reply_to=["info@bikeaction.org"],
                )
                SENT.append(profile.user.email)
            else:
                print(f"skipping {profile}")
        print(len(SENT))
