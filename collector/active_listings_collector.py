# active_listings_collector.py
import importlib
import json
import logging
import os
from datetime import datetime

import requests

from database.models import add_active_listing_to_db, add_card_definition, get_session

# Load configuration file
CONFIG_FILE = "sites_config.json"

# Configure logging
LOG_FILE = "collector.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def log_progress(message):
    """Log progress messages to the log file."""
    logging.info(message)


def log_error(message):
    """Log error messages to the log file."""
    logging.error(message)


def load_config():
    """Load the sites configuration from the JSON file."""
    with open(CONFIG_FILE, "r") as file:
        return json.load(file)


# Update send_dashboard_notification to include logging
def send_dashboard_notification(level, message):
    """
    Send a notification to the dashboard or monitoring system.
    """
    # Print the notification to the console
    print(f"NOTIFICATION [{level}]: {message}")

    # Log the notification
    if level == "ERROR":
        log_error(message)
    else:
        log_progress(message)

    # Send the notification to a monitoring system (e.g., Slack or Grafana)
    try:
        monitoring_url = os.getenv("MONITORING_WEBHOOK_URL")
        if monitoring_url:
            payload = {
                "level": level,
                "message": message,
                "timestamp": datetime.now(datetime.timezone.utc).isoformat(),
            }
            headers = {"Content-Type": "application/json"}
            response = requests.post(monitoring_url, json=payload, headers=headers)
            response.raise_for_status()
    except Exception as e:
        print(f"Failed to send notification to monitoring system: {e}")
        log_error(f"Failed to send notification to monitoring system: {e}")


def process_site(site_config):
    """Process a single site based on its configuration."""
    session = get_session()
    try:
        for collector in site_config.get("collectors", []):
            module_name = collector["module"]
            function_name = collector["function"]
            module = importlib.import_module(module_name)
            collect_function = getattr(module, function_name)

            print(
                f"DEBUG: Collector function {function_name} returned: {list(collect_function())}"
            )

            for listing in collect_function():
                print(f"DEBUG: Processing listing: {listing}")
                player_name = listing.get("player_name")
                card_year = listing.get("card_year")
                card_set = listing.get("card_set")
                card_number = listing.get("card_number")
                attributes = listing.get("attributes")

                card_id = add_card_definition(
                    {
                        "player_name": player_name,
                        "card_year": card_year,
                        "card_set": card_set,
                        "card_number": card_number,
                        "attributes": attributes,
                    }
                )

                print(f"DEBUG: Adding listing to DB: {listing} (card_id={card_id})")

                add_active_listing_to_db(session, card_id, listing)
        session.commit()
    except Exception as e:
        session.rollback()
        log_error(f"Error processing site {site_config.get('name')}: {e}")
    finally:
        session.close()


def main():
    """Main function to orchestrate the collection process."""
    config = load_config()

    for site in config:
        if not site.get("enabled", False):
            continue

        send_dashboard_notification("INFO", f"Starting collection for {site['name']}")
        process_site(site)
        send_dashboard_notification(
            "INFO", f"Successfully collected listings from {site['name']}"
        )


if __name__ == "__main__":
    main()
