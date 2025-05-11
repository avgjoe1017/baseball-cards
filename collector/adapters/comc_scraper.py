import time

import requests
from bs4 import BeautifulSoup


def collect_comc_listings():
    """
    Scrape COMC for active baseball card listings.
    Returns a list of standardized listing dictionaries.
    """
    base_url = "https://www.comc.com"
    search_path = "/Baseball-Cards"
    max_pages = 5  # Limit the number of pages to scrape

    listings = []

    for page in range(1, max_pages + 1):
        url = f"{base_url}{search_path}?page={page}"
        response = requests.get(url)

        if response.status_code != 200:
            print(f"Failed to fetch page {page}: {response.status_code}")
            break

        soup = BeautifulSoup(response.text, "html.parser")

        # Find all listing elements (adjust the selector based on COMC's structure)
        listing_elements = soup.select(".listing-card")

        for element in listing_elements:
            try:
                raw_title = element.select_one(".card-title").text.strip()
                price_text = element.select_one(".price").text.strip()
                price = float(price_text.replace("$", "").replace(",", ""))
                source_item_id = element["data-item-id"]
                source_url = f"{base_url}{element.select_one('a')['href']}"
                image_url = element.select_one("img")["src"]

                # Add the listing to the results
                listings.append(
                    {
                        "raw_title": raw_title,
                        "listing_price": price,
                        "currency": "USD",
                        "source": "COMC",
                        "source_item_id": source_item_id,
                        "source_url": source_url,
                        "image_url": image_url,
                    }
                )

            except Exception as e:
                print(f"Error parsing listing: {e}")

        # Respectful delay between requests
        time.sleep(1)

    return listings
