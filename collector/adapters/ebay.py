# collector/adapters/ebay.py
import asyncio
import os

from aiohttp import ClientSession
from tenacity import retry, stop_after_attempt, wait_exponential

EBAY_API = "https://api.ebay.com/buy/browse/v1/item_summary/search"
HEADERS = {"Authorization": f"Bearer {os.getenv('EBAY_ACCESS_TOKEN')}"}


@retry(wait=wait_exponential(multiplier=1, max=60), stop=stop_after_attempt(5))
async def _call(session, params):
    async with session.get(EBAY_API, headers=HEADERS, params=params) as r:
        if r.status == 429:
            raise Exception("rate-limited")
        r.raise_for_status()
        return await r.json()


async def fetch_cards(query: str, limit: int = 100):
    items, offset = [], 0
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
            items.extend(payload.get("itemSummaries", []))
            if "next" not in payload.get("href", ""):
                break
            offset += 50
            await asyncio.sleep(0.1)
    return items[:limit]
