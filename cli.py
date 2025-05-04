import asyncio
import os

import click
from dotenv import load_dotenv

from collector.adapters.ebay import fetch_cards
from database.models import init_db

load_dotenv()

# Initialize the database schema
init_db()


@click.group()
def cli():
    """Baseball Card Deal Finder CLI"""
    pass


@cli.command()
@click.option(
    "--query", default="psa 10 topps chrome", help="Search string for eBay."
)
@click.option("--limit", default=100, help="Maximum number of items to fetch.")
def crawl(query, limit):
    """Fetch listings from eBay based on a query."""
    click.echo(f"Fetching up to {limit} items for query: '{query}'...")
    if not os.getenv("EBAY_ACCESS_TOKEN"):
        click.echo(
            "Error: EBAY_ACCESS_TOKEN environment variable not set.", err=True
        )
        click.echo(
            "Pls generate a token (see README) and add it to your .env file.",
            err=True,
        )
        return
    try:
        cards = asyncio.run(fetch_cards(query, limit=limit))
        click.echo(f"Successfully fetched {len(cards)} items from eBay.")
    except Exception as e:
        click.echo(f"Error during crawl: {e}", err=True)


@cli.command()
def analyze():
    """Analyze fetched data to find deals (Placeholder)."""
    click.echo("Analyzer stub - Implement analysis logic here.")


if __name__ == "__main__":
    cli()
