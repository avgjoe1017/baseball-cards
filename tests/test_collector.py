import os
from unittest.mock import MagicMock, patch

import pytest

try:
    from aioresponses import aioresponses
except ImportError:
    aioresponses = None

from collector import active_listings_collector as alc
from collector.active_listings_collector import (
    process_site,
    send_dashboard_notification,
)
from collector.adapters.ebay import fetch_cards
from collector.adapters.ebay_sold_collector import fetch_sold_items
from collector.adapters.ebay_valuation_collector import fetch_valuations
from collector.adapters.sportscardspro_sold_collector import (
    fetch_sold_items as scp_fetch_sold_items,
)
from collector.adapters.sportscardspro_valuation_collector import (
    fetch_valuations as scp_fetch_valuations,
)
from database.models import Card, Session


@patch("collector.active_listings_collector.load_config")
def test_load_config(mock_load_config):
    mock_load_config.return_value = [
        {
            "name": "eBay",
            "type": "API",
            "enabled": True,
            "module": "collector.adapters.ebay",
            "function": "collect_ebay_listings",
        }
    ]
    config = alc.load_config()
    mock_load_config.assert_called_once()
    assert len(config) == 1


@patch("collector.active_listings_collector.importlib.import_module")
@patch("collector.active_listings_collector.add_card_definition")
@patch("collector.active_listings_collector.add_active_listing_to_db")
def test_process_site(
    mock_add_active_listing_to_db, mock_add_card_definition, mock_import_module
):
    mock_site_function = MagicMock()
    mock_site_function.return_value = [
        {
            "player_name": "Test Player",
            "card_year": 2025,
            "card_set": "Test Set",
            "card_number": "123",
            "attributes": "Test Attributes",
            "raw_title": "Test Card",
            "listing_price": 10.0,
            "currency": "USD",
            "source": "eBay",
            "source_item_id": "12345",
            "source_url": "http://example.com",
            "grade": "PSA 9",
            "grading_company": "PSA",
        }
    ]
    mock_module = MagicMock()
    mock_module.collect_ebay_listings = mock_site_function
    mock_import_module.return_value = mock_module

    mock_add_card_definition.return_value = 1

    site_config = {
        "name": "eBay",
        "enabled": True,
        "collectors": [
            {
                "module": "collector.adapters.ebay",
                "function": "collect_ebay_listings",
            }
        ],
    }

    process_site(site_config)
    mock_add_card_definition.assert_called_once()
    mock_add_active_listing_to_db.assert_called_once()


@patch("builtins.print")
def test_send_dashboard_notification(mock_print):
    send_dashboard_notification("INFO", "Test message")
    mock_print.assert_called_once_with("NOTIFICATION [INFO]: Test message")


@pytest.mark.asyncio
async def test_fetch_cards():
    query = "psa 10 topps chrome"
    limit = 5

    mock_response = {
        "itemSummaries": [
            {
                "title": "PSA 10 Topps Chrome Card 1",
                "categoryPath": "Sports Memorabilia > Cards",
                "itemId": "1234567890",
            },
            {
                "title": "PSA 10 Topps Chrome Card 2",
                "categoryPath": "Sports Memorabilia > Cards",
                "itemId": "0987654321",
            },
        ]
    }

    mock_session = MagicMock(spec=Session)
    added_cards_in_session_scope = []

    def side_effect_for_add(card_instance):
        added_cards_in_session_scope.append(card_instance)

    mock_session.add.side_effect = side_effect_for_add

    current_mock_pk_id = 1

    def side_effect_for_flush():
        nonlocal current_mock_pk_id
        for card_obj in added_cards_in_session_scope:
            if isinstance(card_obj, Card) and getattr(card_obj, "id", None) is None:
                card_obj.id = current_mock_pk_id
                current_mock_pk_id += 1

    mock_session.flush = MagicMock(side_effect=side_effect_for_flush)
    actual_commit_action_mock = MagicMock(name="ActualCommitActionMock")

    def side_effect_for_commit(*args, **kwargs):
        mock_session.flush()
        actual_commit_action_mock(*args, **kwargs)

    mock_session.commit = MagicMock(side_effect=side_effect_for_commit)
    mock_session.close = MagicMock()

    with (
        patch("collector.adapters.ebay.get_session", return_value=mock_session),
        patch.dict(os.environ, {"EBAY_ACCESS_TOKEN": "mocked_token"}),
        aioresponses() as m,
    ):
        m.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search"
            "?q=psa%2010%20topps%20chrome&limit=50&offset=0",
            headers={"Authorization": "Bearer mocked_token"},
            payload=mock_response,
        )

        cards = await fetch_cards(query, limit)

    assert len(cards) == 2
    assert cards[0]["source_item_id"] == "1234567890"
    assert cards[1]["source_item_id"] == "0987654321"

    assert mock_session.add.call_count == 2
    assert len(added_cards_in_session_scope) == 2
    mock_session.flush.assert_called_once()

    assigned_ids = set()
    for card_in_mock_db in added_cards_in_session_scope:
        assert isinstance(card_in_mock_db, Card)
        assert card_in_mock_db.id is not None
        assigned_ids.add(card_in_mock_db.id)
    assert len(assigned_ids) == len(added_cards_in_session_scope)

    actual_commit_action_mock.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.parametrize(
    "config, expected_count",
    [
        (
            {
                "api_details": {"app_id": "mock_app_id"},
                "last_run_timestamp": None,
            },
            0,
        )
    ],
)
def test_ebay_sold_collector(config, expected_count):
    with patch("collector.adapters.ebay_sold_collector.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "findCompletedItemsResponse": [{"searchResult": [{"item": []}]}]
        }
        result = fetch_sold_items(config)
        assert len(result["sold_items"]) == expected_count


@pytest.mark.parametrize(
    "config, expected_count",
    [
        (
            {
                "api_details": {"app_id": "mock_app_id"},
                "last_run_timestamp": None,
            },
            0,
        )
    ],
)
def test_ebay_valuation_collector(config, expected_count):
    with patch("collector.adapters.ebay_valuation_collector.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"valuations": []}
        result = fetch_valuations(config)
        assert len(result["valuation_entries"]) == expected_count


@pytest.mark.parametrize(
    "config, expected_count",
    [
        (
            {
                "api_details": {"api_token": "mock_token"},
                "last_run_timestamp": None,
            },
            0,
        )
    ],
)
def test_sportscardspro_sold_collector(config, expected_count):
    with patch(
        "collector.adapters.sportscardspro_sold_collector.requests.get"
    ) as mock_get:
        mock_get.return_value.json.return_value = {"sold_items": []}
        result = scp_fetch_sold_items(config)
        assert len(result["sold_items"]) == expected_count


@pytest.mark.parametrize(
    "config, expected_count",
    [
        (
            {
                "api_details": {"api_token": "mock_token"},
                "last_run_timestamp": None,
            },
            0,
        )
    ],
)
def test_sportscardspro_valuation_collector(config, expected_count):
    with patch(
        "collector.adapters.sportscardspro_valuation_collector.requests.get"
    ) as mock_get:
        mock_get.return_value.json.return_value = {"valuation_entries": []}
        result = scp_fetch_valuations(config)
        assert len(result["valuation_entries"]) == expected_count
