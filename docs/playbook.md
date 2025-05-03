## Playbook: Card Finder Operations

### Crawler Fails

1.  Check container logs: `docker logs cardfinder`
    *   Look for `rate-limited` messages or authentication errors (e.g., 401 Unauthorized).
2.  **If Authentication Error:**
    *   The eBay OAuth access token likely expired.
    *   Run the token refresh script (assuming one exists at `scripts/refresh_token.py` - **Note: This script needs to be created**).
    *   Update the `EBAY_ACCESS_TOKEN` in your `.env` file or secret management system.
    *   Restart the container: `docker restart cardfinder`
3.  **If Rate Limited:**
    *   The application is making too many API calls.
    *   Review `collector/adapters/ebay.py` for potential optimizations (e.g., longer sleep intervals, batching requests if possible).
    *   Consider requesting a higher API quota from eBay Developer Portal.
4.  **If Other Errors:**
    *   Investigate the specific error message and stack trace.
    *   Check network connectivity, database connection, etc.

### False Deal Alert

1.  Identify the `listing ID` or `source_item_id` from the alert message.
2.  Query the sales history for the specific card:
    ```sql
    -- Replace ? with the actual card_id
    SELECT * FROM sales_history
    WHERE card_id = (SELECT id FROM cards WHERE player='...' AND year=... AND set_name='...' AND card_num='...' AND attributes='...')
    ORDER BY sold_at DESC
    LIMIT 10;
    ```
3.  Analyze the recent comparable sales (`comps`).
4.  **If ≤ 3 recent comps:** The sample size might be too small for a reliable median.
    *   Consider increasing the required number of comps in the analyzer logic.
    *   Optionally, blacklist this specific card temporarily if it's prone to volatility (e.g., create a `config/blacklist.yaml` - **Note: This needs implementation**).
5.  **If comps exist but the price seems off:**
    *   The alert threshold (e.g., 70% of median) might be too aggressive for this card or market segment.
    *   Adjust the threshold in the analyzer logic (potentially making it dynamic based on velocity or standard deviation).

### Add New Marketplace Adapter

1.  Create a new adapter file in `collector/adapters/`, e.g., `collector/adapters/goldin.py`.
2.  Define a new adapter class, inheriting from a base adapter class (e.g., `BaseAdapter` - **Note: This base class needs to be defined**).
    ```python
    # collector/adapters/goldin.py
    from .base import BaseAdapter # Assuming base.py exists

    class GoldinAdapter(BaseAdapter):
        def __init__(self, api_key):
            self.api_key = api_key
            # ... other setup ...

        async def fetch_raw(self, query: str, limit: int) -> list[dict]:
            # Implement logic to call Goldin API
            # Fetch listings based on query and limit
            # Return a list of dictionaries, normalized to a common format
            # Example format: {'item_id': '...', 'title': '...', 'price': ..., 'end_time': ..., 'source': 'goldin'}
            pass
    ```
3.  Implement the `.fetch_raw()` method to interact with the new marketplace's API and return data in a standardized dictionary format.
4.  Register the new adapter in `collector/__init__.py` (or a dedicated registry module).
    ```python
    # collector/__init__.py (Example registry)
    from .adapters.ebay import EbayAdapter
    from .adapters.goldin import GoldinAdapter

    ADAPTERS = {
        'ebay': EbayAdapter,
        'goldin': GoldinAdapter,
        # ... add other adapters
    }

    def get_adapter(source_name: str, config: dict):
        adapter_class = ADAPTERS.get(source_name)
        if not adapter_class:
            raise ValueError(f"Unknown adapter source: {source_name}")
        # Pass relevant config to the adapter's constructor
        return adapter_class(**config.get(source_name, {}))
    ```
5.  Update the main crawl logic (`cli.py` or orchestrator) to instantiate and use the new adapter based on configuration.