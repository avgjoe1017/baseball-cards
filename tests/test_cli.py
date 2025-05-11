from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli import cli


@pytest.mark.parametrize(
    "query, limit, token_present, expected_output",
    [
        ("psa 10 topps chrome", 5, True, "Successfully fetched"),
        (
            "psa 10 topps chrome",
            5,
            False,
            "Error: EBAY_ACCESS_TOKEN environment variable not set.",
        ),
    ],
)
def test_crawl(query, limit, token_present, expected_output):
    runner = CliRunner()

    with (
        patch("cli.fetch_cards") as mock_fetch_cards,
        patch.dict(
            "os.environ",
            {"EBAY_ACCESS_TOKEN": "mocked_token"} if token_present else {},
        ),
    ):
        if token_present:
            mock_fetch_cards.return_value = [
                "Card1",
                "Card2",
            ]  # Mocked response

        result = runner.invoke(cli, ["crawl", "--query", query, "--limit", str(limit)])

        assert expected_output in result.output
        if token_present:
            mock_fetch_cards.assert_called_once_with(query, limit=limit)


@pytest.mark.parametrize(
    "query, limit, expected_output",
    [
        ("", 5, "Fetching up to 5 items for query: ''..."),
        (
            "psa 10 topps chrome",
            0,
            "Fetching up to 0 items for query: 'psa 10 topps chrome'...",
        ),
        (
            "psa 10 topps chrome",
            10000,
            "Fetching up to 10000 items for query: 'psa 10 topps chrome'...",
        ),
    ],
)
def test_crawl_edge_cases(query, limit, expected_output):
    runner = CliRunner()

    with (
        patch("cli.fetch_cards") as mock_fetch_cards,
        patch.dict("os.environ", {"EBAY_ACCESS_TOKEN": "mocked_token"}),
    ):
        mock_fetch_cards.return_value = []  # Mocked empty response

        result = runner.invoke(cli, ["crawl", "--query", query, "--limit", str(limit)])

        assert expected_output in result.output
        mock_fetch_cards.assert_called_once_with(query, limit=limit)


def test_crawl_exception_handling():
    runner = CliRunner()

    with (
        patch("cli.fetch_cards") as mock_fetch_cards,
        patch.dict("os.environ", {"EBAY_ACCESS_TOKEN": "mocked_token"}),
    ):
        mock_fetch_cards.side_effect = Exception("Simulated fetch error")

        result = runner.invoke(
            cli, ["crawl", "--query", "psa 10 topps chrome", "--limit", "5"]
        )

        assert "Error during crawl: Simulated fetch error" in result.output


def test_analyze():
    runner = CliRunner()
    result = runner.invoke(cli, ["analyze"])
    assert "Analyzer stub" in result.output
