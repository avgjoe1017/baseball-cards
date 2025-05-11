# collector/adapters/ebay.py
import asyncio
import os

import aiohttp
import requests
from aiohttp import ClientSession
from tenacity import retry, stop_after_attempt, wait_exponential
from database.models import get_session


# Placeholder function for parsing raw titles
def parse_raw_title(title: str) -> dict:
    """
    Parse the raw title of a card listing to extract metadata.

    Args:
        title (str): The raw title string.

    Returns:
        dict: A dictionary containing parsed metadata.
    """
    # Example implementation (replace with actual parsing logic)
    return {
        "player_name": "Unknown Player",
        "card_year": "Unknown Year",
        "set_name": "Unknown Set",
        "card_number": "Unknown Number",
        "attributes": [],
        "grade": None,
        "grading_company": None,
    }


EBAY_API = "https://api.ebay.com/buy/browse/v1/item_summary/search"
# Update HEADERS to dynamically fetch the token from .env
HEADERS = {"Authorization": f"Bearer {os.getenv('EBAY_ACCESS_TOKEN')}"}

# Add a delay to respect eBay's rate limits
RATE_LIMIT_DELAY = float(os.getenv("EBAY_RATE_LIMIT_DELAY", 0.1))


class RateLimitException(Exception):
    """Custom exception for rate-limiting errors."""


class TokenRefreshException(Exception):
    """Custom exception for token refresh errors."""


def refresh_ebay_token():
    """Refresh the eBay OAuth access token."""
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

    response = requests.post(
        url, headers=headers, data=data, auth=(client_id, client_secret)
    )
    if response.status_code != 200:
        print("Failed to refresh token. Response:", response.text)
    response.raise_for_status()

    new_access_token = response.json().get("access_token")
    if new_access_token:
        # Update the global HEADERS with the new token
        HEADERS["Authorization"] = f"Bearer {new_access_token}"
        print("Access token refreshed successfully.")
    else:
        raise TokenRefreshException("Failed to refresh eBay access token.")


@retry(wait=wait_exponential(multiplier=1, max=60), stop=stop_after_attempt(5))
async def _call(session, params):
    try:
        async with session.get(EBAY_API, headers=HEADERS, params=params) as r:
            if r.status == 429:
                raise RateLimitException("rate-limited")
            r.raise_for_status()
            return await r.json()
    except aiohttp.ClientResponseError as e:
        if e.status == 401:  # Unauthorized
            print("Access token expired. Refreshing token...")
            refresh_ebay_token()
            # Retry the request with the new token
            async with session.get(EBAY_API, headers=HEADERS, params=params) as r:
                r.raise_for_status()
                return await r.json()
        else:
            print(f"HTTPError: {e.status} - {e.message}")
            raise
    except Exception as e:
        print(f"Unexpected error during API call: {e}")
        raise


async def fetch_cards(query: str, limit: int = 100):
    """
    Fetch cards from eBay's API and return standardized card dictionaries.

    Args:
        query (str): The search query.
        limit (int): The maximum number of cards to fetch.

    Returns:
        list: A list of standardized card dictionaries.
    """
    items, offset = [], 0

    async with ClientSession() as session:
        while len(items) < limit:
            try:
                payload = await _call(
                    session,
                    dict(
                        q=query,
                        limit=50,
                        offset=offset,
                    ),
                )
                for item in payload.get("itemSummaries", []):
                    parsed_data = parse_raw_title(item.get("title", ""))

                    card_dict = {
                        "player_name": parsed_data.get("player_name"),
                        "card_year": parsed_data.get("card_year"),
                        "card_set": parsed_data.get("set_name"),
                        "card_number": parsed_data.get("card_number"),
                        "attributes": parsed_data.get("attributes"),
                        "grade": parsed_data.get("grade"),
                        "grading_company": parsed_data.get("grading_company"),
                        "source": "eBay",
                        "source_item_id": item.get("itemId"),
                        "listing_price": float(item.get("price", {}).get("value", 0)),
                        "currency": item.get("price", {}).get("currency", "USD"),
                        "listing_date": item.get("itemCreationDate"),
                        "source_url": item.get("itemWebUrl"),
                    }

                    card_dict = {
                        k: v if v is not None else "" for k, v in card_dict.items()
                    }
                    items.append(card_dict)

                if "next" not in payload.get("href", ""):
                    break
                offset += 50
                await asyncio.sleep(RATE_LIMIT_DELAY)
            except RateLimitException:
                print("Rate limit hit. Retrying after delay...")
                await asyncio.sleep(60)  # Wait before retrying
            except Exception as e:
                print(f"Error fetching cards: {e}")
                break

    session = get_session()
    try:
        for card in items[:limit]:
            session.add(card)  # Add each card to the database session
        session.commit()  # Commit the session after adding all cards
    except Exception as e:
        session.rollback()
        print(f"Error saving cards to the database: {e}")
    finally:
        session.close()

    return items[:limit]


async def fetch_item_details(session: ClientSession, item_id: str):
    """
    Fetch details for a specific eBay item by its ID.

    Args:
        session (ClientSession): The aiohttp session for making requests.
        item_id (str): The eBay item ID.

    Returns:
        dict: The item details if found, or None if not found.
    """
    # Corrected endpoint for fetching a single item by its ID using Browse API
    url = f"https://api.ebay.com/buy/browse/v1/item/{item_id}"
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                print(f"Item {item_id} not found.")
                return None
            else:
                response.raise_for_status()
    except Exception as e:
        print(f"Error fetching item details for {item_id}: {e}")
        return None


# eBay API Collector
# This module interacts with the eBay API to fetch baseball card listings.


def collect_ebay_listings():
    """
    Fetch active eBay listings using the eBay Browse or Finding API.

    Returns:
        list: A list of standardized dictionaries containing listing details.
    """
    API_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    HEADERS = {
        "Authorization": f"Bearer {os.getenv('EBAY_ACCESS_TOKEN')}",
        "Content-Type": "application/json",
    }
    PARAMS = {"q": "sports cards", "limit": 50}

    response = requests.get(API_ENDPOINT, headers=HEADERS, params=PARAMS)
    response.raise_for_status()
    data = response.json()

    listings = []
    for item in data.get("itemSummaries", []):
        listings.append(
            {
                "raw_title": item.get("title"),
                "source": "eBay",
                "source_item_id": item.get("itemId"),
                "listing_price": float(item.get("price", {}).get("value", 0)),
                "currency": item.get("price", {}).get("currency", "USD"),
                "listing_date": item.get("itemCreationDate"),
                "source_url": item.get("itemWebUrl"),
                "grade": None,  # Placeholder, requires additional parsing
                "grading_company": None,  # Placeholder, requires additional parsing
            }
        )

    return listings
