import os
from datetime import datetime

import requests


def fetch_valuations(config):
    """
    Fetch valuation entries from SportsCardsPro since last_run_timestamp.
    Args:
        config (dict): includes 'last_run_timestamp' and API credentials.
    Returns:
        dict: {'sold_items': [], 'valuation_entries': [<standardized valuation dict>]}
    """
    API_ENDPOINT = "https://api.sportscardspro.com/valuations"
    HEADERS = {
        "Authorization": f"Bearer {os.getenv('SPORTSCARDSPRO_API_KEY')}",
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
                "source": "SportsCardsPro",
                "source_url_to_valuation_info": item.get("url"),
                "grade": None,  # Placeholder
                "grading_company": None,  # Placeholder
            }
        )

    return {"sold_items": [], "valuation_entries": valuation_entries}
