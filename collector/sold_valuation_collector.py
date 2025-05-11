import datetime
import importlib
import json
import logging
import os

import pytz

from database.models import (
    add_card_definition,
    add_sold_listing_to_db,
    add_valuation,
    get_last_run_timestamp,
    get_session,
    update_last_run_timestamp,
)

CONFIG_FILE_PATH = (
    "sites_config.json"  # Assuming same config file, potentially with new sections/keys
)
LOG_FILE_PATH = "sold_valuation_collector_log.txt"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s"
)


def send_dashboard_notification(level, message):
    logging.info(f"DASHBOARD_NOTIFICATION [{level}]: {message}")


def load_sites_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        logging.error(f"Configuration file not found: {CONFIG_FILE_PATH}")
        return []
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logging.error(f"Failed to load site configurations: {e}")
        return []


def process_sold_item_data(sold_item_data, site_name_from_config):
    logging.debug(
        f"Processing SOLD item: {sold_item_data.get('raw_title', 'N/A')} from {site_name_from_config}"
    )
    card_id = add_card_definition(sold_item_data)
    if card_id is None:
        logging.warning(
            f"Could not define card for SOLD item: {sold_item_data.get('raw_title')}. Skipping DB add."
        )
        return False
    sale_data_for_model = {
        "sale_price": sold_item_data["sale_price"],
        "currency": sold_item_data.get("currency", "USD"),
        "sale_date": sold_item_data["sale_date"],
        "source": site_name_from_config,
        "source_item_id": sold_item_data["source_item_id"],
        "source_url": sold_item_data["source_url"],
        "grade": sold_item_data.get("grade"),
        "grading_company": sold_item_data.get("grading_company"),
    }
    return add_sold_listing_to_db(get_session(), card_id, sale_data_for_model)


def process_valuation_entry_data(valuation_data, site_name_from_config):
    logging.debug(
        f"Processing VALUATION entry: {
            valuation_data.get(
                'raw_card_name_from_source',
                'N/A')} from {site_name_from_config}"
    )
    card_id = add_card_definition(valuation_data)
    if card_id is None:
        logging.warning(
            f"Could not define card for VALUATION entry: {
                valuation_data.get('raw_card_name_from_source')}. Skipping DB add."
        )
        return False
    return add_valuation(
        card_id=card_id,
        estimated_value=valuation_data["estimated_value"],
        currency=valuation_data.get("currency", "USD"),
        valuation_date=valuation_data["valuation_date"],
        source=site_name_from_config,
        valuation_type=valuation_data.get("valuation_type"),
        source_url_to_valuation_info=valuation_data.get("source_url_to_valuation_info"),
        grade=valuation_data.get("grade"),
        grading_company=valuation_data.get("grading_company"),
        raw_card_name_from_source=valuation_data.get("raw_card_name_from_source"),
    )


def process_site(site_config):
    """Process a single site based on its configuration."""
    for collector in site_config.get("collectors", []):
        if collector["type"] == "sold_items":
            module_name = collector["module"]
            function_name = collector["function"]
            module = importlib.import_module(module_name)
            collect_function = getattr(module, function_name)
            for sale in collect_function():
                card_id = add_card_definition(sale)
                add_sold_listing_to_db(get_session(), card_id, sale)


def collect_all_sold_and_valuations():
    logging.info("--- Starting Sold & Valuation Collection Cycle ---")
    sites_config = load_sites_config()
    if not sites_config:
        logging.error("No site configurations loaded. Exiting cycle.")
        return

    current_run_start_time_iso = datetime.datetime.now(pytz.utc).isoformat()

    for site_conf_entry in sites_config:
        process_site_config(site_conf_entry, current_run_start_time_iso)

    # Ensure timestamp is updated even if no data is processed
    for site_conf_entry in sites_config:
        site_name = site_conf_entry.get("name")
        for collector_details in site_conf_entry.get("collectors", []):
            data_type_to_collect = collector_details.get("type")
            update_last_run_timestamp(site_name, data_type_to_collect, current_run_start_time_iso)

    logging.info("--- Sold & Valuation Collection Cycle Finished ---")


def process_site_config(site_conf_entry, current_run_start_time_iso):
    site_name = site_conf_entry.get("name")
    if not site_conf_entry.get("enabled", False):
        logging.info(f"Skipping disabled site: {site_name}")
        return
    if "collectors" not in site_conf_entry:
        return

    for collector_details in site_conf_entry["collectors"]:
        process_collector_details(
            site_name, collector_details, current_run_start_time_iso
        )


def process_collector_details(site_name, collector_details, current_run_start_time_iso):
    data_type_to_collect = collector_details.get("type")
    if data_type_to_collect not in ["sold_items", "valuations"]:
        return

    logging.info(
        f"--- Starting collection for site: {site_name}, type: {data_type_to_collect} ---"
    )
    module_name = collector_details.get("module")
    function_name = collector_details.get("function")

    if not module_name or not function_name:
        log_and_notify_config_error(site_name, data_type_to_collect)
        return

    last_run_ts = get_last_run_timestamp(site_name, data_type_to_collect)
    logging.debug(
        f"Last successful run for {site_name}/{data_type_to_collect}: {last_run_ts or 'Never'}"
    )
    try:
        fetched_data_map = fetch_data_from_site(
            module_name, function_name, collector_details, last_run_ts
        )
        if not isinstance(fetched_data_map, dict):
            log_and_notify_return_type_error(site_name, data_type_to_collect)
            return

        process_fetched_data(
            site_name, data_type_to_collect, fetched_data_map, current_run_start_time_iso
        )
    except ImportError:
        log_and_notify_import_error(site_name, module_name, data_type_to_collect)
    except AttributeError:
        log_and_notify_attribute_error(
            site_name, module_name, function_name, data_type_to_collect
        )
    except Exception as e:
        log_and_notify_runtime_error(site_name, data_type_to_collect, e)
    finally:
        logging.info(
            f"--- Finished collection attempt for site: {site_name}, type: {data_type_to_collect} ---"
        )


def fetch_data_from_site(module_name, function_name, collector_details, last_run_ts):
    site_module = importlib.import_module(module_name)
    site_function = getattr(site_module, function_name)
    config_params = collector_details.get(
        "api_details", collector_details.get("scrape_details", {})
    )
    config_params["last_run_timestamp"] = last_run_ts
    return site_function(config_params)


def process_fetched_data(
    site_name, data_type_to_collect, fetched_data_map, current_run_start_time_iso
):
    sold_items_from_site = fetched_data_map.get("sold_items", [])
    sold_items_processed = process_sold_items(site_name, sold_items_from_site) if sold_items_from_site else True

    valuation_entries_from_site = fetched_data_map.get("valuation_entries", [])
    valuations_processed = process_valuation_entries(site_name, valuation_entries_from_site) if valuation_entries_from_site else True

    if sold_items_processed and valuations_processed:
        update_last_run_timestamp(
            site_name, data_type_to_collect, current_run_start_time_iso
        )


def process_sold_items(site_name, sold_items_from_site):
    logging.info(f"Received {len(sold_items_from_site)} SOLD items from {site_name}")
    new_sold_added_count = 0
    for item_data in sold_items_from_site:
        if not all(
            k in item_data
            for k in [
                "raw_title",
                "sale_price",
                "sale_date",
                "source_item_id",
                "source_url",
            ]
        ):
            logging.warning(
                f"Skipping SOLD item from {site_name} due to missing essential fields: {item_data.get('source_item_id', 'N/A')}"
            )
            continue
        if process_sold_item_data(item_data, site_name):
            new_sold_added_count += 1
    logging.info(f"{new_sold_added_count} new SOLD items added to DB from {site_name}.")


def process_valuation_entries(site_name, valuation_entries_from_site):
    logging.info(
        f"Received {len(valuation_entries_from_site)} VALUATION entries from {site_name}"
    )
    new_valuations_added_count = 0
    for val_data in valuation_entries_from_site:
        if not all(
            k in val_data
            for k in [
                "raw_card_name_from_source",
                "estimated_value",
                "valuation_date",
            ]
        ):
            logging.warning(
                f"Skipping VALUATION entry from {site_name} due to missing essential fields: {val_data.get('raw_card_name_from_source', 'N/A')}"
            )
            continue
        if process_valuation_entry_data(val_data, site_name):
            new_valuations_added_count += 1
    logging.info(
        f"{new_valuations_added_count} new VALUATION entries added to DB from {site_name}."
    )


def log_and_notify_config_error(site_name, data_type_to_collect):
    logging.error(f"Module/function missing for {site_name}/{data_type_to_collect}.")
    send_dashboard_notification(
        "ERROR",
        f"Config error for {site_name}/{data_type_to_collect}: Module/function missing.",
    )


def log_and_notify_return_type_error(site_name, data_type_to_collect):
    logging.error(
        f"Site function for {site_name} did not return a dictionary. Skipping."
    )
    send_dashboard_notification(
        "ERROR", f"Return type error for {site_name}/{data_type_to_collect}."
    )


def log_and_notify_import_error(site_name, module_name, data_type_to_collect):
    logging.error(
        f"Failed to import module: {module_name} for {site_name}/{data_type_to_collect}."
    )
    send_dashboard_notification(
        "ERROR", f"ImportError: {site_name} - {module_name}."
    )


def log_and_notify_attribute_error(
    site_name, module_name, function_name, data_type_to_collect
):
    logging.error(
        f"Failed to find function: {function_name} in {module_name} for {site_name}/{data_type_to_collect}."
    )
    send_dashboard_notification(
        "ERROR",
        f"AttributeError: {site_name} - {module_name}.{function_name}.",
    )


def log_and_notify_runtime_error(site_name, data_type_to_collect, e):
    logging.error(f"Unexpected error for {site_name}/{data_type_to_collect}: {e}")
    send_dashboard_notification(
        "ERROR", f"Runtime error for {site_name}/{data_type_to_collect}: {str(e)}."
    )


if __name__ == "__main__":
    # Create a dummy sites_config.json for testing
    dummy_config_data = [
        {
            "name": "DummySoldValSite",
            "enabled": True,
            "collectors": [
                {
                    "type": "sold_items",
                    "module": "dummy_sold_valuation_api_collector",
                    "function": "fetch_data",
                    "api_details": {"api_key": "dummy_key_sold_val"},
                },
                {
                    "type": "valuations",
                    "module": "dummy_sold_valuation_api_collector",
                    "function": "fetch_data",
                    "api_details": {"api_key": "dummy_key_sold_val"},
                },
            ],
        },
        {
            "name": "DummySalesOnlySite",
            "enabled": True,
            "collectors": [
                {
                    "type": "sold_items",
                    "module": "dummy_sales_only_collector",
                    "function": "fetch_sales_data",
                    "api_details": {"endpoint": "sales.example.com"},
                }
            ],
        },
    ]
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(dummy_config_data, f, indent=2)

    # Create dummy collector files
    with open("dummy_sold_valuation_api_collector.py", "w", encoding="utf-8") as f:
        f.write(
            """
from datetime import datetime, timezone

def fetch_data(config):
    print(f"DUMMY_SOLD_VAL_API: Fetching data with config: {config}")
    last_run = config.get("last_run_timestamp")
    current_time_marker = datetime.now(timezone.utc).isoformat()  # For simulation
    print(f"  Last run timestamp received: {last_run}")

    sold_items = []
    if last_run is None or current_time_marker > last_run:
        sold_items.append({
            "raw_title": "SOLD: 1986 Fleer Michael Jordan RC #57 PSA 8",
            "player_name": "Michael Jordan",
            "card_year": 1986,
            "card_set": "Fleer",
            "card_number": "57",
            "attributes": "Rookie",
            "grade": "PSA 8",
            "grading_company": "PSA",
            "sale_price": 15000.00,
            "currency": "USD",
            "sale_date": datetime.now(timezone.utc).isoformat(),
            "source_item_id": "DUMMYSOLD123",
            "source_url": "http://dummysold.com/item/123",
            "listing_type": "Auction"
        })
        sold_items.append({
            "raw_title": "SOLD: 1989 Upper Deck Ken Griffey Jr RC #1 PSA 9",
            "player_name": "Ken Griffey Jr",
            "card_year": 1989,
            "card_set": "Upper Deck",
            "card_number": "1",
            "attributes": "Rookie",
            "grade": "PSA 9",
            "grading_company": "PSA",
            "sale_price": 150.00,
            "currency": "USD",
            "sale_date": datetime.now(timezone.utc).isoformat(),
            "source_item_id": "DUMMYSOLDKGJ",
            "source_url": "http://dummysold.com/item/kgj",
            "listing_type": "BIN"
        })

    valuations = []
    if last_run is None or current_time_marker > last_run:
        valuations.append({
            "raw_card_name_from_source": "1986 Fleer Michael Jordan RC #57 PSA 8 (Valuation)",
            "player_name": "Michael Jordan",
            "card_year": 1986,
            "card_set": "Fleer",
            "card_number": "57",
            "attributes": "Rookie",
            "grade": "PSA 8",
            "grading_company": "PSA",
            "estimated_value": 15250.00,
            "currency": "USD",
            "valuation_date": datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            "valuation_type": "Market Average",
            "source_url_to_valuation_info": "http://dummypriceguide.com/mj86psa8"
        })
    return {"sold_items": sold_items, "valuation_entries": valuations}
        """
        )

    with open("dummy_sales_only_collector.py", "w", encoding="utf-8") as f:
        f.write(
            """
from datetime import datetime, timezone

def fetch_sales_data(config):
    print(f"DUMMY_SALES_ONLY_COLLECTOR: Fetching sales with config: {config}")
    last_run = config.get("last_run_timestamp")
    current_time_marker = datetime.now(timezone.utc).isoformat()
    print(f"  Last run timestamp received: {last_run}")

    sold_items = []
    if last_run is None or current_time_marker > last_run:
        sold_items.append({
            "raw_title": "SOLD: 2011 Topps Update Mike Trout RC #US175 BGS 9.5",
            "player_name": "Mike Trout",
            "card_year": 2011,
            "card_set": "Topps Update",
            "card_number": "US175",
            "attributes": "Rookie",
            "grade": "BGS 9.5",
            "grading_company": "BGS",
            "sale_price": 3000.00,
            "currency": "USD",
            "sale_date": datetime.now(timezone.utc).isoformat(),
            "source_item_id": "SALESONLYSITE789",
            "source_url": "http://salesonly.com/item/789",
            "listing_type": "Auction"
        })
    return {"sold_items": sold_items}  # No valuation_entries key
        """
        )

    # Run the collector
    print("--- First Run ---")
    collect_all_sold_and_valuations()

    print(
        "\n--- Second Run (should ideally fetch no new data if timestamps work correctly) ---"
    )
    collect_all_sold_and_valuations()

    # Clean up dummy files
    os.remove(CONFIG_FILE_PATH)
    os.remove("dummy_sold_valuation_api_collector.py")
    os.remove("dummy_sales_only_collector.py")
    print(
        f"\nNOTE: Dummy files ({CONFIG_FILE_PATH}, dummy_*.py, {LOG_FILE_PATH}) were created/used."
    )
