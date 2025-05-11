import os

import requests

from collector.adapters import parse_raw_title  # Import the parser


def fetch_sold_items(config):
    """
    Fetch completed eBay sales since last_run_timestamp using Finding API.
    """
    app_id = config["api_details"].get("app_id") or os.getenv("EBAY_APP_ID")
    last_run = config.get("last_run_timestamp")
    url = "https://svcs.ebay.com/services/search/FindingService/v1"
    headers = {
        "X-EBAY-SOA-OPERATION-NAME": "findCompletedItems",
        "X-EBAY-SOA-SERVICE-VERSION": "1.13.0",
        "X-EBAY-SOA-SECURITY-APPNAME": app_id,
        "X-EBAY-SOA-RESPONSE-DATA-FORMAT": "JSON",
    }
    params = {
        "keywords": config.get("keywords", ""),
        "sortOrder": "EndTimeSoonest",
        "itemFilter(0).name": "SoldItemsOnly",
        "itemFilter(0).value": "true",
        "paginationInput.entriesPerPage": "100",
    }
    # If last_run provided, convert to eBay API timestamp filter
    if last_run:
        params["itemFilter(1).name"] = "EndTimeFrom"
        params["itemFilter(1).value"] = last_run

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()
    # Navigate to items
    results = (
        data.get("findCompletedItemsResponse", [{}])[0]
        .get("searchResult", [{}])[0]
        .get("item", [])
    )
    sold_items = []

    for item in results:
        raw_title = item.get("title")
        parsed_details = parse_raw_title(raw_title)  # Parse the raw title

        sold_items.append(
            {
                "raw_title": raw_title,
                "player_name": parsed_details.get("player_name"),
                "card_year": parsed_details.get("card_year"),
                "card_set": parsed_details.get(
                    "set_name"
                ),  # Ensure key matches parser output
                "card_number": parsed_details.get("card_number"),
                "attributes": parsed_details.get("attributes"),
                "grade": parsed_details.get("grade"),
                "grading_company": parsed_details.get("grading_company"),
                "sale_price": float(
                    item.get("sellingStatus", [{}])[0]
                    .get("currentPrice", [{}])[0]
                    .get("__value__", 0)
                ),
                "currency": item.get("sellingStatus", [{}])[0]
                .get("currentPrice", [{}])[0]
                .get("@currencyId"),
                "sale_date": item.get("listingInfo", [{}])[0].get(
                    "endTime"
                ),  # Correctly parsed
                "source": "eBay",
                "source_item_id": item.get("itemId"),
                "source_url": item.get("viewItemURL"),
                "listing_type": item.get("listingInfo", [{}])[0].get("listingType"),
                "seller_info": None,
                "buyer_info": None,
                "image_url": item.get("galleryURL"),
                "description_text": None,
            }
        )
    return {"sold_items": sold_items, "valuation_entries": []}
