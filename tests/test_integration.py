from unittest.mock import MagicMock, patch

import pytest

from analyzer.analyzer import analyze_listing  # Removed unused calculate_comp_stats
from collector.adapters.ebay import fetch_cards  # fetch_cards is async
from collector.sold_valuation_collector import collect_all_sold_and_valuations
from database.models import SoldListing, get_session, init_db


@pytest.fixture(scope="function")
def setup_integration_db(request):
    """Initializes DB and populates with mock SoldListing data for integration tests."""
    init_db()  # Ensure tables are created
    session = get_session()
    try:
        # Clear existing data to ensure test isolation
        session.query(SoldListing).delete()
        # Add mock data for card_id 1 (consistent with test_analyzer.py)
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
        session.commit()
        yield
    finally:
        session.close()


@pytest.mark.asyncio
async def test_integration_flow(setup_integration_db):  # Apply the fixture
    # Step 1: Mock eBay API response
    mock_items = [
        {
            "card_id": 1,
            "listing_price": 1300,
            "grade": "PSA 9",
            "grading_company": "PSA",
            "source_url": "http://example.com/listing1",
            "source": "eBay",
        },
        {
            "card_id": 1,
            "listing_price": 1650,
            "grade": "PSA 9",
            "grading_company": "PSA",
            "source_url": "http://example.com/listing2",
            "source": "eBay",
        },
    ]
    mock_ebay_payload = {"itemSummaries": mock_items}

    # Mock both the eBay API call AND the database session used by fetch_cards
    mock_db_session = MagicMock()
    with (
        patch("collector.adapters.ebay._call", return_value=mock_ebay_payload),
        patch("collector.adapters.ebay.get_session", return_value=mock_db_session),
    ):
        # Step 2: Fetch cards from eBay
        # This will now use the mock_db_session internally
        cards = await fetch_cards("psa 10 topps chrome", limit=2)
        assert len(cards) == 2

        # Remove assertion if fetch_cards no longer performs DB inserts
        assert mock_db_session.add.call_count == 2

        # Ensure session.add is called if it should still add items
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called_once()
        mock_db_session.close.assert_called_once()

    # Step 4: Analyze listings
    # Note: analyze_listing uses placeholder data internally for now.
    # If it needed real DB data, you'd mock its DB calls too.
    analysis_results = []
    for card in mock_items:
        result = analyze_listing(card)
        analysis_results.append(result)

    # Verify analysis results
    assert len(analysis_results) == 2
    assert analysis_results[0]["is_potentially_undervalued"] is True
    assert analysis_results[1]["is_potentially_undervalued"] is False


@pytest.mark.parametrize(
    "mock_sites_config",
    [
        [
            {
                "name": "eBay",
                "enabled": True,
                "collectors": [
                    {
                        "type": "sold_items",
                        "module": "collector.adapters.ebay_sold_collector",
                        "function": "fetch_sold_items",
                        "api_details": {"app_id": "mock_app_id"},
                    },
                    {
                        "type": "valuations",
                        "module": "collector.adapters.ebay_valuation_collector",
                        "function": "fetch_valuations",
                        "api_details": {"api_key": "mock_api_key"},
                    },
                ],
            }
        ]
    ],
)
def test_collect_all_sold_and_valuations(mock_sites_config):
    with (
        patch(
            "collector.sold_valuation_collector.load_sites_config",
            return_value=mock_sites_config,
        ),
        patch(
            "collector.sold_valuation_collector.get_last_run_timestamp",
            return_value=None,
        ),
        patch(
            "collector.sold_valuation_collector.update_last_run_timestamp"
        ) as mock_update_timestamp,
        patch(
            "collector.adapters.ebay_sold_collector.fetch_sold_items",
            return_value={
                "sold_items": [
                    {
                        "raw_title": "Mock Item",
                        "sale_price": 100.0,
                        "currency": "USD",
                        "sale_date": "2025-05-07",
                        "source_item_id": "12345",
                        "source_url": "http://example.com",
                    }
                ],
                "valuation_entries": [],
            },
        ),
        patch(
            "collector.adapters.ebay_valuation_collector.fetch_valuations",
            return_value={
                "sold_items": [],
                "valuation_entries": [
                    {
                        "raw_card_name_from_source": "Mock Valuation",
                        "estimated_value": 200.0,
                        "currency": "USD",
                        "valuation_date": "2025-05-07",
                    }
                ],
            },
        ) as mock_valuation_collector,
        patch(
            "collector.sold_valuation_collector.add_sold_listing_to_db",
            return_value=True,
        ),
        patch("collector.sold_valuation_collector.add_valuation", return_value=True),
    ):
        collect_all_sold_and_valuations()

        # Verify that the last run timestamp was updated
        mock_update_timestamp.assert_called()
        # Verify that the valuation collector was called
        mock_valuation_collector.assert_called()
