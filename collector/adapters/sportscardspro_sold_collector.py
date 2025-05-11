import os

import requests

from collector.adapters import parse_raw_title  # Import the parser


def fetch_sold_items(config):
    """
    Fetch completed sales from SportsCardsPro since last_run_timestamp.
    Args:
        config (dict): includes 'last_run_timestamp' and API credentials.
    Returns:
        dict: {'sold_items': [<standardized dict>], 'valuation_entries': []}
    """
    API_ENDPOINT = "https://api.sportscardspro.com/sold"
    HEADERS = {
        "Authorization": f"Bearer {os.getenv('SPORTSCARDSPRO_API_KEY')}",
        "Content-Type": "application/json",
    }
    PARAMS = {"category": "sports cards", "limit": 50}

    response = requests.get(API_ENDPOINT, headers=HEADERS, params=PARAMS)
    response.raise_for_status()
    data = response.json()

    sold_items = []
    for item in data.get("soldItems", []):
        raw_title = item.get("title")
        parsed_details = parse_raw_title(raw_title)  # Parse the raw title

        sold_items.append(
            {
                "raw_title": raw_title,
                "player_name": parsed_details.get("player_name"),
                "card_year": parsed_details.get("card_year"),
                "card_set": parsed_details.get("set_name"),
                "card_number": parsed_details.get("card_number"),
                "attributes": parsed_details.get("attributes"),
                "grade": parsed_details.get("grade"),
                "grading_company": parsed_details.get("grading_company"),
                "sale_price": float(item.get("price", 0)),
                "currency": item.get("currency", "USD"),
                "sale_date": item.get("dateSold"),
                "source": "SportsCardsPro",
                "source_item_id": item.get("id"),
                "source_url": item.get("url"),
            }
        )

    return {"sold_items": sold_items, "valuation_entries": []}
