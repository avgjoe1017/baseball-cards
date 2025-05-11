# Blowout Cards Scraper
# This module scrapes the Blowout Cards website to fetch baseball card listings.

import requests
from bs4 import BeautifulSoup

def collect_blowout_cards_listings():
    """Scrape listings from Blowout Cards."""
    url = "https://www.blowoutcards.com/baseball"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch data from {url}, status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    listings = []

    # Example scraping logic: Find product containers and extract details
    product_containers = soup.find_all('div', class_='product-container')
    for container in product_containers:
        title = container.find('h2', class_='product-title').get_text(strip=True)
        price = container.find('span', class_='product-price').get_text(strip=True)
        link = container.find('a', class_='product-link')['href']

        listings.append({
            'title': title,
            'price': price,
            'link': f"https://www.blowoutcards.com{link}"
        })

    return listings
