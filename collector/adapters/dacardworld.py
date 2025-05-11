import re, time, logging
from decimal import Decimal
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.dacardworld.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
PRICE_RE = re.compile(r"[\d,.]+")

def collect_dacardworld_listings(max_pages=5, delay=1.5):
    sess = requests.Session()
    sess.headers.update(HEADERS)

    page = 1
    listings = []
    while page <= max_pages:
        url = f"{BASE}/sports-cards?page={page}"
        r = sess.get(url, timeout=15)
        if r.status_code != 200:
            logging.warning("page %s -> %s", page, r.status_code)
            break

        soup = BeautifulSoup(r.text, "html.parser")
        for p in soup.select("div.product"):
            title_tag = p.select_one("h4 a")
            price_tag = p.select_one("span.price")
            if not (title_tag and price_tag):
                continue
            listings.append(
                {
                    "title": title_tag.get_text(strip=True),
                    "price": Decimal(PRICE_RE.search(price_tag.text).group().replace(",", "")),
                    "link": urljoin(BASE, title_tag["href"]),
                }
            )

        if not soup.select_one("a.next"):
            break
        page += 1
        time.sleep(delay)

    return listings
