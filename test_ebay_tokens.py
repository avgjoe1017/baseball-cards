import os

import requests


def test_refresh_token():
    """Test the eBay OAuth refresh token."""
    client_id = os.getenv("EBAY_APP_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    refresh_token = os.getenv("EBAY_OAUTH_REFRESH_TOKEN")

    url = "https://api.ebay.com/identity/v1/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://api.ebay.com/oauth/api_scope/buy.*",
    }

    print("Testing refresh token...")
    response = requests.post(
        url, headers=headers, data=data, auth=(client_id, client_secret)
    )
    if response.status_code == 200:
        print("Refresh token is valid. Access token obtained successfully.")
        print("Access Token:", response.json().get("access_token"))
    else:
        print("Failed to refresh token. Response:", response.text)


def test_access_token():
    """Test the eBay access token by making a test API call."""
    access_token = os.getenv("EBAY_ACCESS_TOKEN")
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search?q=test"
    headers = {"Authorization": f"Bearer {access_token}"}

    print("Testing access token...")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("Access token is valid. API call succeeded.")
    else:
        print("Access token is invalid. Response:", response.text)


if __name__ == "__main__":
    test_refresh_token()
    test_access_token()
