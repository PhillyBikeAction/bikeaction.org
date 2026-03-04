from zoneinfo import ZoneInfo

import requests
from django.conf import settings


class WordPressAPI:
    def __init__(self, url=None, email=None, password=None):
        self.url = url if url is not None else settings.WP_URL
        self.email = email if email is not None else settings.WP_LOGIN_EMAIL
        self.password = password if password is not None else settings.WP_LOGIN_PASS
        self.token = None

    def auth(self):
        if self.token is not None:
            self.refresh_token()
        else:
            self.fetch_token()

    def refresh_token(self):
        r = requests.post(
            f"{self.url}/",
            params={
                "rest_route": "/simple-jwt-login/v1/auth/refresh",
            },
            data={
                "JWT": self.token,
            },
        )
        self.token = r.json()["data"]["jwt"]

    def fetch_token(self):
        r = requests.post(
            f"{self.url}/",
            params={
                "rest_route": "/simple-jwt-login/v1/auth",
            },
            data={
                "email": self.email,
                "password": self.password,
            },
        )
        self.token = r.json()["data"]["jwt"]

    def create_venue(self, venue_name):
        r = requests.post(
            f"{self.url}/wp-json/tribe/events/v1/venues/",
            headers={"Authorization": f"Bearer {self.token}"},
            data={
                "venue": venue_name,
            },
        )
        return r.json()

    def fetch_venue(self, venue_name):
        url = f"{self.url}/wp-json/tribe/events/v1/venues/?page=1&per_page=10&status=publish"
        _venue = None

        while url is not None:
            venues = requests.get(url, headers={"Authorization": f"Bearer {self.token}"})
            if venues.json().get("next_rest_url", None):
                url = venues.json()["next_rest_url"]
            else:
                url = None
            for venue in venues.json()["venues"]:
                if venue_name.lower() == venue["venue"].lower():
                    _venue = venue

        if _venue is None:
            _venue = self.create_venue(venue_name)

        return _venue["id"]

    def create_event(
        self, title, description, location, status, start_datetime, end_datetime, cover_url=None
    ):
        venue_id = self.fetch_venue(location)
        data = {
            "title": title,
            "description": description,
            "status": "publish",
            "start_date": start_datetime.astimezone(tz=ZoneInfo(settings.TIME_ZONE)).isoformat(
                sep=" "
            ),
            "end_date": end_datetime.astimezone(tz=ZoneInfo(settings.TIME_ZONE)).isoformat(sep=" "),
            "timezone": settings.TIME_ZONE,
            "venue": venue_id,
        }
        if cover_url is not None:
            data["image"] = cover_url
        r = requests.post(
            f"{self.url}/wp-json/tribe/events/v1/events/",
            headers={"Authorization": f"Bearer {self.token}"},
            data=data,
        )
        return r.json()

    def update_event(
        self,
        event_id,
        title,
        description,
        location,
        status,
        start_datetime,
        end_datetime,
        cover_url=None,
    ):
        venue_id = self.fetch_venue(location)
        data = {
            "title": title,
            "description": description,
            "status": "publish",
            "start_date": start_datetime.astimezone(tz=ZoneInfo(settings.TIME_ZONE)).isoformat(
                sep=" "
            ),
            "end_date": end_datetime.astimezone(tz=ZoneInfo(settings.TIME_ZONE)).isoformat(sep=" "),
            "timezone": settings.TIME_ZONE,
            "venue": venue_id,
        }
        if cover_url is not None:
            data["image"] = cover_url
        r = requests.post(
            f"{self.url}/wp-json/tribe/events/v1/events/{event_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            data=data,
        )
        return r.json()

    def delete_event(self, event_id):
        r = requests.delete(
            f"{self.url}/wp-json/tribe/events/v1/events/{event_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        return r.json()

    def fetch_page(self, page_id):
        r = requests.get(
            f"{self.url}/wp-json/wp/v2/pages/{page_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        return r.json()

    def create_page(self, slug, parent_id, title, content, excerpt, status):
        r = requests.post(
            f"{self.url}/wp-json/wp/v2/pages",
            headers={"Authorization": f"Bearer {self.token}"},
            data={
                "slug": slug,
                "parent": parent_id,
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "status": status,
            },
        )
        return r.json()

    def update_page(self, page_id, slug, parent_id, title, content, excerpt, status):
        r = requests.post(
            f"{self.url}/wp-json/wp/v2/pages/{page_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            data={
                "slug": slug,
                "parent": parent_id,
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "status": status,
            },
        )
        return r.json()
