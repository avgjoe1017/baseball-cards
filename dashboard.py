import asyncio
import json
import os
import re

import pandas as pd
import streamlit as st
from dotenv import load_dotenv, set_key
from sqlalchemy import text

# --- Import your existing functions ---
# Note: Adjust imports based on your project structure and async needs
from collector.adapters.ebay import fetch_cards
from database.models import SoldListing  # Added SoldListing import
from database.models import (
    ActiveListing,
    Card,
    add_active_listing_to_db,
    add_card_definition,
    get_session,
)


# --- Helper to run async functions in Streamlit ---
def run_async(func):
    return asyncio.run(func)


# --- Simple NLP ---
def parse_command(text):
    text = text.lower()
    if text.startswith("crawl") or text.startswith("fetch"):
        match_limit = re.search(r"limit (\d+)", text)
        limit = int(match_limit.group(1)) if match_limit else 5  # Default limit
        # Very basic query extraction - assumes query is after "for" or the command word
        query_match = re.search(r"(?:crawl|fetch) for (.+?)(?: limit \d+|$)", text)
        if not query_match:
            query_match = re.search(r"(?:crawl|fetch) (.+?)(?: limit \d+|$)", text)
        query = (
            query_match.group(1).strip() if query_match else "psa 10"
        )  # Default query
        return {"intent": "crawl", "params": {"query": query, "limit": limit}}
    # Add more parsing rules for "analyze", "show sales", etc.
    # elif text.startswith("analyze"):
    #     # ... parse for card details ...
    #     return {"intent": "analyze", "params": {...}}
    else:
        return {"intent": "unknown", "params": {}}


# --- Streamlit App ---
st.title("Baseball Card Assistant")

# --- Add tabs for different functionalities ---
tabs = st.tabs(
    [
        "Scan",
        "Deals",
        "Database",
        "Comps & Charts",
        "System Health",
        "Settings",
    ]
)


def scan_tab():
    """
    Scan tab logic to fetch and display new listings.
        This function itself is synchronous as Streamlit runs in a sync manner.
        It calls async functions using run_async.
    """
    # This is just an example of how you might trigger it.
    # In a real dashboard, you'd likely have a button or scheduled refresh.


if st.button("Run Scan for Saved Queries (Example)"):
    with st.spinner("Scanning saved queries..."):
        session = get_session()
        try:
            saved_queries = [
                "PSA 10 Griffey UD 1989",
                "PSA 9 Jordan Rookie",
            ]  # Example saved queries
            for query in saved_queries:
                st.write(f"Fetching for: {query}")
                listings = run_async(fetch_cards(query))  # Use run_async
                for listing_data in listings:  # Renamed to avoid conflict
                    card_id = add_card_definition(
                        listing_data
                    )  # add_card_definition manages its own session
                    add_active_listing_to_db(
                        session, card_id, listing_data
                    )  # Pass existing session
            session.commit()  # Commit once after processing all queries
            st.success("Scan complete for saved queries.")
        except Exception as e:
            session.rollback()
            st.error(f"Error during scan: {e}")
        finally:
            session.close()


def deals_tab():
    """
    Deals tab logic to show active listings where price is below calculated comp value.
    """
    session = get_session()
    try:
        deals = (
            session.query(ActiveListing)
            .filter(ActiveListing.listing_price < ActiveListing.comp_value)
            .all()
        )
        return deals
    finally:
        session.close()


# --- Database Query Helper ---
def query_cards():
    session = get_session()
    try:
        listings = session.query(ActiveListing).all()
        # Build a list of dicts for DataFrame
        data = []
        for listing in listings:
            data.append(
                {
                    "Player": getattr(listing, "player", ""),
                    "Year": getattr(listing, "year", ""),
                    "Set": getattr(listing, "set_name", ""),
                    "Card Number": getattr(listing, "card_num", ""),
                    "Attributes": getattr(listing, "attributes", ""),
                    "Grade": listing.grade,
                    "Grading Company": listing.grading_company,
                    "Price": listing.listing_price,
                    "Currency": listing.currency,
                    "Source": listing.source,
                    "Source Item ID": listing.source_item_id,
                    "URL": listing.source_url,
                    "Last Seen": listing.last_seen_at,
                    "Comp Value": listing.comp_value,
                    "Is Undervalued": listing.is_undervalued,
                }
            )
        return data
    finally:
        session.close()


# --- Scan Tab ---
with tabs[0]:
    st.header("Scan for Cards")
    query = st.text_input("Enter your query (e.g., 'PSA 10 Griffey UD 1989'):")
    limit = st.slider("Limit", min_value=1, max_value=100, value=10)
    if st.button("Run Scan"):
        with st.spinner("Scanning..."):
            # Assuming fetch_cards returns data that can be directly displayed
            # and that database saving happens separately or is triggered here.
            # For now, just fetching and displaying.
            results = run_async(fetch_cards(query, limit=limit))  # Pass limit
            st.success(f"Found {len(results)} listings.")
            st.dataframe(pd.DataFrame(results))

# --- Deals Tab ---
with tabs[1]:
    st.header("Undervalued Deals")
    st.text("Filter and view flagged deals.")
    # Query deals
    deals = deals_tab()
    if deals:
        deals_data = []
        for listing in deals:
            pct_below = None
            if listing.comp_value and listing.listing_price:
                try:
                    pct_below = round(
                        100 * (1 - listing.listing_price / listing.comp_value),
                        1,
                    )
                except Exception:
                    pct_below = None
            deals_data.append(
                {
                    "Player": getattr(listing, "player", ""),
                    "Year": getattr(listing, "year", ""),
                    "Set": getattr(listing, "set_name", ""),
                    "Card Number": getattr(listing, "card_num", ""),
                    "Attributes": getattr(listing, "attributes", ""),
                    "Grade": listing.grade,
                    "Grading Company": listing.grading_company,
                    "Price": listing.listing_price,
                    "Comp Value": listing.comp_value,
                    "% Below Comp": pct_below,
                    "Currency": listing.currency,
                    "Source": listing.source,
                    "Source Item ID": listing.source_item_id,
                    "URL": listing.source_url,
                    "Last Seen": listing.last_seen_at,
                }
            )
        df = pd.DataFrame(deals_data)
        # Sidebar filters for deals
        st.sidebar.header("Deals Filters")
        player_filter = st.sidebar.multiselect(
            "Player (Deals)",
            sorted(df["Player"].dropna().unique()),
            default=None,
        )
        year_filter = st.sidebar.multiselect(
            "Year (Deals)", sorted(df["Year"].dropna().unique()), default=None
        )
        grade_filter = st.sidebar.multiselect(
            "Grade (Deals)",
            sorted(df["Grade"].dropna().unique()),
            default=None,
        )
        source_filter = st.sidebar.multiselect(
            "Source (Deals)",
            sorted(df["Source"].dropna().unique()),
            default=None,
        )
        pct_below_min, pct_below_max = st.sidebar.slider(
            "% Below Comp", min_value=0, max_value=100, value=(0, 100)
        )
        filtered_df = df.copy()
        if player_filter:
            filtered_df = filtered_df[filtered_df["Player"].isin(player_filter)]
        if year_filter:
            filtered_df = filtered_df[filtered_df["Year"].isin(year_filter)]
        if grade_filter:
            filtered_df = filtered_df[filtered_df["Grade"].isin(grade_filter)]
        if source_filter:
            filtered_df = filtered_df[filtered_df["Source"].isin(source_filter)]
        filtered_df = filtered_df[
            (filtered_df["% Below Comp"].fillna(0) >= pct_below_min)
            & (filtered_df["% Below Comp"].fillna(0) <= pct_below_max)
        ]
        # Make URL clickable
        if not filtered_df.empty and "URL" in filtered_df.columns:
            filtered_df["URL"] = filtered_df["URL"].apply(
                lambda x: f"[link]({x})" if pd.notnull(x) and x else ""
            )
        st.dataframe(filtered_df, use_container_width=True)
        # Export to CSV
        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button("Export Deals to CSV", csv, "deals.csv", "text/csv")
        # --- Visualizations ---
        st.subheader("Deal Analytics")
        if not filtered_df.empty:
            st.bar_chart(filtered_df.set_index("Player")["% Below Comp"])
            st.boxplot = st.box_chart(filtered_df["Price"])
            st.metric("Median % Below Comp", filtered_df["% Below Comp"].median())
            st.metric("Median Price", filtered_df["Price"].median())
            st.metric("# Deals", len(filtered_df))
    else:
        st.info("No undervalued deals found.")

# --- Database Tab ---
with tabs[2]:
    st.header("Database Explorer")
    st.text("Explore stored cards and sales history.")
    db_data = query_cards()
    if db_data:
        df = pd.DataFrame(db_data)
        # Sidebar filters
        st.sidebar.header("Database Filters")
        player_filter = st.sidebar.multiselect(
            "Player", sorted(df["Player"].dropna().unique()), default=None
        )
        year_filter = st.sidebar.multiselect(
            "Year", sorted(df["Year"].dropna().unique()), default=None
        )
        grade_filter = st.sidebar.multiselect(
            "Grade", sorted(df["Grade"].dropna().unique()), default=None
        )
        source_filter = st.sidebar.multiselect(
            "Source", sorted(df["Source"].dropna().unique()), default=None
        )
        undervalued_filter = st.sidebar.selectbox(
            "Is Undervalued", options=["All", True, False], index=0
        )

        filtered_df = df.copy()
        if player_filter:
            filtered_df = filtered_df[filtered_df["Player"].isin(player_filter)]
        if year_filter:
            filtered_df = filtered_df[filtered_df["Year"].isin(year_filter)]
        if grade_filter:
            filtered_df = filtered_df[filtered_df["Grade"].isin(grade_filter)]
        if source_filter:
            filtered_df = filtered_df[filtered_df["Source"].isin(source_filter)]
        if undervalued_filter != "All":
            filtered_df = filtered_df[
                filtered_df["Is Undervalued"] == undervalued_filter
            ]

        # Make URL clickable
        if not filtered_df.empty and "URL" in filtered_df.columns:
            filtered_df["URL"] = filtered_df["URL"].apply(
                lambda x: f"[link]({x})" if pd.notnull(x) and x else ""
            )

        st.dataframe(filtered_df, use_container_width=True)
        # Export to CSV
        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button("Export to CSV", csv, "active_listings.csv", "text/csv")
    else:
        st.info("No active listings found in the database.")

# --- Comps & Charts Tab ---
with tabs[3]:
    st.header("Comps & Charts")
    st.text("Visualize sales data and trends.")
    session = get_session()
    # Dropdowns for card selection
    cards = session.query(Card).all()
    if not cards:
        st.info("No cards in database.")
    else:
        card_df = pd.DataFrame(
            [
                {
                    "Player": c.player,
                    "Year": c.year,
                    "Set": c.set_name,
                    "Card Number": c.card_num,
                    "Attributes": c.attributes,
                    "id": c.id,
                }
                for c in cards
            ]
        )
        player = st.selectbox("Player", sorted(card_df["Player"].dropna().unique()))
        year = st.selectbox(
            "Year",
            sorted(card_df[card_df["Player"] == player]["Year"].dropna().unique()),
        )
        set_name = st.selectbox(
            "Set",
            sorted(
                card_df[(card_df["Player"] == player) & (card_df["Year"] == year)][
                    "Set"
                ]
                .dropna()
                .unique()
            ),
        )
        card_num = st.selectbox(
            "Card Number",
            sorted(
                card_df[
                    (card_df["Player"] == player)
                    & (card_df["Year"] == year)
                    & (card_df["Set"] == set_name)
                ]["Card Number"]
                .dropna()
                .unique()
            ),
        )
        attributes = st.selectbox(
            "Attributes",
            sorted(
                card_df[
                    (card_df["Player"] == player)
                    & (card_df["Year"] == year)
                    & (card_df["Set"] == set_name)
                    & (card_df["Card Number"] == card_num)
                ]["Attributes"]
                .dropna()
                .unique()
            ),
        )
        # Get card_id
        card_row = card_df[
            (card_df["Player"] == player)
            & (card_df["Year"] == year)
            & (card_df["Set"] == set_name)
            & (card_df["Card Number"] == card_num)
            & (card_df["Attributes"] == attributes)
        ]
        if not card_row.empty:
            card_id = int(card_row.iloc[0]["id"])
            # Grade selection from SoldListing
            grades = (
                session.query(SoldListing.grade)
                .filter(SoldListing.card_id == card_id)
                .distinct()
                .all()
            )
            grade_options = sorted([g[0] for g in grades if g[0]])
            grade = st.selectbox("Grade", grade_options)
            # Query comps
            comps = (
                session.query(SoldListing)
                .filter(SoldListing.card_id == card_id, SoldListing.grade == grade)
                .order_by(SoldListing.sale_date)
                .all()
            )
            if not comps:
                st.warning("No sales comps found for this card/grade.")
            else:
                comps_df = pd.DataFrame(
                    [
                        {
                            "Sale Price": c.sale_price,
                            "Sale Date": c.sale_date,
                            "Source": c.source,
                            "URL": c.source_url,
                        }
                        for c in comps
                    ]
                )
                st.subheader("Sale Price Time Series")
                st.line_chart(comps_df.set_index("Sale Date")["Sale Price"])
                st.subheader("Price Distribution (Boxplot)")
                st.box_chart(comps_df["Sale Price"])
                # Sales velocity
                now = pd.Timestamp.now(tz="UTC")
                comps_df["Sale Date"] = pd.to_datetime(comps_df["Sale Date"])
                last_30 = comps_df[comps_df["Sale Date"] >= now - pd.Timedelta(days=30)]
                last_90 = comps_df[comps_df["Sale Date"] >= now - pd.Timedelta(days=90)]
                st.metric("Sales in last 30 days", len(last_30))
                st.metric("Sales in last 90 days", len(last_90))
                st.metric("Median Sale Price", comps_df["Sale Price"].median())
                st.metric("Average Sale Price", comps_df["Sale Price"].mean())
                # Show table with clickable URLs
                comps_df["URL"] = comps_df["URL"].apply(
                    lambda x: f"[link]({x})" if pd.notnull(x) and x else ""
                )
                st.dataframe(comps_df)
    session.close()

# --- System Health Tab ---
with tabs[4]:
    st.header("System Health")
    st.text("Monitor the health of the system.")
    # Parse log for metrics
    log_path = os.path.join(
        os.path.dirname(__file__), "sold_valuation_collector_log.txt"
    )
    last_crawl = None
    error_count = 0
    success_count = 0
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if "Finished collection attempt" in line:
                    # Extract timestamp
                    ts = line.split(" ")[0] + " " + line.split(" ")[1]
                    last_crawl = ts
                    success_count += 1
                if "ERROR" in line or "Failed" in line:
                    error_count += 1
    except Exception as e:
        st.warning(f"Could not read log: {e}")
    st.metric(label="Last Crawl Time", value=last_crawl or "N/A")
    st.metric(label="Crawl Successes", value=success_count)
    st.metric(label="Error Count", value=error_count)
    st.metric(label="API Quota Usage", value="(Not available in log)")

# --- Settings Tab ---
with tabs[5]:
    st.header("Settings")
    # Saved Queries
    st.subheader("Saved Queries")
    queries_path = os.path.join(os.path.dirname(__file__), "saved_queries.json")
    if os.path.exists(queries_path):
        with open(queries_path, "r", encoding="utf-8") as f:
            saved_queries = json.load(f)
    else:
        saved_queries = ["PSA 10 Griffey UD 1989", "PSA 9 Jordan Rookie"]
    # Replace st.experimental_data_editor with st.text_area for editing saved queries
    queries = st.text_area(
        "Edit Saved Queries (one per line):",
        value="\n".join(saved_queries),
        height=200,
        key="queries_editor",
    )
    queries = [query.strip() for query in queries.split("\n") if query.strip()]
    if st.button("Save Queries"):
        with open(queries_path, "w", encoding="utf-8") as f:
            json.dump(queries, f, indent=2)
        st.success("Saved queries updated.")
    # API Key Management
    st.subheader("API Keys (.env)")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
    ebay_key = os.getenv("EBAY_APP_ID", "")
    ebay_token = os.getenv("EBAY_ACCESS_TOKEN", "")
    st.write(f"eBay App ID: {ebay_key[:4]}...{ebay_key[-4:] if ebay_key else ''}")
    st.write(
        f"eBay Access Token: {ebay_token[:4]}...{ebay_token[-4:] if ebay_token else ''}"
    )
    new_ebay_token = st.text_input(
        "Update eBay Access Token", value="", type="password"
    )
    if st.button("Save eBay Token") and new_ebay_token:
        set_key(env_path, "EBAY_ACCESS_TOKEN", new_ebay_token)
        st.success("eBay Access Token updated in .env.")
    # Thresholds
    st.subheader("Analysis Thresholds")
    undervalue = st.slider(
        "Undervalue Threshold (%)",
        min_value=50,
        max_value=100,
        value=int(float(os.getenv("UNDERVALUE_THRESHOLD", 85))),
    )
    hist_days = st.slider(
        "Historical Days for Comps",
        min_value=7,
        max_value=180,
        value=int(float(os.getenv("HISTORICAL_DAYS", 90))),
    )
    if st.button("Save Thresholds"):
        set_key(env_path, "UNDERVALUE_THRESHOLD", str(undervalue))
        set_key(env_path, "HISTORICAL_DAYS", str(hist_days))
        st.success("Thresholds updated in .env.")
    # Materialized View Refresh
    st.subheader("Database Maintenance")
    if st.button("Refresh Materialized Views"):
        session = get_session()
        try:
            # Replace with your actual materialized view names
            views = ["comp_stats_mv"]
            for view in views:
                session.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            session.commit()
            st.success("Materialized views refreshed.")
        except Exception as e:
            st.error(f"Failed to refresh materialized views: {e}")
        finally:
            session.close()
