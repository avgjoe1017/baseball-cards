# collector/adapters/ebay.py
import asyncio
import os

from aiohttp import ClientSession
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from database.models import Card, SessionLocal

# Load environment variables from .env
load_dotenv()

EBAY_API = "https://api.ebay.com/buy/browse/v1/item_summary/search"
# Update HEADERS to dynamically fetch the token from .env
HEADERS = {"Authorization": f"Bearer {os.getenv('EBAY_ACCESS_TOKEN')}"}

# Add a delay to respect eBay's rate limits
RATE_LIMIT_DELAY = float(os.getenv("EBAY_RATE_LIMIT_DELAY", 0.1))


class RateLimitException(Exception):
    """Custom exception for rate-limiting errors."""

    pass


@retry(wait=wait_exponential(multiplier=1, max=60), stop=stop_after_attempt(5))
async def _call(session, params):
    async with session.get(EBAY_API, headers=HEADERS, params=params) as r:
        if r.status == 429:
            raise RateLimitException("rate-limited")
        r.raise_for_status()
        return await r.json()


async def fetch_cards(query: str, limit: int = 100):
    items, offset = [], 0
    db = SessionLocal()
    try:
        async with ClientSession() as session:
            while len(items) < limit:
                payload = await _call(
                    session,
                    dict(
                        q=query,
                        limit=50,
                        offset=offset,
                    ),
                )
                for item in payload.get("itemSummaries", []):
                    # Map eBay data to Card model
                    card = Card(
                        player=item.get(
                            "title"
                        ),  # Example mapping, adjust as needed
                        year=None,  # Add logic to extract year if available
                        set_name=item.get("categoryPath"),
                        card_num=item.get("itemId"),
                        attributes=str(item),
                    )
                    db.add(card)
                db.commit()
                items.extend(payload.get("itemSummaries", []))
                if "next" not in payload.get("href", ""):
                    break
                offset += 50
                await asyncio.sleep(
                    RATE_LIMIT_DELAY
                )  # Use the delay from .env
    finally:
        db.close()
    return items[:limit]
