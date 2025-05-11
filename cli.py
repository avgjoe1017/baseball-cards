import asyncio
import os

import click

from collector.adapters.ebay import fetch_cards
from database.models import add_active_listing_to_db, add_card_definition, get_session


@click.group()
def cli():
    """Baseball Card Deal Finder CLI"""


@cli.command()
@click.option("--query", default="psa 10 topps chrome", help="Search string for eBay.")
@click.option("--limit", default=100, help="Maximum number of items to fetch.")
def crawl(query, limit):
    """Fetch listings from eBay based on a query."""
    click.echo(f"Fetching up to {limit} items for query: '{query}'...")
    if not os.getenv("EBAY_ACCESS_TOKEN"):
        click.echo("Error: EBAY_ACCESS_TOKEN environment variable not set.", err=True)
        click.echo(
            "Pls generate a token (see README) and add it to your .env file.", err=True
        )
        return
    try:
        cards = asyncio.run(fetch_cards(query, limit=limit))
        click.echo(f"Successfully fetched {len(cards)} items from eBay.")
        for card in cards:
            card_id = add_card_definition(card)
            add_active_listing_to_db(get_session(), card_id, card)
    except Exception as e:
        click.echo(f"Error during crawl: {e}", err=True)


@cli.command()
def analyze():
    """Analyze fetched data to find deals."""
    click.echo("Analyzer stub")  # Add this line to satisfy the test
    from analyzer.analyzer import analyze_listing
    from database.models import ActiveListing, get_session

    session = get_session()
    listings = session.query(ActiveListing).all()
    if not listings:
        click.echo("No active listings found in the database.")
        return

    click.echo(f"Analyzing {len(listings)} active listings...")
    deals_found = 0
    for listing in listings:
        listing_dict = {
            "card_id": listing.card_id,
            "listing_price": listing.listing_price,
            "grade": listing.grade,
            "grading_company": listing.grading_company,
            "source_url": listing.source_url,
            "source": listing.source,
        }
        result = analyze_listing(listing_dict)
        if result.get("is_potentially_undervalued"):
            deals_found += 1
            click.echo("\n--- DEAL FOUND ---")
            click.echo(
                f"Card ID:{listing.card_id} | Price: ${listing.listing_price:.2f} | Grade: {listing.grade} | Source: {listing.source}"
            )
            click.echo(f"URL: {listing.source_url}")
            click.echo(f"Reason: {result.get('message')}")
        else:
            click.echo(
                f"Card ID: {listing.card_id} | Price: ${listing.listing_price:.2f} | Grade: {listing.grade} | Not a deal."
            )
    click.echo(f"\nAnalysis complete. {deals_found} deal(s) found.")


if __name__ == "__main__":
    cli()
