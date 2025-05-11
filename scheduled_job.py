import asyncio
import time
from datetime import datetime  # Removed timedelta as it is unused

from aiohttp import ClientSession
from apscheduler.schedulers.background import BackgroundScheduler

from collector.adapters.ebay import fetch_cards  # Import _call
from database.models import ActiveListing  # Added imports
from database.models import add_active_listing_to_db, add_card_definition, get_session


async def fetch_new_listings(saved_queries):  # Make async
    """
    Fetch new listings from saved searches and add them to the database.

    Args:
        saved_queries (list): A list of search queries.
    """
    session = get_session()  # This session is for synchronous DB operations
    try:
        for query in saved_queries:
            listings = await fetch_cards(
                query
            )  # Await async call, ensure fetch_cards returns standardized dicts
            for listing in listings:
                card_id = add_card_definition(listing)
                add_active_listing_to_db(session, card_id, listing)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


async def refresh_existing_listings():  # Make async
    """
    Refresh existing listings by querying the ActiveListing table.
    Update listing_price and last_seen_at, and remove inactive listings.
    """
    session = get_session()
    # Create an aiohttp session for async eBay calls
    async with ClientSession() as http_session:
        try:
            active_listings = session.query(ActiveListing).all()
            for listing in active_listings:
                # Define fetch_item_details inline as a placeholder
                async def fetch_item_details(http_session, source_item_id):
                    # Simulate fetching item details
                    return {"price": {"value": "100.00"}}  # Mock response

                response = await fetch_item_details(
                    http_session, listing.source_item_id
                )
                if response and response.get("price"):
                    listing.listing_price = float(response["price"]["value"])
                    listing.last_seen_at = datetime.utcnow()
                    session.add(listing)
                else:
                    print(f"Listing {listing.source_item_id} not found. Deleting.")
                    session.delete(listing)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error refreshing listings: {e}")  # Log error
            # raise e # Optionally re-raise
        finally:
            session.close()


async def run_daily_sync():
    """Run the daily sync job for fetching and refreshing listings."""
    saved_queries = [
        "psa 10 griffey rookie",
        "psa 10 topps chrome",
    ]  # Example queries
    await fetch_new_listings(saved_queries)
    await refresh_existing_listings()


def run_daily_sync_sync():
    """Synchronous wrapper for the async run_daily_sync function."""
    asyncio.run(run_daily_sync())


def schedule_jobs():
    """Schedule the daily sync job."""
    scheduler = BackgroundScheduler()
    # Run once immediately then at interval
    scheduler.add_job(
        run_daily_sync_sync, "interval", days=1, next_run_time=datetime.now()
    )
    scheduler.start()

    print("Scheduler started. Press Ctrl+C to exit.")

    try:
        while True:
            time.sleep(2)  # Keep the script running
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    # Initialize DB if needed (idempotent)
    # from database.models import init_db
    # init_db()
    schedule_jobs()
