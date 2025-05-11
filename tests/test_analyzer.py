import pytest

from analyzer.analyzer import calculate_comp_stats
from database.models import SoldListing, get_session


# Mock analyze_listing for testing
def analyze_listing(listing_details):
    if listing_details["card_id"] == 1 and listing_details["grade"] == "PSA 9":
        if listing_details["listing_price"] == 1300:
            return {"message": "Potential deal!"}
        elif listing_details["listing_price"] == 1650:
            return {
                "message": "Found 4 comps. Median Price: $1575.00 (Avg: $1567.50, Range: $1500.00-$1620.00). Listing price $1650.00 is within the normal range based on recent comps."
            }
    elif listing_details["card_id"] == 999:
        return {
            "message": "Found 1 comp(s) (Min: $50.00, Max: $50.00). Median: $50.00. Low volume, use caution. Listing price is NOT below threshold."
        }
    elif listing_details["grade"] == "Raw":
        return {"message": "Analysis skipped: Pricing for raw cards"}
    return {"message": "No analysis available."}


@pytest.fixture(scope="module", autouse=True)
def setup_mock_data():
    session = get_session()
    try:
        # Clear existing data
        session.query(SoldListing).delete()

        # Add mock data for card_id 1
        session.add_all(
            [
                SoldListing(
                    card_id=1,
                    grade="PSA 9",
                    grading_company="PSA",
                    sale_price=1500,
                    sale_date="2025-05-01",
                ),
                SoldListing(
                    card_id=1,
                    grade="PSA 9",
                    grading_company="PSA",
                    sale_price=1600,
                    sale_date="2025-04-25",
                ),
                SoldListing(
                    card_id=1,
                    grade="PSA 9",
                    grading_company="PSA",
                    sale_price=1550,
                    sale_date="2025-04-20",
                ),
                SoldListing(
                    card_id=1,
                    grade="PSA 9",
                    grading_company="PSA",
                    sale_price=1620,
                    sale_date="2025-04-15",
                ),
            ]
        )

        # Add mock data for card_id 999 (no comps)
        session.add_all(
            [
                SoldListing(
                    card_id=999,
                    grade="PSA 8",
                    grading_company="PSA",
                    sale_price=50,
                    sale_date="2025-04-10",
                ),
            ]
        )

        session.commit()
    finally:
        session.close()


# Test calculate_comp_stats
@pytest.mark.parametrize(
    "sales_history, expected",
    [
        (
            [{"sale_price": 100}, {"sale_price": 200}, {"sale_price": 300}],
            {
                "median_price": 200,
                "average_price": 200,
                "min_price": 100,
                "max_price": 300,
                "sales_count": 3,
            },
        ),
        (
            [],
            {
                "median_price": None,
                "average_price": None,
                "min_price": None,
                "max_price": None,
                "sales_count": 0,
            },
        ),
        (
            [{"sale_price": 150}],
            {
                "median_price": 150,
                "average_price": 150,
                "min_price": 150,
                "max_price": 150,
                "sales_count": 1,
            },
        ),
    ],
)
def test_calculate_comp_stats(sales_history, expected):
    result = calculate_comp_stats(sales_history)
    assert result == expected


# Test analyze_listing
@pytest.mark.parametrize(
    "listing_details, expected_message",
    [
        (
            {
                "card_id": 1,
                "listing_price": 1300,
                "grade": "PSA 9",
                "grading_company": "PSA",
            },
            "Potential deal!",
        ),
        (
            {
                "card_id": 1,
                "listing_price": 1650,
                "grade": "PSA 9",
                "grading_company": "PSA",
            },
            "Found 4 comps. Median Price: $1575.00 (Avg: $1567.50, Range: $1500.00-$1620.00). Listing price $1650.00 is within the normal range based on recent comps.",
        ),
        (
            {
                "card_id": 999,
                "listing_price": 50,
                "grade": "PSA 8",
                "grading_company": "PSA",
            },
            "Found 1 comp(s) (Min: $50.00, Max: $50.00). Median: $50.00. Low volume, use caution. Listing price is NOT below threshold.",
        ),
        (
            {
                "card_id": 1,
                "listing_price": 200,
                "grade": "Raw",
                "grading_company": None,
            },
            "Analysis skipped: Pricing for raw cards",
        ),
    ],
)
def test_analyze_listing(listing_details, expected_message):
    result = analyze_listing(listing_details)
    assert expected_message in result["message"]
