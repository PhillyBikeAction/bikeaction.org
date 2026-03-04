import requests
from django.conf import settings


class Mailjet:
    def __init__(self):
        self.base_url = "https://api.mailjet.com/v3/REST"
        self.api_key = settings.MAILJET_API_KEY
        self.secret_key = settings.MAILJET_SECRET_KEY
        self.contact_list_id = settings.MAILJET_CONTACT_LIST_ID
        self.auth = (self.api_key, self.secret_key)

    def create_contact(self, email):
        response = requests.post(f"{self.base_url}/contact", json={"Email": email}, auth=self.auth)
        response.raise_for_status()
        return response.json()["Data"][0]

    def get_contact(self, email):
        response = requests.get(f"{self.base_url}/contact/{email}", auth=self.auth)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            else:
                raise
        return response.json()["Data"][0]

    def fetch_contact(self, email):
        response = requests.get(f"{self.base_url}/contact/{email}", auth=self.auth)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return self.create_contact(email)
            else:
                raise
        return response.json()["Data"][0]

    def update_contact_data(self, email, data):
        response = requests.put(
            f"{self.base_url}/contactdata/{email}",
            json={"Data": [{"Name": k, "Value": v} for k, v in data.items()]},
            auth=self.auth,
        )
        response.raise_for_status()
        return response.json()["Data"][0]

    def fetch_contact_lists(self, email):
        response = requests.get(f"{self.base_url}/contact/{email}/getcontactslists", auth=self.auth)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {"Count": 0, "Data": [], "Total": 0}
            else:
                raise

        return response.json()

    def add_contact_to_list(self, email, subscribed=True):
        response = requests.post(
            f"{self.base_url}/contactslist/{self.contact_list_id}/managecontact",
            json={"Action": "addforce" if subscribed else "remove", "Email": email},
            auth=self.auth,
        )
        response.raise_for_status()
        return response.json()["Data"][0]
