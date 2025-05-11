import os
from datetime import datetime

import requests


def fetch_valuations(config):
    """
    Fetch card valuation data from eBay price guide or similar.
    Args:
        config (dict): includes 'last_run_timestamp' and API credentials.
    Returns:
        dict: {'sold_items': [], 'valuation_entries': [<standardized valuation dict>]}
    """
    API_ENDPOINT = (
        "https://api.ebay.com/valuation/endpoint"  # Replace with actual endpoint
    )
    HEADERS = {
        "Authorization": f"Bearer {os.getenv('EBAY_ACCESS_TOKEN')}",
        "Content-Type": "application/json",
    }
    PARAMS = {"category": "sports cards", "limit": 50}

    response = requests.get(API_ENDPOINT, headers=HEADERS, params=PARAMS)
    response.raise_for_status()
    data = response.json()

    valuation_entries = []
    for item in data.get("valuations", []):
        valuation_entries.append(
            {
                "raw_card_name_from_source": item.get("title"),
                "estimated_value": float(item.get("value", 0)),
                "currency": item.get("currency", "USD"),
                "valuation_date": datetime.utcnow().isoformat(),
                "source": "eBay",
                "source_url_to_valuation_info": item.get("url"),
                "grade": None,  # Placeholder
                "grading_company": None,  # Placeholder
            }
        )

    return {"sold_items": [], "valuation_entries": valuation_entries}
