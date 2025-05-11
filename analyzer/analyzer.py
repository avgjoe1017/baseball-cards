import datetime
import os
import statistics
from datetime import timedelta, timezone

import yaml

from database.models import ActiveListing, SoldListing, get_session


def fetch_sales_history(
    card_id, grade, grading_company, historical_days, analysis_result
):
    """
    Fetch sales history for a specific card, grade, and grading company within a given date range.
    """
    try:
        session = get_session()
        cutoff_date = datetime.datetime.now(timezone.utc) - timedelta(
            days=historical_days
        )
        sales = (
            session.query(SoldListing)
            .filter(
                SoldListing.card_id == card_id,
                SoldListing.grade == grade,
                SoldListing.grading_company == grading_company,
                SoldListing.sale_date >= cutoff_date,
            )
            .all()
        )
        return [
            {"sale_price": sale.sale_price, "sale_date": sale.sale_date}
            for sale in sales
        ]
    except Exception as e:
        analysis_result["message"] = (
            f"Error: Failed to fetch sales history from database - {e}"
        )
        return None
    finally:
        session.close()


# --- Constants ---
DEFAULT_HISTORICAL_DAYS = 90
MIN_COMPS_FOR_RELIABLE_AVG = 3
DEFAULT_UNDERVALUE_THRESHOLD = 0.85


def calculate_comp_stats(sales_history):
    """
    Calculates statistics from a list of sales history records.
    """
    if not sales_history:
        return {
            "median_price": None,
            "average_price": None,
            "min_price": None,
            "max_price": None,
            "sales_count": 0,
        }
    prices = [sale["sale_price"] for sale in sales_history if "sale_price" in sale]
    count = len(prices)
    if count == 0:
        return {
            "median_price": None,
            "average_price": None,
            "min_price": None,
            "max_price": None,
            "sales_count": 0,
        }
    stats = {
        "median_price": statistics.median(prices),
        "average_price": statistics.mean(prices),
        "min_price": min(prices),
        "max_price": max(prices),
        "sales_count": count,
    }
    return stats


def analyze_listing(
    listing_details,
    historical_days=DEFAULT_HISTORICAL_DAYS,
    undervalue_threshold=DEFAULT_UNDERVALUE_THRESHOLD,
    dynamic_threshold=True,
):
    """
    Analyzes a current listing against recent sales comparables.
    """
    analysis_result = initialize_analysis_result(
        listing_details, historical_days, undervalue_threshold
    )
    if not validate_listing_details(listing_details, analysis_result):
        return analysis_result
    card_id, grade, grading_company, listing_price = extract_listing_details(
        listing_details
    )

    if is_blacklisted(card_id, grade):
        analysis_result["message"] = (
            "Suppressed: This card/grade is blacklisted for deal alerts."
        )
        analysis_result["is_potentially_undervalued"] = False
        return analysis_result
    if is_raw_card(grade, analysis_result):
        return analysis_result
    sales_history = fetch_sales_history(
        card_id, grade, grading_company, historical_days, analysis_result
    )
    if sales_history is None:
        return analysis_result
    comp_stats = calculate_comp_stats(sales_history)
    analysis_result["comp_stats"] = comp_stats

    if dynamic_threshold:
        undervalue_threshold = get_dynamic_undervalue_threshold(
            comp_stats, sales_history
        )
    analysis_result["undervalue_threshold"] = undervalue_threshold
    perform_comparison(comp_stats, listing_price, undervalue_threshold, analysis_result)

    update_active_listing_with_analysis(
        card_id, comp_stats, analysis_result["is_potentially_undervalued"]
    )
    return analysis_result


def initialize_analysis_result(listing_details, historical_days, undervalue_threshold):
    """
    Initializes the analysis result dictionary with default values.
    """
    return {
        "listing_details": listing_details,
        "comp_stats": None,
        "analysis_period_days": historical_days,
        "is_potentially_undervalued": False,
        "undervalue_threshold": undervalue_threshold,
        "message": "",
    }


def extract_listing_details(listing_details):
    return (
        listing_details["card_id"],
        listing_details["grade"],
        listing_details["grading_company"],
        listing_details["listing_price"],
    )


def is_raw_card(grade, analysis_result):
    if grade is None or (isinstance(grade, str) and grade.lower() == "raw"):
        analysis_result["message"] = (
            "Analysis skipped: Pricing for raw cards is highly subjective and not reliably comparable."
        )
        return True
    return False


def perform_comparison(
    comp_stats, listing_price, undervalue_threshold, analysis_result
):
    if comp_stats["sales_count"] == 0:
        analysis_result["message"] = (
            f"No recent sales comps found for this exact card/grade in the last "
            f"{analysis_result['analysis_period_days']} days."
        )
    elif comp_stats["sales_count"] < MIN_COMPS_FOR_RELIABLE_AVG:
        handle_low_volume_comps(
            comp_stats, listing_price, undervalue_threshold, analysis_result
        )
    else:
        handle_sufficient_comps(
            comp_stats, listing_price, undervalue_threshold, analysis_result
        )


def handle_low_volume_comps(
    comp_stats, listing_price, undervalue_threshold, analysis_result
):
    analysis_result["message"] = (
        f"Found {comp_stats['sales_count']} comp(s) (Min: ${comp_stats['min_price']:.2f}, "
        f"Max: ${comp_stats['max_price']:.2f}). Median: ${comp_stats['median_price']:.2f}. "
        f"Low volume, use caution."
    )
    if listing_price < comp_stats["median_price"] * undervalue_threshold:
        analysis_result["is_potentially_undervalued"] = True
        analysis_result["message"] += " Listing price is below threshold."
    else:
        analysis_result["message"] += " Listing price is NOT below threshold."


def handle_sufficient_comps(
    comp_stats, listing_price, undervalue_threshold, analysis_result
):
    median_comp = comp_stats["median_price"]
    analysis_result["message"] = (
        f"Found {comp_stats['sales_count']} comps. Median Price: ${median_comp:.2f} "
        f"(Avg: ${comp_stats['average_price']:.2f}, Range: ${comp_stats['min_price']:.2f}-"
        f"${comp_stats['max_price']:.2f})."
    )
    if listing_price < median_comp * undervalue_threshold:
        analysis_result["is_potentially_undervalued"] = True
        analysis_result["message"] += (
            f" Listing price ${listing_price:.2f} is below the "
            f"{undervalue_threshold * 100:.0f}% threshold "
            f"(${median_comp * undervalue_threshold:.2f}). Potential deal!"
        )
    else:
        analysis_result["message"] += (
            f" Listing price ${listing_price:.2f} is within the normal range "
            f"based on recent comps."
        )


def validate_listing_details(listing_details, analysis_result):
    """
    Validates the listing details to ensure all required fields are present.
    """
    required_keys = ["card_id", "listing_price", "grade", "grading_company"]
    missing_keys = [key for key in required_keys if key not in listing_details]
    if missing_keys:
        analysis_result["message"] = (
            f"Validation failed: Missing keys {missing_keys} in listing details."
        )
        return False
    return True


def is_blacklisted(card_id, grade):
    """
    Checks if a card/grade combination is blacklisted.
    """
    blacklist_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config", "blacklist.yaml"
    )
    try:
        with open(blacklist_path, "r", encoding="utf-8") as f:
            bl = yaml.safe_load(f) or []
        for entry in bl:
            if (
                entry.get("card_id") == card_id
                and entry.get("grade", "").lower() == (grade or "").lower()
            ):
                return True
    except Exception:
        pass
    return False


def get_dynamic_undervalue_threshold(comp_stats, sales_history):
    """
    Calculates a dynamic undervalue threshold based on sales data.
    """
    base = DEFAULT_UNDERVALUE_THRESHOLD
    if not sales_history or comp_stats["sales_count"] < 3:
        return base
    prices = [s["sale_price"] for s in sales_history]
    stddev = statistics.stdev(prices) if len(prices) > 1 else 0
    velocity = comp_stats["sales_count"] / DEFAULT_HISTORICAL_DAYS
    if stddev > 0.2 * comp_stats["median_price"]:
        return min(base + 0.1, 0.95)
    if velocity < 0.05:
        return min(base + 0.05, 0.9)
    return base


def update_active_listing_with_analysis(card_id, comp_stats, is_undervalued):
    """
    Update the ActiveListing table with comp_value and is_undervalued.
    """
    session = get_session()
    try:
        listing = session.query(ActiveListing).filter_by(card_id=card_id).first()
        if listing:
            listing.comp_value = comp_stats.get("median_price")
            listing.is_undervalued = is_undervalued
            session.add(listing)
            session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error updating ActiveListing for card_id {card_id}: {e}")
    finally:
        session.close()


# --- Example Usage ---
if __name__ == "__main__":
    print("--- Running Analyzer Examples ---")

    listing1 = {
        "card_id": 1,
        "listing_price": 1300.00,
        "grade": "PSA 9",
        "grading_company": "PSA",
        "source_url": "http://example.com/listing1",
        "source": "eBay",
    }
    analysis1 = analyze_listing(listing1, historical_days=90, undervalue_threshold=0.85)
    print("\nAnalysis Result 1:")
    import json

    print(json.dumps(analysis1, indent=2))

    listing2 = {
        "card_id": 1,
        "listing_price": 1650.00,
        "grade": "PSA 9",
        "grading_company": "PSA",
        "source_url": "http://example.com/listing2",
        "source": "eBay",
    }
    analysis2 = analyze_listing(listing2, historical_days=90, undervalue_threshold=0.85)
    print("\nAnalysis Result 2:")
    print(json.dumps(analysis2, indent=2))

    listing3 = {
        "card_id": 999,
        "listing_price": 50.00,
        "grade": "PSA 8",
        "grading_company": "PSA",
        "source_url": "http://example.com/listing3",
        "source": "COMC",
    }
    analysis3 = analyze_listing(listing3)
    print("\nAnalysis Result 3:")
    print(json.dumps(analysis3, indent=2))

    listing4 = {
        "card_id": 1,
        "listing_price": 200.00,
        "grade": "Raw",
        "grading_company": None,
        "source_url": "http://example.com/listing4",
        "source": "eBay",
    }
    analysis4 = analyze_listing(listing4)
    print("\nAnalysis Result 4:")
    print(json.dumps(analysis4, indent=2))

    print("\nAnalysis Result 5 (Few Comps - requires adjusting placeholder data):")
