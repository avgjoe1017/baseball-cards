import os

import requests
from dotenv import load_dotenv, set_key

load_dotenv()

EBAY_CLIENT_ID = os.getenv("EBAY_APP_ID")
EBAY_CLIENT_SECRET = os.getenv("EBAY_CERT_ID")
EBAY_REFRESH_TOKEN = os.getenv("EBAY_OAUTH_REFRESH_TOKEN")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def refresh_token():
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    auth = (EBAY_CLIENT_ID, EBAY_CLIENT_SECRET)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": EBAY_REFRESH_TOKEN,
        "scope": (
            "https://api.ebay.com/oauth/api_scope "
            "https://api.ebay.com/oauth/api_scope/buy.marketplace.insight "
            "https://api.ebay.com/oauth/api_scope/buy.item.summary "
            "https://api.ebay.com/oauth/api_scope/buy.item.bulk"
        ),
    }
    resp = requests.post(url, headers=headers, data=data, auth=auth)
    if resp.status_code == 200:
        access_token = resp.json()["access_token"]
        set_key(ENV_PATH, "EBAY_ACCESS_TOKEN", access_token)
        print("eBay access token refreshed and saved to .env.")
    else:
        print(f"Failed to refresh token: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    refresh_token()
